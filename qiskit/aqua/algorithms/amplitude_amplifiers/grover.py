# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Grover's Search algorithm."""

from typing import Optional, Union, Dict, List, Any, Callable
import warnings
import logging
import operator
import numpy as np

from qiskit import ClassicalRegister, QuantumCircuit
from qiskit.circuit.library import GroverOperator
from qiskit.providers import BaseBackend
from qiskit.quantum_info import Statevector

from qiskit.aqua import QuantumInstance, AquaError
from qiskit.aqua.utils import get_subsystem_density_matrix
from qiskit.aqua.utils.validation import validate_min, validate_in_set
from qiskit.aqua.algorithms import QuantumAlgorithm
from qiskit.aqua.components.oracles import Oracle, TruthTableOracle
from qiskit.aqua.components.initial_states import InitialState

logger = logging.getLogger(__name__)


# pylint: disable=invalid-name


class Grover(QuantumAlgorithm):
    r"""Grover's Search algorithm.

    Grover’s Search is a well known quantum algorithm for searching through
    unstructured collections of records for particular targets with quadratic
    speedup compared to classical algorithms.

    Given a set :math:`X` of :math:`N` elements :math:`X=\{x_1,x_2,\ldots,x_N\}`
    and a boolean function :math:`f : X \rightarrow \{0,1\}`, the goal of an
    unstructured-search problem is to find an element :math:`x^* \in X` such
    that :math:`f(x^*)=1`.

    Unstructured search is often alternatively formulated as a database search
    problem, in which, given a database, the goal is to find in it an item that
    meets some specification.

    The search is called *unstructured* because there are no guarantees as to how
    the database is ordered.  On a sorted database, for instance, one could perform
    binary search to find an element in :math:`\mathbb{O}(\log N)` worst-case time.
    Instead, in an unstructured-search problem, there is no prior knowledge about
    the contents of the database. With classical circuits, there is no alternative
    but to perform a linear number of queries to find the target element.
    Conversely, Grover's Search algorithm allows to solve the unstructured-search
    problem on a quantum computer in :math:`\mathcal{O}(\sqrt{N})` queries.

    All that is needed for carrying out a search is an oracle from Aqua's
    :mod:`~qiskit.aqua.components.oracles` module for specifying the search criterion,
    which basically indicates a hit or miss for any given record.  More formally, an
    oracle :math:`O_f` is an object implementing a boolean function
    :math:`f` as specified above.  Given an input :math:`x \in X`,
    :math:`O_f` implements :math:`f(x)`.  The details of how :math:`O_f` works are
    unimportant; Grover's search algorithm treats the oracle as a black box.

    For example the :class:`~qiskit.aqua.components.oracles.LogicalExpressionOracle`
    can take as input a SAT problem in
    `DIMACS CNF format <http://www.satcompetition.org/2009/format-benchmarks2009.html>`__
    and be used with Grover algorithm to find a satisfiable assignment.

    Signature: 

    Q = A S_0 A_dg S_f 

    Should internally use Grover operator to construct Q, then "applying j iterations of Grover"
    only means apply Q j-times where, Q is the grover op)
    """

    def __init__(self,
                 oracle: Union[Oracle, QuantumCircuit, Statevector],
                 state_preparation: Optional[Union[QuantumCircuit, InitialState]] = None,
                 is_good_state: Union[Callable, List[int], Statevector] = None,
                 grover_operator: Optional[QuantumCircuit] = None,
                 incremental: bool = False,
                 num_iterations: int = 1,
                 lam: float = 1.34,
                 rotation_counts: Optional[List[int]] = None,
                 num_solutions: Optional[int] = None,
                 quantum_instance: Optional[Union[QuantumInstance, BaseBackend]] = None,
                 init_state: Optional[InitialState] = None,
                 mct_mode: str = 'noancilla') -> None:
        # pylint: disable=line-too-long
        r"""
        Args:
            oracle: The oracle component
            init_state: An optional initial quantum state. If None (default) then Grover's Search
                 by default uses uniform superposition to initialize its quantum state. However,
                 an initial state may be supplied, if useful, for example, if the user has some
                 prior knowledge regarding where the search target(s) might be located.
            incremental: Whether to use incremental search mode (True) or not (False).
                 Supplied *num_iterations* is ignored when True and instead the search task will
                 be carried out in successive rounds, using circuits built with incrementally
                 higher number of iterations for the repetition of the amplitude amplification
                 until a target is found or the maximal number :math:`\log N` (:math:`N` being the
                 total number of elements in the set from the oracle used) of iterations is
                 reached. The implementation follows Section 4 of [2].
            lam: For incremental search mode, the maximum number of repetition of amplitude
                 amplification increases by factor lam in every round,
                 :math:`R_{i+1} = lam \times R_{i}`. If this parameter is not set, the default
                 value lam = 1.34 is used, which is proved to be optimal [1].
            rotation_counts: For incremental mode, if rotation_counts is defined, parameter *lam*
                is ignored. rotation_counts is the list of integers that defines the number of
                repetition of amplitude amplification for each round.
            num_iterations: How many times the marking and reflection phase sub-circuit is
                repeated to amplify the amplitude(s) of the target(s). Has a minimum value of 1.
            mct_mode: Multi-Control Toffoli mode ('basic' | 'basic-dirty-ancilla' |
                'advanced' | 'noancilla')
            quantum_instance: Quantum Instance or Backend
            grover_operator: A GroverOperator for the Grover's algorithm can be set directly.
            is_good_state: Answers the Grover's algorithm is looking for.
                It is used to check whether the result is correct or not.
            num_solutions: num_solutions: is used to decide num_iterations
            state_preparation: TODO

        Raises:
            TypeError: If ``init_state`` is of unsupported type or is of type ``InitialState` but
                the oracle is not of type ``Oracle``.
            AquaError: evaluate_classically() missing from the input oracle
            TypeError: If ``oracle`` is of unsupported type.


        References:
            [1]: Baritompa et al., Grover's Quantum Algorithm Applied to Global Optimization
                 `<https://www.researchgate.net/publication/220133694_Grover%27s_Quantum_Algorithm_Applied_to_Global_Optimization>`_
            [2]: Boyer et al., Tight bounds on quantum searching
                 `<https://arxiv.org/abs/quant-ph/9605034>`_
        """
        validate_min('num_iterations', num_iterations, 1)
        validate_in_set('mct_mode', mct_mode,
                        {'basic', 'basic-dirty-ancilla',
                         'advanced', 'noancilla'})
        super().__init__(quantum_instance)

        # init_state has been renamed to state_preparation
        if init_state is not None:
            warnings.warn('The init_state argument is deprecated as of 0.8.0, and will be removed '
                          'no earlier than 3 months after the release date. You should use the '
                          'state_preparation argument instead and pass a QuantumCircuit or '
                          'Statevector instead of an InitialState.',
                          DeprecationWarning, stacklevel=2)
            state_preparation = init_state

        if mct_mode is not None:
            warnings.warn('The mct_mode argument is deprecated as of 0.8.0, and will be removed no '
                          'earlier than 3 months after the release date. If you want to use a '
                          'special MCX mode you should use the GroverOperator in '
                          'qiskit.circuit.library directly and pass it to the grover_operator '
                          'keyword argument.', DeprecationWarning, stacklevel=2)

        # Construct GroverOperator circuit
        if grover_operator is not None:
            self._grover_operator = grover_operator
        else:
            # check the type of state_preparation
            if isinstance(state_preparation, InitialState):
                warnings.warn('Passing an InitialState component is deprecated as of 0.8.0, and '
                              'will be removed no earlier than 3 months after the release date. '
                              'You should pass a QuantumCircuit instead.',
                              DeprecationWarning, stacklevel=2)
                if isinstance(oracle, Oracle):
                    state_preparation = init_state.construct_circuit(
                        mode='circuit', register=oracle.variable_register
                        )
                else:
                    raise TypeError('If init_state is of type InitialState, oracle must be of type '
                                    'Oracle')
            elif not isinstance(state_preparation, QuantumCircuit) and state_preparation is not None:
                raise TypeError('Unsupported type "{}" of state_preparation'.format(
                    type(state_preparation)))

            # check to oracle type and if necessary convert the deprecated Oracle component to
            # a circuit
            reflection_qubits = None
            if isinstance(oracle, Oracle):
                if not callable(getattr(oracle, "evaluate_classically", None)):
                    raise AquaError(
                        'Missing the evaluate_classically() method \
                            from the provided oracle instance.'
                    )
                warnings.warn('Passing an qiskit.aqua.components.oracles.Oracle object is '
                              'deprecated as of 0.8.0, and the support will be removed no '
                              'earlier than 3 months after the release date. You should pass a '
                              'QuantumCircuit or Statevector argument instead. See also the '
                              'qiskit.circuit.library.GroverOperator for more information.',
                              DeprecationWarning, stacklevel=2)

                oracle, reflection_qubits, is_good_state = _oracle_component_to_circuit(oracle)
            elif not isinstance(oracle, (QuantumCircuit, Statevector)):
                raise TypeError('Unsupported type "{}" of oracle'.format(type(oracle)))

            self._grover_operator = GroverOperator(oracle=oracle,
                                                   state_preparation=state_preparation,
                                                   reflection_qubits=reflection_qubits,
                                                   mcx_mode=mct_mode)

        self._is_good_state = is_good_state
        self._incremental = incremental
        self._lam = lam
        self._rotation_counts = rotation_counts
        self._max_num_iterations = np.ceil(2 ** (len(self._grover_operator.reflection_qubits) / 2))
        if incremental:
            self._num_iterations = 1
        elif num_solutions:
            self._num_iterations = round(np.pi*np.sqrt(
                2**len(self._grover_operator.reflection_qubits)/num_solutions)/4)
        else:
            self._num_iterations = num_iterations

        if incremental:
            logger.debug('Incremental mode specified, \
                ignoring "num_iterations" and "num_solutions".')
        elif num_solutions:
            logger.debug('"num_solutions" specified, ignoring "num_iterations".')
        elif self._max_num_iterations is not None:
            if num_iterations > self._max_num_iterations:
                logger.warning('The specified value %s for "num_iterations" '
                               'might be too high.', num_iterations)
        self._ret = {}  # type: Dict[str, Any]

    # remove?
    @property
    def qc_amplitude_amplification_iteration(self):
        """ Return GroverOperator """
        return self._grover_operator

    def _run_experiment(self, power):
        """Run a grover experiment for a given power of the Grover operator."""
        if self._quantum_instance.is_statevector:

            qc = self.construct_circuit(power, measurement=False)
            result = self._quantum_instance.execute(qc)
            complete_state_vec = result.get_statevector(qc)
            if qc.width() != len(self._grover_operator.reflection_qubits):
                variable_register_density_matrix = get_subsystem_density_matrix(
                    complete_state_vec,
                    range(len(self._grover_operator.reflection_qubits), qc.width())
                )
                variable_register_density_matrix_diag = np.diag(variable_register_density_matrix)
                max_amplitude = max(
                    variable_register_density_matrix_diag.min(),
                    variable_register_density_matrix_diag.max(),
                    key=abs
                )
                max_amplitude_idx = \
                    np.where(variable_register_density_matrix_diag == max_amplitude)[0][0]
                top_measurement = np.binary_repr(max_amplitude_idx, len(
                    self._grover_operator.reflection_qubits))
            else:
                max_amplitude = max(
                    complete_state_vec.max(),
                    complete_state_vec.min(),
                    key=abs)
                max_amplitude_idx = \
                    np.where(complete_state_vec == max_amplitude)[0][0]
                top_measurement = np.binary_repr(max_amplitude_idx, len(
                    self._grover_operator.reflection_qubits))
        else:
            qc = self.construct_circuit(power, measurement=True)
            measurement = self._quantum_instance.execute(qc).get_counts(qc)
            self._ret['measurement'] = measurement
            top_measurement = max(measurement.items(), key=operator.itemgetter(1))[0]

        self._ret['top_measurement'] = top_measurement

        return top_measurement, self.is_good_state(top_measurement)

    def is_good_state(self, bitstr: str) -> bool:
        """Check whether a provided bitstring is a good state or not.

        Args:
            bitstr: The measurement as bitstring.

        Raises:
            NotImplementedError: If self._is_good_state couldn't be used to determine whether
                the bitstring is a good state.

        Returns:
            True if the measurement is a good state, False otherwise.
        """
        if callable(self._is_good_state):
            oracle_evaluation, _ = self._is_good_state(bitstr)
            return oracle_evaluation
        elif isinstance(self._is_good_state, list):
            return bitstr in self._is_good_state
        elif isinstance(self._is_good_state, Statevector):
            return bitstr in self._is_good_state.probabilities_dict()
        else:
            raise NotImplementedError('Conversion to callable not implemented for {}'.format(
                type(self._is_good_state)))

    def construct_circuit(self, power: int, measurement: bool = False) -> QuantumCircuit:
        """Construct

        Args:
            power: The number of times the Grover operator is repeated.
            measurement: Boolean flag to indicate if measurement should be included in the circuit.

        Returns:
            QuantumCircuit: the QuantumCircuit object for the constructed circuit
        """
        qc = QuantumCircuit(self._grover_operator.num_qubits, name='Grover circuit')
        qc.compose(self._grover_operator.state_preparation, inplace=True)
        if power > 0:
            qc.compose(self._grover_operator.power(power), inplace=True)

        if measurement:
            measurement_cr = ClassicalRegister(
                len(self._grover_operator.reflection_qubits), name='m')
            qc.add_register(measurement_cr)
            qc.measure(self._grover_operator.reflection_qubits, measurement_cr)

        self._ret['circuit'] = qc
        return qc

    def _run(self):
        """Run an entire experiment."""
        if self._incremental:
            if self._rotation_counts:
                for target_num_iterations in self._rotation_counts:
                    assignment, oracle_evaluation = self._run_experiment(target_num_iterations)
                    if oracle_evaluation:
                        break
                    if target_num_iterations > self._max_num_iterations:
                        break
            else:
                current_max_num_iterations = 1
                while current_max_num_iterations < self._max_num_iterations:
                    target_num_iterations = self.random.integers(current_max_num_iterations) + 1
                    assignment, oracle_evaluation = self._run_experiment(target_num_iterations)
                    if oracle_evaluation:
                        break
                    current_max_num_iterations = \
                        min(self._lam * current_max_num_iterations, self._max_num_iterations)

        else:
            assignment, oracle_evaluation = self._run_experiment(self._num_iterations)

        self._ret['result'] = assignment
        self._ret['oracle_evaluation'] = oracle_evaluation
        return self._ret


def _oracle_component_to_circuit(oracle: Oracle):
    """ Convert an Oracle to a QuantumCircuit."""
    circuit = QuantumCircuit(oracle.circuit.num_qubits)

    if isinstance(oracle, TruthTableOracle):
        index = 0
        for qreg in oracle.circuit.qregs:
            if qreg.name == "o":
                break
            index += qreg.size
        _output_register = index
    else:
        _output_register = [i for i, qubit in enumerate(oracle.circuit.qubits)
                            if qubit in oracle.output_register[:]]

    circuit.x(_output_register)
    circuit.h(_output_register)
    circuit.compose(oracle.circuit, list(range(oracle.circuit.num_qubits)),
                    inplace=True)
    circuit.h(_output_register)
    circuit.x(_output_register)

    reflection_qubits = [i for i, qubit in enumerate(oracle.circuit.qubits)
                         if qubit in oracle.variable_register[:]]

    is_good_state = oracle.evaluate_classically

    return circuit, reflection_qubits, is_good_state
