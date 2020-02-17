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
from ddt import ddt, data, unpack

from qiskit import QuantumCircuit, transpile
from qiskit.circuit import Parameter
from qiskit.circuit.random.utils import random_circuit
from qiskit.extensions.standard import XGate, RXGate, CrxGate
from qiskit.quantum_info import Pauli

from qiskit.aqua.operators import WeightedPauliOperator, MatrixOperator
from qiskit.aqua.components.ansatz import Ansatz, OperatorAnsatz

from test.aqua import QiskitAquaTestCase


@ddt
class TestAnsatz(QiskitAquaTestCase):
    """Tests for the Ansatz class."""

    def setUp(self):
        pass
        super().setUp()

    def assertCircuitEqual(self, a, b, visual=False, verbosity=0, transpiled=True):
        """An equality test specialized to circuits."""
        basis_gates = ['id', 'u1', 'u3', 'cx']
        a_transpiled = transpile(a, basis_gates=basis_gates)
        b_transpiled = transpile(b, basis_gates=basis_gates)

        if verbosity > 0:
            print('-- circuit a:')
            print(a)
            print('-- circuit b:')
            print(b)
            print('-- transpiled circuit a:')
            print(a_transpiled)
            print('-- transpiled circuit b:')
            print(b_transpiled)

        if verbosity > 1:
            print('-- dict:')
            for key in a.__dict__.keys():
                if key == '_data':
                    print(key)
                    print(a.__dict__[key])
                    print(b.__dict__[key])
                else:
                    print(key, a.__dict__[key], b.__dict__[key])

        if transpiled:
            a, b = a_transpiled, b_transpiled

        if visual:
            self.assertEqual(a.draw(), b.draw())
        else:
            self.assertEqual(a, b)

    def test_empty_ansatz(self):
        """Test the creation of an empty Ansatz."""
        ansatz = Ansatz()
        self.assertEqual(ansatz.num_qubits, 0)
        self.assertEqual(ansatz.num_parameters, 0)

        self.assertEqual(ansatz.to_circuit(), QuantumCircuit())

        for attribute in [ansatz._blocks, ansatz._qargs, ansatz._reps]:
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

        self.assertEqual(ansatz.to_circuit(), reference)

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

    def test_parameter_getter_and_setter(self):
        """Test getting and setting of the ansatz parameters."""
        a, b = Parameter('a'), Parameter('b')
        circuit = QuantumCircuit(2)
        circuit.ry(a, 0)
        circuit.crx(b, 0, 1)

        # repeat circuit and check that parameters are duplicated
        reps = 3
        ansatz = Ansatz(circuit, reps=reps)
        expected_params = reps * [a, b]
        self.assertEqual(expected_params, ansatz.params)


class TestBackwardCompatibility(QiskitAquaTestCase):
    """Tests to ensure that the variational forms and feature maps are backwards compatible."""

    def test_varforms(self):
        """Test the variational forms are backwards compatible."""
        self.assertTrue(False)

    def test_featmaps(self):
        """Test the feature maps are backwards compatible."""
        self.assertTrue(False)


class TestRY(QiskitAquaTestCase):
    """Tests for the RY Ansatz."""

    def test_circuit_diagrams(self):
        """Test the resulting circuits via diagrams."""
        self.assertTrue(False)


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
