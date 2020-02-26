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

"""Tests for Aqua's Ansatz object."""


import unittest
import numpy as np
from ddt import ddt, data

from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Parameter, ParameterVector, ParameterExpression
from qiskit.circuit.random.utils import random_circuit
from qiskit.extensions.standard import XGate, RXGate, CrxGate
from qiskit.quantum_info import Pauli

from qiskit.aqua.operators import WeightedPauliOperator, MatrixOperator
from qiskit.aqua.components.ansatz import Ansatz, OperatorAnsatz, SwapRZ, RY, RYRZ

from test.aqua import QiskitAquaTestCase


@ddt
class TestAnsatz(QiskitAquaTestCase):
    """Tests for the Ansatz class."""

    def setUp(self):
        pass
        super().setUp()

    def assertCircuitEqual(self, qc1, qc2, visual=False, verbosity=0, transpiled=True):
        """An equality test specialized to circuits."""
        basis_gates = ['id', 'u1', 'u3', 'cx']
        qc1_transpiled = transpile(qc1, basis_gates=basis_gates)
        qc2_transpiled = transpile(qc2, basis_gates=basis_gates)

        if verbosity > 0:
            print('-- circuit 1:')
            print(qc1)
            print('-- circuit 2:')
            print(qc2)
            print('-- transpiled circuit 1:')
            print(qc1_transpiled)
            print('-- transpiled circuit 2:')
            print(qc2_transpiled)

        if verbosity > 1:
            print('-- dict:')
            for key in qc1.__dict__.keys():
                if key == '_data':
                    print(key)
                    print(qc1.__dict__[key])
                    print(qc2.__dict__[key])
                else:
                    print(key, qc1.__dict__[key], qc2.__dict__[key])

        if transpiled:
            qc1, qc2 = qc1_transpiled, qc2_transpiled

        if visual:
            self.assertEqual(qc1.draw(), qc2.draw())
        else:
            self.assertEqual(qc1, qc2)

    def test_empty_ansatz(self):
        """Test the creation of an empty Ansatz."""
        ansatz = Ansatz()
        self.assertEqual(ansatz.num_qubits, 0)
        self.assertEqual(ansatz.num_parameters, 0)

        self.assertEqual(ansatz.to_circuit(), QuantumCircuit())

        for attribute in [ansatz._blocks, ansatz._qargs, ansatz._replist]:
            self.assertEqual(len(attribute), 0)

    @data(
        [(XGate(), [0])],
        [(XGate(), [0]), (XGate(), [2])],
        [(RXGate(0.2), [2]), (CrxGate(-0.2), [1, 3])],
    )
    def test_append_gates_to_empty_ansatz(self, gate_data):
        """Test appending gates to an empty ansatz."""
        ansatz = Ansatz()

        max_num_qubits = 0
        for (_, indices) in gate_data:
            max_num_qubits = max(max_num_qubits, max(indices))

        reference = QuantumCircuit(max_num_qubits + 1)
        for (gate, indices) in gate_data:
            ansatz.append(gate, indices)
            reference.append(gate, indices)

        self.assertCircuitEqual(ansatz.to_circuit(), reference, verbosity=0)

    @data(
        [5, 3], [1, 5], [1, 1], [5, 1], [1, 2],
    )
    def test_append_circuit(self, num_qubits):
        """Test appending circuits to an ansatz."""
        # fixed depth of 3 gates per circuit
        depth = 3

        # keep track of a reference circuit
        reference = QuantumCircuit(max(num_qubits))

        # construct the Ansatz from the first circuit
        first_circuit = random_circuit(num_qubits[0], depth)
        # TODO Terra bug: if this is to_gate it fails, since the QC adds an instruction not gate
        ansatz = Ansatz(first_circuit.to_instruction())
        reference.append(first_circuit, list(range(num_qubits[0])))

        # append the rest
        for num in num_qubits[1:]:
            circuit = random_circuit(num, depth)
            ansatz.append(circuit)
            reference.append(circuit, list(range(num)))

        self.assertCircuitEqual(ansatz.to_circuit(), reference)

    @data(
        [5, 3], [1, 5], [1, 1], [5, 1], [1, 2],
    )
    def test_append_ansatz(self, num_qubits):
        """Test appending an ansatz to an ansatz."""
        # fixed depth of 3 gates per circuit
        depth = 3

        # keep track of a reference circuit
        reference = QuantumCircuit(max(num_qubits))

        # construct the Ansatz from the first circuit
        first_circuit = random_circuit(num_qubits[0], depth)
        # TODO Terra bug: if this is to_gate it fails, since the QC adds an instruction not gate
        ansatz = Ansatz(first_circuit.to_instruction())
        reference.append(first_circuit, list(range(num_qubits[0])))

        # append the rest
        for num in num_qubits[1:]:
            circuit = random_circuit(num, depth)
            ansatz.append(Ansatz(circuit))
            reference.append(circuit, list(range(num)))

        self.assertCircuitEqual(ansatz.to_circuit(), reference)

    def test_add_overload(self):
        """Test the overloaded + operator."""
        num_qubits, depth = 2, 2

        # construct two circuits for adding
        first_circuit = random_circuit(num_qubits, depth)
        circuit = random_circuit(num_qubits, depth)

        # get a reference
        reference = first_circuit + circuit

        # convert the appendee to different types
        others = [circuit, circuit.to_instruction(), circuit.to_gate(), Ansatz(circuit)]

        # try adding each type
        for other in others:
            ansatz = Ansatz(first_circuit)
            new_ansatz = ansatz + other
            with self.subTest(msg='type: {}'.format(type(other))):
                self.assertCircuitEqual(new_ansatz.to_circuit(), reference, verbosity=0)

    def test_parameter_getter_from_automatic_repetition(self):
        """Test getting and setting of the ansatz parameters."""
        a, b = Parameter('a'), Parameter('b')
        circuit = QuantumCircuit(2)
        circuit.ry(a, 0)
        circuit.crx(b, 0, 1)

        # repeat circuit and check that parameters are duplicated
        reps = 3
        ansatz = Ansatz(circuit, reps=reps)
        self.assertTrue(len(ansatz.params) == 2 * reps)

    @data(list(range(6)), ParameterVector('θ', length=6))
    def test_parameter_setter_from_automatic_repetition(self, params):
        """Test getting and setting of the ansatz parameters.

        TODO Test the input ``[0, 1, Parameter('θ'), 3, 4, 5]`` once that's supported.
        """
        a, b = Parameter('a'), Parameter('b')
        circuit = QuantumCircuit(2)
        circuit.ry(a, 0)
        circuit.crx(b, 0, 1)

        # repeat circuit and check that parameters are duplicated
        reps = 3
        ansatz = Ansatz(circuit, reps=reps)
        ansatz.params = params

        param_set = set(p for p in params if isinstance(p, ParameterExpression))
        with self.subTest(msg='Test the parameters of the non-transpiled circuit'):
            # check the parameters of the final circuit
            print(ansatz)
            self.assertEqual(ansatz.to_circuit().parameters, param_set)

        with self.subTest(msg='Test the parameters of the transpiled circuit'):
            basis_gates = ['id', 'u1', 'u2', 'u3', 'cx']
            transpiled_circuit = transpile(ansatz.to_circuit(), basis_gates=basis_gates)
            self.assertEqual(transpiled_circuit.parameters, param_set)

    # TODO add as soon as supported by Terra: [0, 1, Parameter('θ'), 3, 4, 5])
    # (the test already supports that structure)
    @data(list(range(6)), ParameterVector('θ', length=6))
    def test_parameters_setter(self, params):
        """Test setting the parameters via list."""
        # construct circuit with some parameters
        initial_params = ParameterVector('p', length=6)
        circuit = QuantumCircuit(1)
        for i, initial_param in enumerate(initial_params):
            circuit.ry(i * initial_param, 0)

        # create an Ansatz from the circuit and set the new parameters
        ansatz = Ansatz(circuit)
        ansatz.params = params

        param_set = set(p for p in params if isinstance(p, ParameterExpression))
        with self.subTest(msg='Test the parameters of the non-transpiled circuit'):
            # check the parameters of the final circuit
            print(ansatz)
            self.assertEqual(ansatz.to_circuit().parameters, param_set)

        with self.subTest(msg='Test the parameters of the transpiled circuit'):
            basis_gates = ['id', 'u1', 'u2', 'u3', 'cx']
            transpiled_circuit = transpile(ansatz.to_circuit(), basis_gates=basis_gates)
            self.assertEqual(transpiled_circuit.parameters, param_set)

    def test_repetetive_parameter_setting(self):
        """Test alternate setting of parameters and circuit construction."""

        p = Parameter('p')
        circuit = QuantumCircuit(1)
        circuit.rx(p, 0)

        ansatz = Ansatz(circuit, reps=[0, 0, 0], insert_barriers=True)
        with self.subTest(msg='immediately after initialization'):
            self.assertEqual(len(ansatz.params), 3)

        with self.subTest(msg='after circuit construction'):
            as_circuit = ansatz.to_circuit()
            self.assertEqual(len(ansatz.params), 3)

        ansatz.params = [0, -1, 0]
        with self.subTest(msg='setting parameter to numbers'):
            as_circuit = ansatz.to_circuit()
            self.assertEqual(ansatz.params, [0, -1, 0])
            self.assertEqual(as_circuit.parameters, set())

        q = Parameter('q')
        ansatz.params = [p, q, q]
        with self.subTest(msg='setting parameter to Parameter objects'):
            as_circuit = ansatz.to_circuit()
            self.assertEqual(ansatz.params, [p, q, q])
            self.assertEqual(as_circuit.parameters, set([p, q]))


class TestBackwardCompatibility(QiskitAquaTestCase):
    """Tests to ensure that the variational forms and feature maps are backwards compatible."""

    @unittest.skip('TODO')
    def test_varforms(self):
        """Test the variational forms are backwards compatible."""
        self.assertTrue(False)  # pylint: disable=redundant-unittest-assert

    @unittest.skip('TODO')
    def test_featmaps(self):
        """Test the feature maps are backwards compatible."""
        self.assertTrue(False)  # pylint: disable=redundant-unittest-assert

    def test_parameter_order(self):
        """Test that the parameter appearance is equal in the old and new variational forms."""
        from qiskit.aqua.components.variational_forms.ry import RY as DeprecatedRY
        num_qubits = 3
        reps = 2

        def varform_params(cls):
            ry = cls(num_qubits, reps)
            params = ParameterVector('_', length=9)
            circuit_params = ry.construct_circuit(params).parameters
            return list(circuit_params)

        self.assertListEqual(varform_params(RY), varform_params(DeprecatedRY))


class TestRY(QiskitAquaTestCase):
    """Tests for the RY Ansatz."""

    def test_circuit_diagrams(self):
        """Test the resulting circuits via diagrams."""
        with self.subTest(msg='Test linear entanglement'):
            ry = RY(3, entanglement='linear', reps=1)
            print(ry)

        with self.subTest(msg='Test barriers'):
            ry = RY(2, reps=1, insert_barriers=True)
            print(ry)


class TestSwapRZ(QiskitAquaTestCase):
    """Tests for the SwapRZ Ansatz."""

    def test_circuit_diagram(self):
        """Test the circuit diagram for SwapRZ."""
        swaprz = SwapRZ(3, insert_barriers=True)
        print(swaprz)


@ddt
class TestOperatorAnsatz(QiskitAquaTestCase):
    """Tests for the operator ansatz."""

    @data(['X'], ['ZXX', 'XYX', 'ZII'])
    def test_from_pauli_operator(self, pauli_labels):
        """Test creation of the operator ansatz from a single weighted pauli operator."""
        paulis = [Pauli.from_label(label) for label in pauli_labels]
        op = WeightedPauliOperator.from_list(paulis)
        ansatz = OperatorAnsatz(op)
        print(ansatz)

    def test_multiple_operators(self):
        """Test creation of the operator ansatz from multiple weighted pauli operators."""
        pauli_labels = ['ZXX', 'XYX', 'ZII']
        ops = [WeightedPauliOperator.from_list([Pauli.from_label(label)]) for label in pauli_labels]
        ansatz = OperatorAnsatz(ops, insert_barriers=True)
        print(ansatz)

    def test_matrix_operator(self):
        """Test the creation of the operator ansatz from a matrix operator."""
        matrix_1 = np.array([[1, 1], [1, -1]]) / np.sqrt(2)
        matrix_2 = np.array([[0, 1], [1, 0]])
        op_1, op_2 = MatrixOperator(matrix_1), MatrixOperator(matrix_2)
        ansatz = OperatorAnsatz([op_1, op_2])
        print(ansatz)


if __name__ == '__main__':
    unittest.main()
