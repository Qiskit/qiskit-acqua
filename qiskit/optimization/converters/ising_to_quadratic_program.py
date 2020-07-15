# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


"""The converter from a ```Operator``` to ``QuadraticProgram``."""

from typing import Optional, Union
import copy

import numpy as np

from qiskit.aqua.operators import OperatorBase, WeightedPauliOperator, SummedOp, ListOp
from ..problems.quadratic_program import QuadraticProgram
from ..exceptions import QiskitOptimizationError


class IsingToQuadraticProgram:
    """Convert a qubit operator into a quadratic program"""

    def __init__(self, linear: bool = False) -> None:
        r"""

        Args:
            linear: If linear is True, :math:`x^2` is treated as a linear term
                since :math:`x^2 = x` for :math:`x \in \{0,1\}`.
                Else, :math:`x^2` is treat as a quadratic term.
                The default value is False.
        """
        self._qubit_op = None
        self._offset = 0.0
        self._num_qubits = 0
        self._qubo_matrix = None  # type: Optional[np.ndarray]
        self._qp = None  # type: Optional[QuadraticProgram]
        self._linear = linear

    def convert(self,
                qubit_op: Union[OperatorBase, WeightedPauliOperator],
                offset: float = 0.0, name: str = '') -> QuadraticProgram:
        """Convert a qubit operator and a shift value into a quadratic program

        Args:
            qubit_op: The qubit operator to be converted into a
                :class:`~qiskit.optimization.problems.quadratic_program.QuadraticProgram`
            offset: The shift value of the qubit operator
            name: The name of the converted problem.

        Returns:
            QuadraticProgram converted from the input qubit operator and the shift value

        Raises:
            QiskitOptimizationError: If there are Pauli Xs in any Pauli term
            QiskitOptimizationError: If there are more than 2 Pauli Zs in any Pauli term
            NotImplementedError: If the input operator is a ListOp
        """
        # Set properties
        if isinstance(qubit_op, WeightedPauliOperator):
            qubit_op = qubit_op.to_opflow()

        # No support for ListOp yet, this can be added in future
        # pylint: disable=unidiomatic-typecheck
        if isinstance(qubit_op, ListOp):
            raise NotImplementedError(
                'Conversion of a ListOp is not supported, convert each '
                'operator in the ListOp separately.'
            )

        self._qubit_op = qubit_op
        self._offset = copy.deepcopy(offset)
        self._num_qubits = qubit_op.num_qubits

        # Create `QuadraticProgram`
        self._qp = QuadraticProgram(name=name)
        for i in range(self._num_qubits):
            self._qp.binary_var(name='x_{0}'.format(i))
        # Create QUBO matrix
        self._create_qubo_matrix()

        # Initialize dicts for linear terms and quadratic terms
        linear_terms = {}
        quadratic_terms = {}

        # For quadratic pauli terms of operator
        # x_i * x_ j = (1 - Z_i - Z_j + Z_i * Z_j)/4
        for i, row in enumerate(self._qubo_matrix):
            for j, weight in enumerate(row):
                # Focus on the upper triangular matrix
                if j <= i:
                    continue
                # Add a quadratic term to the object function of `QuadraticProgram`
                # The coefficient of the quadratic term in `QuadraticProgram` is
                # 4 * weight of the pauli
                coef = weight * 4
                quadratic_terms[i, j] = coef
                # Sub the weight of the quadratic pauli term from the QUBO matrix
                self._qubo_matrix[i, j] -= weight
                # Sub the weight of the linear pauli term from the QUBO matrix
                self._qubo_matrix[i, i] += weight
                self._qubo_matrix[j, j] += weight
                # Sub the weight from offset
                offset -= weight

        # After processing quadratic pauli terms, only linear paulis are left
        # x_i = (1 - Z_i)/2
        for i in range(self._num_qubits):
            weight = self._qubo_matrix[i, i]
            # Add a linear term to the object function of `QuadraticProgram`
            # The coefficient of the linear term in `QuadraticProgram` is
            # 2 * weight of the pauli
            coef = weight * 2
            if self._linear:
                # If the linear option is True, add it into linear_terms
                linear_terms[i] = -coef
            else:
                # Else, add it into quadratic_terms as a diagonal element.
                quadratic_terms[i, i] = -coef
            # Sub the weight of the linear pauli term from the QUBO matrix
            self._qubo_matrix[i, i] -= weight
            offset += weight

        # Set the objective function
        self._qp.minimize(constant=offset, linear=linear_terms, quadratic=quadratic_terms)

        offset -= offset

        return self._qp

    def _create_qubo_matrix(self):
        """Create a QUBO matrix from the qubit operator

        Raises:
            QiskitOptimizationError: If there are Pauli Xs in any Pauli term
            QiskitOptimizationError: If there are more than 2 Pauli Zs in any Pauli term

        """
        # Set properties
        # The Qubo matrix is an upper triangular matrix.
        # Diagonal elements in the QUBO matrix is for linear terms of the qubit operator
        # The other elements in the QUBO matrix is for quadratic terms of the qubit operator
        self._qubo_matrix = np.zeros((self._num_qubits, self._num_qubits))

        if not isinstance(self._qubit_op, SummedOp):
            oplist = [self._qubit_op.to_pauli_op()]
        else:
            oplist = self._qubit_op.to_pauli_op().oplist

        for pauli_op in oplist:
            pauli = pauli_op.primitive
            coeff = pauli_op.coeff
            # Count the number of Pauli Zs in a Pauli term
            lst_z = pauli.z.tolist()
            z_index = [i for i, z in enumerate(lst_z) if z is True]
            num_z = len(z_index)

            # Add its weight of the Pauli term to the corresponding element of QUBO matrix
            if num_z == 1:
                self._qubo_matrix[z_index[0], z_index[0]] = coeff.real
            elif num_z == 2:
                self._qubo_matrix[z_index[0], z_index[1]] = coeff.real
            else:
                raise QiskitOptimizationError(
                    'There are more than 2 Pauli Zs in the Pauli term {}'.format(pauli.z)
                )

            # If there are Pauli Xs in the Pauli term, raise an error
            lst_x = pauli.x.tolist()
            x_index = [i for i, x in enumerate(lst_x) if x is True]
            if len(x_index) > 0:
                raise QiskitOptimizationError('Pauli Xs exist in the Pauli {}'.format(pauli.x))

    @property
    def linear(self) -> bool:
        r"""
        Returns the conversion mode for quadratic terms

        Returns:
            If it's True :math:`x^2` is treated as a linear term.
            Else, :math:`x^2` is treated as a quadratic term.
        """
        return self._linear

    @linear.setter  # type:ignore
    def linear(self, linear: bool) -> None:
        """Set a conversion mode for quadratic terms

        Args:
            linear: If it's True :math:`x^2` is treated as a linear term.
                Else, :math:`x^2` is treated as a quadratic term.
        """
        self._linear = linear
