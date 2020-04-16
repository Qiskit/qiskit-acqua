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

""" Test QuadraticObjective """

import unittest
from test.optimization.optimization_test_case import QiskitOptimizationTestCase
import logging
import numpy as np

from qiskit.optimization import QuadraticProgram
from qiskit.optimization.problems.quadratic_objective import ObjSense

logger = logging.getLogger(__name__)


class TestQuadraticObjective(QiskitOptimizationTestCase):
    """Test QuadraticObjective"""

    def test_init(self):
        """ test init. """

        quadratic_program = QuadraticProgram()
        for _ in range(5):
            quadratic_program.continuous_var()

        self.assertEqual(quadratic_program.objective.constant, 0.0)
        self.assertEqual(
            len(quadratic_program.objective.linear.to_dict()), 0)
        self.assertEqual(
            len(quadratic_program.objective.quadratic.to_dict()), 0)
        self.assertEqual(quadratic_program.objective.sense, ObjSense.MINIMIZE)

        constant = 1.0
        linear_coeffs = np.array(range(5))
        quadratic_coeffs = np.array([[i*j for i in range(5)] for j in range(5)])

        quadratic_program.minimize(constant, linear_coeffs, quadratic_coeffs)

        self.assertEqual(quadratic_program.objective.constant, constant)
        self.assertTrue(
            (quadratic_program.objective.linear.to_array() == linear_coeffs).all())
        self.assertTrue(
            (quadratic_program.objective.quadratic.to_array() == quadratic_coeffs)
            .all())
        self.assertEqual(quadratic_program.objective.sense, ObjSense.MINIMIZE)

        quadratic_program.maximize(constant, linear_coeffs, quadratic_coeffs)

        self.assertEqual(quadratic_program.objective.constant, constant)
        self.assertTrue(
            (quadratic_program.objective.linear.to_array() == linear_coeffs).all())
        self.assertTrue(
            (quadratic_program.objective.quadratic.to_array() == quadratic_coeffs)
            .all())
        self.assertEqual(quadratic_program.objective.sense, ObjSense.MAXIMIZE)

        self.assertEqual(quadratic_program.objective.evaluate(linear_coeffs), 931.0)

    def test_setters(self):
        """ test setters. """

        quadratic_program = QuadraticProgram()
        for _ in range(5):
            quadratic_program.continuous_var()

        constant = 1.0
        linear_coeffs = np.array(range(5))
        quadratic_coeffs = np.array([[i*j for i in range(5)] for j in range(5)])

        quadratic_program.objective.constant = constant
        quadratic_program.objective.linear = linear_coeffs
        quadratic_program.objective.quadratic = quadratic_coeffs

        self.assertEqual(quadratic_program.objective.constant, constant)
        self.assertTrue(
            (quadratic_program.objective.linear.to_array() == linear_coeffs).all())
        self.assertTrue(
            (quadratic_program.objective.quadratic.to_array() == quadratic_coeffs)
            .all())

        self.assertEqual(quadratic_program.objective.sense, ObjSense.MINIMIZE)

        quadratic_program.objective.sense = ObjSense.MAXIMIZE
        self.assertEqual(quadratic_program.objective.sense, ObjSense.MAXIMIZE)

        quadratic_program.objective.sense = ObjSense.MINIMIZE
        self.assertEqual(quadratic_program.objective.sense, ObjSense.MINIMIZE)


if __name__ == '__main__':
    unittest.main()
