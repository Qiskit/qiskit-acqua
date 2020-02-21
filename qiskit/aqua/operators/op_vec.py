# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

""" Eager Operator Vec Container """


import numpy as np
from functools import reduce

from .operator_base import OperatorBase


class OpVec(OperatorBase):
    """ A class for storing and manipulating lists of operators. Vec here refers to the fact that this class serves
    as a base class for other Operator combinations which store a list of operators, such as OpSum or OpKron,
    but also refers to the "vec" mathematical operation.
    """

    def __init__(self, oplist, combo_fn=lambda x: x, coeff=1.0):
        """
        Args:
            oplist (list(OperatorBase)): The operators being summed.
            combo_fn (callable): The recombination function to reduce classical operators when available (e.g. sum)
            coeff (int, float, complex): A coefficient multiplying the primitive

            Note that the default "recombination function" lambda above is the identity - it takes a list of operators,
            and is supposed to return a list of operators.
        """
        self._oplist = oplist
        self._combo_fn = combo_fn
        self._coeff = coeff

    @property
    def oplist(self):
        return self._oplist

    @property
    def combo_fn(self):
        return self._combo_fn

    @property
    def coeff(self):
        return self._coeff

    def get_primitives(self):
        """ Return a set of primitives in the Operator """
        return reduce(set.union, [op.get_primitives() for op in self.oplist])

    @property
    def num_qubits(self):
        """ For now, follow tensor convention that each Operator in the vec is a separate "system" """
        return sum([op.num_qubits for op in self.oplist])

    # TODO change to *other to efficiently handle lists?
    def add(self, other):
        """ Addition. Overloaded by + in OperatorBase. OpSum overrides with its own add(). """
        if self == other:
            return self.mul(2.0)

        # TODO do this lazily for some primitives (Pauli, Instruction), and eager for others (Matrix)?
        # if eager and isinstance(other, OpPrimitive):
        #     return self.__class__([op.add(other) for op in self.oplist], coeff=self.coeff)

        # Avoid circular dependency
        from .op_sum import OpSum
        return OpSum([self, other])

    def neg(self):
        """ Negate. Overloaded by - in OperatorBase. """
        return self.mul(-1.0)

    def adjoint(self):
        """ Return operator adjoint (conjugate transpose). Overloaded by ~ in OperatorBase.

        Works for OpSum, OpCompose, OpVec, OpKron, at least. New combos must check whether they need to overload this.
        """
        # TODO test this a lot...
        # TODO do this lazily? Basically rebuilds the entire tree, and ops and adjoints almost always come in pairs.
        return self.__class__([op.adjoint() for op in self.oplist], coeff=np.conj(self.coeff))

    def traverse(self, convert_fn, coeff=None):
        """ Apply the convert_fn to each node in the oplist. """
        return self.__class__([convert_fn(op) for op in self.oplist], coeff=coeff or self.coeff)

    def equals(self, other):
        """ Evaluate Equality. Overloaded by == in OperatorBase. """
        if not isinstance(other, type(self)) or not len(self.oplist) == len(other.oplist):
            return False
        # TODO test this a lot
        # Note, ordering matters here (i.e. different ordered lists will return False), maybe it shouldn't
        return self.oplist == other.oplist

    def mul(self, scalar):
        """ Scalar multiply. Overloaded by * in OperatorBase. """
        if not isinstance(scalar, (int, float, complex)):
            raise ValueError('Operators can only be scalar multiplied by float or complex, not '
                             '{} of type {}.'.format(scalar, type(scalar)))
        # return self.__class__([op.mul(scalar) for op in self.oplist])
        return self.__class__(self.oplist, coeff=self.coeff * scalar)

    def kron(self, other):
        """ Kron
        Note: You must be conscious of Qiskit's big-endian bit printing convention. Meaning, X.kron(Y)
        produces an X on qubit 0 and an Y on qubit 1, or X⨂Y, but would produce a QuantumCircuit which looks like
        -[Y]-
        -[X]-
        Because Terra prints circuits and results with qubit 0 at the end of the string or circuit.
        """
        # TODO do this lazily for some primitives (Matrix), and eager for others (Pauli, Instruction)?
        # NOTE: Doesn't work for OpComposition!
        # if eager and isinstance(other, OpPrimitive):
        #     return self.__class__([op.kron(other) for op in self.oplist], coeff=self.coeff)

        # Avoid circular dependency
        from .op_kron import OpKron
        return OpKron([self, other])

    def kronpower(self, other):
        """ Kron with Self Multiple Times """
        if not isinstance(other, int) or other <= 0:
            raise TypeError('Kronpower can only take positive int arguments')

        # Avoid circular dependency
        from .op_kron import OpKron
        return OpKron([self]*other)

    # TODO change to *other to efficiently handle lists?
    def compose(self, other):
        """ Operator Composition (Linear algebra-style, right-to-left)

        Note: You must be conscious of Quantum Circuit vs. Linear Algebra ordering conventions. Meaning, X.compose(Y)
        produces an X∘Y on qubit 0, but would produce a QuantumCircuit which looks like
        -[Y]-[X]-
        Because Terra prints circuits with the initial state at the left side of the circuit.
        """

        # TODO do this lazily for some primitives (Matrix), and eager for others (Pauli, Instruction)?
        # if eager and isinstance(other, OpPrimitive):
        #     return self.__class__([op.compose(other) for op in self.oplist], coeff=self.coeff)

        # Avoid circular dependency
        from .op_composition import OpComposition
        return OpComposition([self, other])

    def power(self, other):
        """ Compose with Self Multiple Times """
        if not isinstance(other, int) or other <= 0:
            raise TypeError('power can only take positive int arguments')

        # Avoid circular dependency
        from .op_composition import OpComposition
        return OpComposition([self]*other)

    def to_matrix(self, massive=False):
        """ Return numpy matrix of operator, warn if more than 16 qubits to force the user to set massive=True if
        they want such a large matrix. Generally big methods like this should require the use of a converter,
        but in this case a convenience method for quick hacking and access to classical tools is appropriate. """

        if self.num_qubits > 16 and not massive:
            # TODO figure out sparse matrices?
            raise ValueError('to_matrix will return an exponentially large matrix, in this case {0}x{0} elements.'
                             ' Set massive=True if you want to proceed.'.format(2**self.num_qubits))

        # Combination function must be able to handle classical values
        return self.combo_fn([op.to_matrix() for op in self.oplist]) * self.coeff

    def eval(self, front=None, back=None):
        """ A square binary Operator can be defined as a function over two binary strings of equal length. This
        method returns the value of that function for a given pair of binary strings. For more information,
        see the eval method in operator_base.py.

        OpVec's eval recursively evaluates each Operator in self.oplist's eval, and returns a value based on the
        recombination function.


        # TODO this doesn't work for compositions and krons! Needs to be to_matrix.
        """
        # TODO Do we need to use partial(np.sum, axis=0) as OpSum combo to be able to handle vector returns correctly?
        return self.combo_fn([op.eval(front, back) for op in self.oplist]) * self.coeff

    def __str__(self):
        """Overload str() """
        if self.coeff == 1.0:
            return "{}[{}]".format(self.__class__.__name__, ', '.join([str(op) for op in self.oplist]))
        else:
            return "{} * {}[{}]".format(self.coeff, self.__class__.__name__, ', '.join([str(op) for op in self.oplist]))

    def __repr__(self):
        """Overload str() """
        return "{}({}, coeff={})".format(self.__class__.__name__, repr(self.oplist), self.coeff)

    def print_details(self):
        """ print details """
        raise NotImplementedError
