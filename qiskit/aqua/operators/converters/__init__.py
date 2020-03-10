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

"""
Converters

"""

from .converter_base import ConverterBase
from .pauli_cob import PauliChangeOfBasis
from .pauli_to_instruction import PaulitoInstruction
from .to_matrixop import ToMatrixOp
from .dict_to_circuit_sum import DicttoCircuitSum
from .abelian_grouper import AbelianGrouper

# TODO MatrixToPauliSum
# TODO MatrixToSimInstruction

__all__ = ['ConverterBase',
           'PauliChangeOfBasis',
           'PaulitoInstruction',
           'ToMatrixOp',
           'DicttoCircuitSum',
           'AbelianGrouper']
