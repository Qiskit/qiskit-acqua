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

"""The Grover operator."""

from typing import List, Optional
from qiskit.circuit import QuantumCircuit, QuantumRegister
from .bit_oracle import BitOracle


class GroverOperator(QuantumCircuit):
    """The Grover operator."""

    def __init__(self, oracle: QuantumCircuit,
                 state_in: Optional[QuantumCircuit] = None,
                 zero_reflection: Optional[QuantumCircuit] = None,
                 idle_qubits: Optional[List[int]] = None,
                 insert_barriers: bool = False,
                 mcx: str = 'noancilla',
                 name: str = 'Q') -> None:
        """
        Args:
            oracle: The oracle implementing a reflection about the bad state.
            state_in: The operator preparing the good and bad state. For Grover's algorithm,
                this is a n-qubit Hadamard gate and for Amplitude Amplification or Estimation
                the operator A.
            zero_reflection: The reflection about the zero state.
            idle_qubits: Qubits that are ignored in the reflection about zero.
            insert_barriers: Whether barriers should be inserted between the reflections and A.
            mcx: The mode to use for building the default zero reflection.
            name: The name of the circuit.
        """
        super().__init__(name=name)
        self._oracle = oracle
        self._state_in = state_in
        self._zero_reflection = zero_reflection
        self._idle_qubits = idle_qubits
        self._insert_barriers = insert_barriers
        self._mcx = mcx

        self._build()

    @property
    def num_state_qubits(self):
        """The number of state qubits."""
        if hasattr(self._oracle, 'num_state_qubits'):
            return self._oracle.num_state_qubits
        return self._oracle.num_qubits

    @property
    def num_ancilla_qubits(self) -> int:
        """The number of ancilla qubits.

        Returns:
            The number of ancilla qubits in the circuit.
        """
        max_num_ancillas = 0
        if self._zero_reflection:
            max_num_ancillas = self._zero_reflection.num_ancilla_qubits
        elif self._oracle.num_qubits - len(self.idle_qubits) > 1:
            max_num_ancillas = 1

        if self._state_in and hasattr(self._state_in, 'num_ancilla_qubits'):
            max_num_ancillas = max(max_num_ancillas, self._state_in.num_ancilla_qubits)

        if hasattr(self._state_in, 'num_ancilla_qubits'):
            max_num_ancillas = max(max_num_ancillas, self._oracle.num_ancilla_qubits)

        return max_num_ancillas

    @property
    def idle_qubits(self):
        """Idle qubits, on which S0 is not applied."""
        if self._idle_qubits is None:
            return []
        return self._idle_qubits

    @property
    def num_qubits(self):
        """The number of qubits in the Grover operator."""
        return self.num_state_qubits + self.num_ancilla_qubits

    @property
    def zero_reflection(self) -> QuantumCircuit:
        """The subcircuit implementing the reflection about 0."""
        if self._zero_reflection is not None:
            return self._zero_reflection

        qubits = [i for i in range(self.num_state_qubits) if i not in self.idle_qubits]
        zero_reflection = BitOracle(self.num_state_qubits, qubits, mcx=self._mcx)
        return zero_reflection

    @property
    def state_in(self) -> QuantumCircuit:
        """The subcircuit implementing the A operator or Hadamards."""
        if self._state_in:
            return self._state_in

        qubits = [i for i in range(self.num_state_qubits) if i not in self.idle_qubits]
        hadamards = QuantumCircuit(self.num_state_qubits, name='H')
        hadamards.h(qubits)
        return hadamards

    @property
    def oracle(self):
        """The oracle implementing a reflection about the bad state."""
        return self._oracle

    def _build(self):
        self.qregs = [QuantumRegister(self.num_state_qubits, name='state')]
        if self.num_ancilla_qubits > 0:
            self.qregs += [QuantumRegister(self.num_ancilla_qubits, name='ancilla')]

        _append(self, self.oracle)
        if self._insert_barriers:
            self.barrier()
        _append(self, self.state_in.inverse())
        if self._insert_barriers:
            self.barrier()
        _append(self, self.zero_reflection)
        if self._insert_barriers:
            self.barrier()
        _append(self, self.state_in)


def _append(target, other, qubits=None, ancillas=None):
    if hasattr(other, 'num_state_qubits') and hasattr(other, 'num_ancilla_qubits'):
        num_state_qubits = other.num_state_qubits
        num_ancilla_qubits = other.num_ancilla_qubits
    else:
        num_state_qubits = other.num_qubits
        num_ancilla_qubits = 0

    if qubits is None:
        qubits = list(range(num_state_qubits))
    elif isinstance(qubits, QuantumRegister):
        qubits = qubits[:]

    if num_ancilla_qubits > 0:
        if ancillas is None:
            qubits += list(range(num_state_qubits, num_state_qubits + num_ancilla_qubits))
        else:
            qubits += ancillas[:num_ancilla_qubits]

    target.append(other.to_gate(), qubits)
