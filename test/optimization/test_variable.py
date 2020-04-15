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

"""Test Variable."""

import logging
import unittest

from qiskit.optimization import infinity
from qiskit.optimization.problems import QuadraticProgram, Variable, VarType
from test.optimization.optimization_test_case import QiskitOptimizationTestCase

logger = logging.getLogger(__name__)


class TestVariable(QiskitOptimizationTestCase):
    """Test Variable."""

    def test_init(self):
        """ test init """

        quadratic_program = QuadraticProgram()
        name = 'variable'
        lowerbound = 0
        upperbound = 10
        vartype = VarType.INTEGER

        variable = Variable(quadratic_program, name, lowerbound, upperbound, vartype)

        self.assertEqual(variable.name, name)
        self.assertEqual(variable.lowerbound, lowerbound)
        self.assertEqual(variable.upperbound, upperbound)
        self.assertEqual(variable.vartype, VarType.INTEGER)

    def test_init_default(self):
        """ test init with default values."""

        quadratic_program = QuadraticProgram()
        name = 'variable'

        variable = Variable(quadratic_program, name)

        self.assertEqual(variable.name, name)
        self.assertEqual(variable.lowerbound, 0)
        self.assertEqual(variable.upperbound, infinity)
        self.assertEqual(variable.vartype, VarType.CONTINUOUS)


if __name__ == '__main__':
    unittest.main()
