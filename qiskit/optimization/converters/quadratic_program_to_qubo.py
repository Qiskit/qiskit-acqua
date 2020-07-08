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

"""A converter from quadratic program to a QUBO."""

from typing import Optional

from ..algorithms.optimization_algorithm import OptimizationResult
from ..exceptions import QiskitOptimizationError
from ..problems.quadratic_program import QuadraticProgram
from .quadratic_program_converter import QuadraticProgramConverter


class QuadraticProgramToQubo(QuadraticProgramConverter):
    """Convert a given optimization problem to a new problem that is a QUBO.

        Examples:
            >>> from qiskit.optimization.problems import QuadraticProgram
            >>> from qiskit.optimization.converters import QuadraticProgramToQubo
            >>> problem = QuadraticProgram()
            >>> # define a problem
            >>> conv = QuadraticProgramToQubo()
            >>> problem2 = conv.convert(problem)
    """

    def __init__(self, penalty: Optional[float] = None, name: Optional[str] = None) -> None:
        """
        Args:
            penalty: Penalty factor to scale equality constraints that are added to objective.

            name: The name of the converted problem. If not provided, the name of the input
                  problem is used.
        """
        from ..converters.integer_to_binary import IntegerToBinary
        from ..converters.inequality_to_equality import InequalityToEquality
        from ..converters.linear_equality_to_penalty import LinearEqualityToPenalty

        self._int_to_bin = IntegerToBinary()
        self._ineq_to_eq = InequalityToEquality(mode='integer')
        self._penalize_lin_eq_constraints = LinearEqualityToPenalty()
        self._penalty = penalty
        self._dst_name = name

    def convert(self, problem: QuadraticProgram) -> QuadraticProgram:
        """Convert a problem with linear equality constraints into new one with a QUBO form.

        Args:
            problem: The problem with linear equality constraints to be solved.

        Returns:
            The problem converted in QUBO format.

        Raises:
            QiskitOptimizationError: In case of an incompatible problem.
        """

        # analyze compatibility of problem
        msg = self.get_compatibility_msg(problem)
        if len(msg) > 0:
            raise QiskitOptimizationError('Incompatible problem: {}'.format(msg))

        # convert inequality constraints into equality constraints by adding slack variables
        self._ineq_to_eq.name = self._dst_name
        problem_ = self._ineq_to_eq.convert(problem)

        # map integer variables to binary variables
        self._int_to_bin.name = self._dst_name
        problem_ = self._int_to_bin.convert(problem_)

        # penalize linear equality constraints with only binary variables
        if self._penalty is None:
            # TODO: should be derived from problem
            penalty = 1e5
        else:
            penalty = self._penalty
        problem_ = self._penalize_lin_eq_constraints.convert(problem_, penalty_factor=penalty)

        # return QUBO
        return problem_

    def interpret(self, result: OptimizationResult) -> OptimizationResult:
        """ Convert a result of a converted problem into that of the original problem.

            Args:
                result: The result of the converted problem.

            Returns:
                The result of the original problem.
        """
        result_ = self._int_to_bin.interpret(result)
        result_ = self._ineq_to_eq.interpret(result_)
        return result_

    @staticmethod
    def get_compatibility_msg(problem: QuadraticProgram) -> str:
        """Checks whether a given problem can be solved with this optimizer.

        Checks whether the given problem is compatible, i.e., whether the problem can be converted
        to a QUBO, and otherwise, returns a message explaining the incompatibility.

        Args:
            problem: The optimization problem to check compatibility.

        Returns:
            A message describing the incompatibility.
        """

        # initialize message
        msg = ''
        # check whether there are incompatible variable types
        if problem.get_num_continuous_vars() > 0:
            msg += 'Continuous variables are not supported! '

        # check whether there are incompatible constraint types
        if len(problem.quadratic_constraints) > 0:
            msg += 'Quadratic constraints are not supported. '
        # check whether there are float coefficients in constraints
        compatible_with_integer_slack = True
        for l_constraint in problem.linear_constraints:
            linear = l_constraint.linear.to_dict()
            if any(isinstance(coef, float) and not coef.is_integer() for coef in linear.values()):
                compatible_with_integer_slack = False
        for q_constraint in problem.quadratic_constraints:
            linear = q_constraint.linear.to_dict()
            quadratic = q_constraint.quadratic.to_dict()
            if any(
                    isinstance(coef, float) and not coef.is_integer()
                    for coef in quadratic.values()
            ) or any(
                isinstance(coef, float) and not coef.is_integer() for coef in linear.values()
            ):
                compatible_with_integer_slack = False
        if not compatible_with_integer_slack:
            msg += 'Can not convert inequality constraints to equality constraint because \
                    float coefficients are in constraints. '

        # if an error occurred, return error message, otherwise, return None
        return msg

    def is_compatible(self, problem: QuadraticProgram) -> bool:
        """Checks whether a given problem can be solved with the optimizer implementing this method.

        Args:
            problem: The optimization problem to check compatibility.

        Returns:
            Returns True if the problem is compatible, False otherwise.
        """
        return len(self.get_compatibility_msg(problem)) == 0

    @property
    def name(self) -> Optional[str]:
        """Returns the name of the converted problem

        Returns:
            The name of the converted problem
        """
        return self._dst_name

    @name.setter  # type:ignore
    def name(self, name: Optional[str]) -> None:
        """Set a name for a converted problem

        Args:
            name: A name for a converted problem. If not provided, the name of the input
                  problem is used.
        """
        self._dst_name = name
