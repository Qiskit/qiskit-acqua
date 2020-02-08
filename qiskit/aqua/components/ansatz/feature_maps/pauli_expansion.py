# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""
This module contains the definition of a base class for
feature map. Several types of commonly used approaches.
"""

from typing import Optional, Callable, List, Union
import itertools
import logging

import numpy as np
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.quantum_info import Pauli
from qiskit.qasm import pi

from qiskit.aqua.operators import evolution_instruction
from qiskit.aqua.utils.validation import validate_min, validate_in_set
from qiskit.aqua.components.ansatz import Ansatz

from .data_mapping import self_product


logger = logging.getLogger(__name__)

# pylint: disable=invalid-name


class PauliExpansion(Ansatz):
    """
    Mapping data with the second order expansion followed by entangling gates.
    Refer to https://arxiv.org/pdf/1804.11326.pdf for details.
    """

    def __init__(self,
                 feature_dimension: int,
                 paulis: Optional[List[str]] = None,
                 entanglement: Union[str, List[List[int]], callable] = 'full',
                 reps: int = 2,
                 data_map_func: Callable[[np.ndarray], float] = self_product,
                 insert_barriers=False) -> None:
        """Constructor.

        Args:
            feature_dimension: number of features
            depth: the number of repeated circuits. Defaults to 2,
                        has a min. value of 1.
            entangler_map: describe the connectivity of qubits, each list describes
                                        [source, target], or None for full entanglement.
                                        Note that the order is the list is the order of
                                        applying the two-qubit gate.
            entanglement: ['full', 'linear'], generate the qubit
                                          connectivity by predefined topology.
                                          Defaults to full
            paulis: a list of strings for to-be-used paulis.
                                    Defaults to None. If None, ['Z', 'ZZ'] will be used.
            data_map_func: a mapping function for data x
        """
        paulis = paulis if paulis is not None else ['Z', 'ZZ']
        validate_min('reps', reps, 1)
        validate_in_set('entanglement', entanglement, {'full', 'linear'})
        super().__init__(num_qubits=feature_dimension)

        self._pauli_strings = self._build_subset_paulis_string(paulis)
        self._data_map_func = data_map_func

        # define a hadamard layer for convenience
        hadamards = QuantumCircuit(self.num_qubits)
        for i in range(self.num_qubits):
            hadamards.h(i)
        hadamard_layer = hadamards.to_gate()

        # iterate over the layers
        for _ in range(reps):
            self.append(hadamard_layer)
            for pauli in self._pauli_strings:
                coeff = self._data_map_func(self._extract_data_for_rotation(pauli, x))
                p = Pauli.from_label(pauli)
                inst = evolution_instruction([[1, p]], coeff, 1)
                self.append(inst)

    @property
    def feature_dimension(self) -> int:
        """Returns the feature dimension (which is equal to the number of qubits).

        Returns:
            The feature dimension of this feature map.
        """
        return self.num_qubits

    def _build_subset_paulis_string(self, paulis):
        # fill out the paulis to the number of qubits
        temp_paulis = []
        for pauli in paulis:
            len_pauli = len(pauli)
            for possible_pauli_idx in itertools.combinations(range(self._num_qubits), len_pauli):
                string_temp = ['I'] * self._num_qubits
                for idx, _ in enumerate(possible_pauli_idx):
                    string_temp[-possible_pauli_idx[idx] - 1] = pauli[-idx - 1]
                temp_paulis.append(''.join(string_temp))
        # clean up string that can not be entangled.
        final_paulis = []
        for pauli in temp_paulis:
            where_z = np.where(np.asarray(list(pauli[::-1])) != 'I')[0]
            if len(where_z) == 1:
                final_paulis.append(pauli)
            else:
                is_valid = True
                for src, targ in itertools.combinations(where_z, 2):
                    if [src, targ] not in self._entangler_map:
                        is_valid = False
                        break
                if is_valid:
                    final_paulis.append(pauli)
                else:
                    logger.warning("Due to the limited entangler_map, %s is skipped.", pauli)

        logger.info("Pauli terms include: %s", final_paulis)
        return final_paulis

    def _extract_data_for_rotation(self, pauli, x):
        where_non_i = np.where(np.asarray(list(pauli[::-1])) != 'I')[0]
        x = np.asarray(x)
        return x[where_non_i]
