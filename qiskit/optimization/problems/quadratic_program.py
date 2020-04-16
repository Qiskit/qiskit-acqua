# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Quadratic Program."""
import logging
from collections import defaultdict
from enum import Enum
from math import fsum
from typing import List, Union, Dict, Optional, Tuple

from docplex.mp.linear import Var
from docplex.mp.quad import QuadExpr
from docplex.mp.model import Model
from docplex.mp.model_reader import ModelReader
from numpy import ndarray
from scipy.sparse import spmatrix

from qiskit.optimization import infinity, QiskitOptimizationError
from qiskit.optimization.problems.constraint import ConstraintSense
from qiskit.optimization.problems.linear_constraint import LinearConstraint
from qiskit.optimization.problems.linear_expression import LinearExpression
from qiskit.optimization.problems.quadratic_constraint import QuadraticConstraint
from qiskit.optimization.problems.quadratic_expression import QuadraticExpression
from qiskit.optimization.problems.quadratic_objective import QuadraticObjective, ObjSense
from qiskit.optimization.problems.variable import Variable, VarType

logger = logging.getLogger(__name__)


class QuadraticProgram:
    """Representation of a Quadratically Constrained Quadratic Program supporting inequality and
    equality constraints as well as continuous, binary, and integer variables.
    """

    def __init__(self, name: str = '') -> None:
        """Constructs a quadratic program.

        Args:
            name: The name of the quadratic program.
        """
        self._name = name

        self._variables: List[Variable] = []
        self._variables_index: Dict[str, int] = {}

        self._linear_constraints: List[LinearConstraint] = []
        self._linear_constraints_index: Dict[str, int] = {}

        self._quadratic_constraints: List[QuadraticConstraint] = []
        self._quadratic_constraints_index: Dict[str, int] = {}

        self._objective = QuadraticObjective(self)

    def clear(self) -> None:
        """Clears the quadratic program, i.e., deletes all variables, constraints, the
        objective function as well as the name.
        """
        self._name = ''

        self._variables: List[Variable] = []
        self._variables_index: Dict[str, int] = {}

        self._linear_constraints: List[LinearConstraint] = []
        self._linear_constraints_index: Dict[str, int] = {}

        self._quadratic_constraints: List[QuadraticConstraint] = []
        self._quadratic_constraints_index: Dict[str, int] = {}

        self._objective = QuadraticObjective(self)

    @property
    def name(self) -> str:
        """Returns the name of the quadratic program.

        Returns:
            The name of the quadratic program.
        """
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        """Sets the name of the quadratic program.

        Args:
            name: The name of the quadratic program.
        """
        self._name = name

    @property
    def variables(self) -> List[Variable]:
        """Returns the list of variables of the quadratic program.

        Returns:
            List of variables.
        """
        return self._variables

    @property
    def variables_index(self) -> Dict[str, int]:
        """Returns the dictionary that maps the name of a variable to its index.

        Returns:
            The variable index dictionary.
        """
        return self._variables_index

    def _add_variable(self, name: Optional[str] = None, lowerbound: float = 0,
                      upperbound: float = infinity,
                      vartype: VarType = VarType.CONTINUOUS) -> Variable:
        """Checks whether a variable name is already taken and adds the variable to list and index
        if not.

        Args:
            name: The name of the variable.
            lowerbound: The lowerbound of the variable.
            upperbound: The upperbound of the variable.
            vartype: The type of the variable.

        Returns:
            The added variable.

        Raises:
            QiskitOptimizationError: if the variable name is already taken.

        """
        if name:
            if name in self._variables_index:
                raise QiskitOptimizationError("Variable name already exists: {}".format(name))
        else:
            k = self.get_num_vars()
            while 'x{}'.format(k) in self._variables_index:
                k += 1
            name = 'x{}'.format(k)
        self.variables_index[name] = len(self.variables)
        variable = Variable(self, name, lowerbound, upperbound, vartype)
        self.variables.append(variable)
        return variable

    def continuous_var(self, name: Optional[str] = None, lowerbound: float = 0,
                       upperbound: float = infinity) -> Variable:
        """Adds a continuous variable to the quadratic program.

        Args:
            name: The name of the variable.
            lowerbound: The lowerbound of the variable.
            upperbound: The upperbound of the variable.

        Returns:
            The added variable.

        Raises:
            QiskitOptimizationError: if the variable name is already occupied.
        """
        return self._add_variable(name, lowerbound, upperbound, VarType.CONTINUOUS)

    def binary_var(self, name: Optional[str] = None) -> Variable:
        """Adds a binary variable to the quadratic program.

        Args:
            name: The name of the variable.

        Returns:
            The added variable.

        Raises:
            QiskitOptimizationError: if the variable name is already occupied.
        """
        return self._add_variable(name, 0, 1, VarType.BINARY)

    def integer_var(self, name: Optional[str] = None, lowerbound: float = 0,
                    upperbound: float = infinity) -> Variable:
        """Adds an integer variable to the quadratic program.

        Args:
            name: The name of the variable.
            lowerbound: The lowerbound of the variable.
            upperbound: The upperbound of the variable.

        Returns:
            The added variable.

        Raises:
            QiskitOptimizationError: if the variable name is already occupied.
        """
        return self._add_variable(name, lowerbound, upperbound, VarType.INTEGER)

    def get_variable(self, i: Union[int, str]) -> Variable:
        """Returns a variable for a given name or index.

        Args:
            i: the index or name of the variable.

        Returns:
            The corresponding variable.
        """
        if isinstance(i, int):
            return self.variables[i]
        else:
            return self.variables[self._variables_index[i]]

    def get_num_vars(self, vartype: Optional[VarType] = None) -> int:
        """Returns the total number of variables or the number of variables of the specified type.

        Args:
            vartype: The type to be filtered on. All variables are counted if None.

        Returns:
            The total number of variables.
        """
        if vartype:
            return sum(variable.vartype == vartype for variable in self.variables)
        else:
            return len(self.variables)

    def get_num_continuous_vars(self) -> int:
        """Returns the total number of continuous variables.

        Returns:
            The total number of continuous variables.
        """
        return self.get_num_vars(VarType.CONTINUOUS)

    def get_num_binary_vars(self) -> int:
        """Returns the total number of binary variables.

        Returns:
            The total number of binary variables.
        """
        return self.get_num_vars(VarType.BINARY)

    def get_num_integer_vars(self) -> int:
        """Returns the total number of integer variables.

        Returns:
            The total number of integer variables.
        """
        return self.get_num_vars(VarType.INTEGER)

    @property
    def linear_constraints(self) -> List[LinearConstraint]:
        """Returns the list of linear constraints of the quadratic program.

        Returns:
            List of linear constraints.
        """
        return self._linear_constraints

    @property
    def linear_constraints_index(self) -> Dict[str, int]:
        """Returns the dictionary that maps the name of a linear constraint to its index.

        Returns:
            The linear constraint index dictionary.
        """
        return self._linear_constraints_index

    def linear_constraint(self,
                          linear: Union[ndarray, spmatrix, List[float],
                                        Dict[Union[int, str], float]] = None,
                          sense: Union[str, ConstraintSense] = '<=',
                          rhs: float = 0.0, name: Optional[str] = None) -> LinearConstraint:
        """Adds a linear equality constraint to the quadratic program of the form:
            linear * x sense rhs.

        Args:
            name: The name of the constraint.
            linear: The linear coefficients of the left-hand-side of the constraint.
            sense: The sense of the constraint,
              - '==', '=', 'E', and 'EQ' denote 'equal to'.
              - '>=', '>', 'G', and 'GE' denote 'greater-than-or-equal-to'.
              - '<=', '<', 'L', and 'LE' denote 'less-than-or-equal-to'.
            rhs: The right hand side of the constraint.

        Returns:
            The added constraint.

        Raises:
            QiskitOptimizationError: if the constraint name already exists or the sense is not
                valid.
        """
        if name:
            if name in self.linear_constraints_index:
                raise QiskitOptimizationError(
                    "Linear constraint's name already exists: {}".format(name))
        else:
            k = self.get_num_linear_constraints()
            while 'c{}'.format(k) in self.linear_constraints_index:
                k += 1
            name = 'c{}'.format(k)
        self.linear_constraints_index[name] = len(self.linear_constraints)
        if linear is None:
            linear = {}
        constraint = LinearConstraint(self, name, linear, ConstraintSense.convert(sense), rhs)
        self.linear_constraints.append(constraint)
        return constraint

    def get_linear_constraint(self, i: Union[int, str]) -> LinearConstraint:
        """Returns a linear constraint for a given name or index.

        Args:
            i: the index or name of the constraint.

        Returns:
            The corresponding constraint.
        """
        if isinstance(i, int):
            return self.linear_constraints[i]
        else:
            return self.linear_constraints[self._linear_constraints_index[i]]

    def get_num_linear_constraints(self) -> int:
        """Returns the number of linear constraints.

        Returns:
            The number of linear constraints.
        """
        return len(self.linear_constraints)

    @property
    def quadratic_constraints(self) -> List[QuadraticConstraint]:
        """Returns the list of quadratic constraints of the quadratic program.

        Returns:
            List of quadratic constraints.
        """
        return self._quadratic_constraints

    @property
    def quadratic_constraints_index(self) -> Dict[str, int]:
        """Returns the dictionary that maps the name of a quadratic constraint to its index.

        Returns:
            The quadratic constraint index dictionary.
        """
        return self._quadratic_constraints_index

    def quadratic_constraint(self,
                             linear: Union[ndarray, spmatrix, List[float],
                                           Dict[Union[int, str], float]] = None,
                             quadratic: Union[ndarray, spmatrix,
                                              List[List[float]],
                                              Dict[
                                                  Tuple[Union[int, str],
                                                        Union[int, str]],
                                                  float]] = None,
                             sense: Union[str, ConstraintSense] = '<=',
                             rhs: float = 0.0, name: Optional[str] = None) -> QuadraticConstraint:
        """Adds a quadratic equality constraint to the quadratic program of the form:
            x * Q * x <= rhs.

        Args:
            name: The name of the constraint.
            linear: The linear coefficients of the constraint.
            quadratic: The quadratic coefficients of the constraint.
            sense: The sense of the constraint,
              - '==', '=', 'E', and 'EQ' denote 'equal to'.
              - '>=', '>', 'G', and 'GE' denote 'greater-than-or-equal-to'.
              - '<=', '<', 'L', and 'LE' denote 'less-than-or-equal-to'.
            rhs: The right hand side of the constraint.

        Returns:
            The added constraint.

        Raises:
            QiskitOptimizationError: if the constraint name already exists.
        """
        if name:
            if name in self.quadratic_constraints_index:
                raise QiskitOptimizationError(
                    "Quadratic constraint name already exists: {}".format(name))
        else:
            k = self.get_num_quadratic_constraints()
            while 'q{}'.format(k) in self.quadratic_constraints_index:
                k += 1
            name = 'q{}'.format(k)
        self.quadratic_constraints_index[name] = len(self.quadratic_constraints)
        if linear is None:
            linear = {}
        if quadratic is None:
            quadratic = {}
        constraint = QuadraticConstraint(self, name, linear, quadratic,
                                         ConstraintSense.convert(sense), rhs)
        self.quadratic_constraints.append(constraint)
        return constraint

    def get_quadratic_constraint(self, i: Union[int, str]) -> QuadraticConstraint:
        """Returns a quadratic constraint for a given name or index.

        Args:
            i: the index or name of the constraint.

        Returns:
            The corresponding constraint.
        """
        if isinstance(i, int):
            return self.quadratic_constraints[i]
        else:
            return self.quadratic_constraints[self._quadratic_constraints_index[i]]

    def get_num_quadratic_constraints(self) -> int:
        """Returns the number of quadratic constraints.

        Returns:
            The number of quadratic constraints.
        """
        return len(self.quadratic_constraints)

    @property
    def objective(self) -> QuadraticObjective:
        """Returns the quadratic objective.

        Returns:
            The quadratic objective.
        """
        return self._objective

    def minimize(self,
                 constant: float = 0.0,
                 linear: Union[ndarray, spmatrix, List[float], Dict[Union[str, int], float]] = None,
                 quadratic: Union[ndarray, spmatrix, List[List[float]],
                                  Dict[Tuple[Union[int, str], Union[int, str]], float]] = None
                 ) -> None:
        """Sets a quadratic objective to be minimized.

        Args:
            constant: the constant offset of the objective.
            linear: the coefficients of the linear part of the objective.
            quadratic: the coefficients of the quadratic part of the objective.

        Returns:
            The created quadratic objective.
        """
        self._objective = QuadraticObjective(self, constant, linear, quadratic, ObjSense.MINIMIZE)

    def maximize(self,
                 constant: float = 0.0,
                 linear: Union[ndarray, spmatrix, List[float], Dict[Union[str, int], float]] = None,
                 quadratic: Union[ndarray, spmatrix, List[List[float]],
                                  Dict[Tuple[Union[int, str], Union[int, str]], float]] = None
                 ) -> None:
        """Sets a quadratic objective to be maximized.

        Args:
            constant: the constant offset of the objective.
            linear: the coefficients of the linear part of the objective.
            quadratic: the coefficients of the quadratic part of the objective.

        Returns:
            The created quadratic objective.
        """
        self._objective = QuadraticObjective(self, constant, linear, quadratic, ObjSense.MAXIMIZE)

    def from_docplex(self, model: Model) -> None:
        """Loads this quadratic program from a docplex model

        Args:
            model: The docplex model to be loaded.

        Raises:
            QiskitOptimizationError: if the model contains unsupported elements.
        """

        # clear current problem
        self.clear()

        # get name
        self.name = model.name

        # get variables
        # keep track of names separately, since docplex allows to have None names.
        var_names = {}
        for x in model.iter_variables():
            if x.get_vartype().one_letter_symbol() == 'C':
                x_new = self.continuous_var(x.name, x.lb, x.ub)
                var_names[x] = x_new.name
            elif x.get_vartype().one_letter_symbol() == 'B':
                x_new = self.binary_var(x.name)
                var_names[x] = x_new.name
            elif x.get_vartype().one_letter_symbol() == 'I':
                x_new = self.integer_var(x.name, x.lb, x.ub)
                var_names[x] = x_new.name
            else:
                raise QiskitOptimizationError("Unsupported variable type!")

        # objective sense
        minimize = model.objective_sense.is_minimize()

        # make sure objective expression is linear or quadratic and not a variable
        if isinstance(model.objective_expr, Var):
            model.objective_expr = model.objective_expr + 0

        # get objective offset
        constant = model.objective_expr.constant

        # get linear part of objective
        linear = {}
        linear_part = model.objective_expr.get_linear_part()
        for x in linear_part.iter_variables():
            linear[var_names[x]] = linear_part.get_coef(x)

        # get quadratic part of objective
        quadratic = {}
        if isinstance(model.objective_expr, QuadExpr):
            for quad_triplet in model.objective_expr.generate_quad_triplets():
                i = var_names[quad_triplet[0]]
                j = var_names[quad_triplet[1]]
                v = quad_triplet[2]
                quadratic[i, j] = v

        # set objective
        if minimize:
            self.minimize(constant, linear, quadratic)
        else:
            self.maximize(constant, linear, quadratic)

        # get linear constraints
        for i in range(model.number_of_linear_constraints):
            constraint = model.get_constraint_by_index(i)
            name = constraint.name
            sense = constraint.sense

            rhs = 0
            if not isinstance(constraint.lhs, Var):
                rhs -= constraint.lhs.constant
            if not isinstance(constraint.rhs, Var):
                rhs += constraint.rhs.constant

            lhs = {}
            for x in constraint.iter_net_linear_coefs():
                lhs[x[0].name] = x[1]

            if sense == sense.EQ:
                self.linear_constraint(lhs, '==', rhs, name)
            elif sense == sense.GE:
                self.linear_constraint(lhs, '>=', rhs, name)
            elif sense == sense.LE:
                self.linear_constraint(lhs, '<=', rhs, name)
            else:
                raise QiskitOptimizationError("Unsupported constraint sense!")

        # get quadratic constraints
        for i in range(model.number_of_quadratic_constraints):
            constraint = model.get_quadratic_by_index(i)
            name = constraint.name
            sense = constraint.sense

            left_expr = constraint.get_left_expr()
            right_expr = constraint.get_right_expr()

            rhs = right_expr.constant - left_expr.constant
            linear = {}
            quadratic = {}

            if left_expr.is_quad_expr():
                for x in left_expr.linear_part.iter_variables():
                    linear[var_names[x]] = left_expr.linear_part.get_coef(x)
                for quad_triplet in left_expr.iter_quad_triplets():
                    i = var_names[quad_triplet[0]]
                    j = var_names[quad_triplet[1]]
                    v = quad_triplet[2]
                    quadratic[i, j] = v
            else:
                for x in left_expr.iter_variables():
                    linear[var_names[x]] = left_expr.get_coef(x)

            if right_expr.is_quad_expr():
                for x in right_expr.linear_part.iter_variables():
                    linear[var_names[x]] = linear.get(var_names[x], 0.0) - \
                        right_expr.linear_part.get_coef(x)
                for quad_triplet in right_expr.iter_quad_triplets():
                    i = var_names[quad_triplet[0]]
                    j = var_names[quad_triplet[1]]
                    v = quad_triplet[2]
                    quadratic[i, j] = quadratic.get((i, j), 0.0) - v
            else:
                for x in right_expr.iter_variables():
                    linear[var_names[x]] = linear.get(var_names[x], 0.0) - right_expr.get_coef(x)

            if sense == sense.EQ:
                self.quadratic_constraint(linear, quadratic, '==', rhs, name)
            elif sense == sense.GE:
                self.quadratic_constraint(linear, quadratic, '>=', rhs, name)
            elif sense == sense.LE:
                self.quadratic_constraint(linear, quadratic, '<=', rhs, name)
            else:
                raise QiskitOptimizationError("Unsupported constraint sense!")

    def to_docplex(self) -> Model:
        """Returns a docplex model corresponding to this quadratic program.

        Returns:
            The docplex model corresponding to this quadratic program.

        Raises:
            QiskitOptimizationError: if non-supported elements (should never happen).
        """

        # initialize model
        mdl = Model(self.name)

        # add variables
        var = {}
        for i, x in enumerate(self.variables):
            if x.vartype == VarType.CONTINUOUS:
                var[i] = mdl.continuous_var(lb=x.lowerbound, ub=x.upperbound, name=x.name)
            elif x.vartype == VarType.BINARY:
                var[i] = mdl.binary_var(name=x.name)
            elif x.vartype == VarType.INTEGER:
                var[i] = mdl.integer_var(lb=x.lowerbound, ub=x.upperbound, name=x.name)
            else:
                # should never happen
                raise QiskitOptimizationError('Unknown variable type: %s!' % x.vartype)

        # add objective
        objective = self.objective.constant
        for i, v in self.objective.linear.to_dict().items():
            objective += v * var[i]
        for (i, j), v in self.objective.quadratic.to_dict().items():
            objective += v * var[i] * var[j]
        if self.objective.sense == ObjSense.MINIMIZE:
            mdl.minimize(objective)
        else:
            mdl.maximize(objective)

        # add linear constraints
        for i, constraint in enumerate(self.linear_constraints):
            name = constraint.name
            rhs = constraint.rhs
            linear_expr = 0
            for j, v in constraint.linear.to_dict().items():
                linear_expr += v * var[j]
            sense = constraint.sense
            if sense == ConstraintSense.EQ:
                mdl.add_constraint(linear_expr == rhs, ctname=name)
            elif sense == ConstraintSense.GE:
                mdl.add_constraint(linear_expr >= rhs, ctname=name)
            elif sense == ConstraintSense.LE:
                mdl.add_constraint(linear_expr <= rhs, ctname=name)
            else:
                # should never happen
                raise QiskitOptimizationError('Unknown sense: %s!' % sense)

        # add quadratic constraints
        for i, constraint in enumerate(self.quadratic_constraints):
            name = constraint.name
            rhs = constraint.rhs
            quadratic_expr = 0
            for j, v in constraint.linear.to_dict().items():
                quadratic_expr += v * var[j]
            for (j, k), v in constraint.quadratic.to_dict().items():
                quadratic_expr += v * var[j] * var[k]
            sense = constraint.sense
            if sense == ConstraintSense.EQ:
                mdl.add_constraint(quadratic_expr == rhs, ctname=name)
            elif sense == ConstraintSense.GE:
                mdl.add_constraint(quadratic_expr >= rhs, ctname=name)
            elif sense == ConstraintSense.LE:
                mdl.add_constraint(quadratic_expr <= rhs, ctname=name)
            else:
                # should never happen
                raise QiskitOptimizationError('Unknown sense: %s!' % sense)

        return mdl

    def pprint_as_string(self) -> str:
        """Pretty prints the quadratic program as a string.

        Returns:
            A string representing the quadratic program.
        """
        return self.to_docplex().pprint_as_string()

    def prettyprint(self, out: Optional[str] = None) -> None:
        """Pretty prints the quadratic program to a given output stream (None = default).

        Args:
            out: The output stream or file name to print to.
              if you specify a file name, the output file name is has '.mod' as suffix.
        """
        self.to_docplex().prettyprint(out)

    def print_as_lp_string(self) -> str:
        """Prints the quadratic program as a string of LP format.

        Returns:
            A string representing the quadratic program.
        """
        return self.to_docplex().export_as_lp_string()

    def read_from_lp_file(self, filename: str) -> None:
        """Loads the quadratic program from a LP file.

        Args:
            filename: The filename of the file to be loaded.
        """
        model_reader = ModelReader()
        model = model_reader.read(filename)
        self.from_docplex(model)

    def write_to_lp_file(self, filename: str) -> None:
        """Writes the quadratic program to an LP file.

        Args:
            filename: The filename of the file the model is written to.
        """
        self.to_docplex().export_as_lp(filename)

    def substitute_variables(
            self, constants: Optional[Dict[Union[str, int], float]] = None,
            variables: Optional[Dict[Union[str, int], Tuple[Union[str, int], float]]] = None) \
            -> Tuple['QuadraticProgram', 'SubstitutionStatus']:
        """Substitutes variables with constants or other variables.

        Args:
            constants: replace variable by constant
                e.g., {'x': 2} means 'x' is substituted with 2

            variables: replace variables by weighted other variable
                need to copy everything using name reference to make sure that indices are matched
                correctly. The lower and upper bounds are updated accordingly.
                e.g., {'x': ('y', 2)} means 'x' is substituted with 'y' * 2

        Returns:
            An optimization problem by substituting variables and the status.
            If the resulting problem has no issue, the status is `success`.
            Otherwise, an empty problem and status `infeasible` are returned.

        Raises:
            QiskitOptimizationError: if the substitution is invalid as follows.
                - Same variable is substituted multiple times.
                - Coefficient of variable substitution is zero.
        """
        return SubstituteVariables().substitute_variables(self, constants, variables)


class SubstitutionStatus(Enum):
    """Status of `QuadraticProgram.substitute_variables`"""
    success = 1
    infeasible = 2


class SubstituteVariables:
    """A class to substitute variables of an optimization problem with constants for other
    variables"""

    CONST = '__CONSTANT__'

    def __init__(self):
        self._src: Optional[QuadraticProgram] = None
        self._dst: Optional[QuadraticProgram] = None
        self._subs = {}

    def substitute_variables(
            self, src: QuadraticProgram,
            constants: Optional[Dict[Union[str, int], float]] = None,
            variables: Optional[Dict[Union[str, int], Tuple[Union[str, int], float]]] = None) \
            -> Tuple[QuadraticProgram, SubstitutionStatus]:
        """Substitutes variables with constants or other variables.

        Args:
            src: a quadratic program to be substituted.

            constants: replace variable by constant
                e.g., {'x': 2} means 'x' is substituted with 2

            variables: replace variables by weighted other variable
                need to copy everything using name reference to make sure that indices are matched
                correctly. The lower and upper bounds are updated accordingly.
                e.g., {'x': ('y', 2)} means 'x' is substituted with 'y' * 2

        Returns:
            An optimization problem by substituting variables and the status.
            If the resulting problem has no issue, the status is `success`.
            Otherwise, an empty problem and status `infeasible` are returned.

        Raises:
            QiskitOptimizationError: if the substitution is invalid as follows.
                - Same variable is substituted multiple times.
                - Coefficient of variable substitution is zero.
        """
        self._src = src
        self._dst = QuadraticProgram(src.name)
        self._subs_dict(constants, variables)
        results = [
            self._variables(),
            self._objective(),
            self._linear_constraints(),
            self._quadratic_constraints(),
        ]
        if any(r == SubstitutionStatus.infeasible for r in results):
            ret = SubstitutionStatus.infeasible
        else:
            ret = SubstitutionStatus.success
        return self._dst, ret

    @staticmethod
    def _feasible(sense: ConstraintSense, rhs: float) -> bool:
        """Checks feasibility of the following condition
            0 `sense` rhs
        """
        # I use the following pylint option because `rhs` should come to right
        # pylint: disable=misplaced-comparison-constant
        if sense == ConstraintSense.EQ:
            if 0 == rhs:
                return True
        elif sense == ConstraintSense.LE:
            if 0 <= rhs:
                return True
        elif sense == ConstraintSense.GE:
            if 0 >= rhs:
                return True
        return False

    @staticmethod
    def _replace_dict_keys_with_names(op, dic):
        key = []
        val = []
        for k in sorted(dic.keys()):
            key.append(op.variables.get_names(k))
            val.append(dic[k])
        return key, val

    def _subs_dict(self, constants, variables):
        # guarantee that there is no overlap between variables to be replaced and combine input
        subs: Dict[str, Tuple[str, float]] = {}
        if constants is not None:
            for i, v in constants.items():
                # substitute i <- v
                i_2 = self._src.get_variable(i).name
                if i_2 in subs:
                    raise QiskitOptimizationError(
                        'Cannot substitute the same variable twice: {} <- {}'.format(i, v))
                subs[i_2] = (self.CONST, v)

        if variables is not None:
            for i, (j, v) in variables.items():
                if v == 0:
                    raise QiskitOptimizationError(
                        'coefficient must be non-zero: {} {} {}'.format(i, j, v))
                # substitute i <- j * v
                i_2 = self._src.get_variable(i).name
                j_2 = self._src.get_variable(j).name
                if i_2 == j_2:
                    raise QiskitOptimizationError(
                        'Cannot substitute the same variable: {} <- {} {}'.format(i, j, v))
                if i_2 in subs:
                    raise QiskitOptimizationError(
                        'Cannot substitute the same variable twice: {} <- {} {}'.format(i, j, v))
                if j_2 in subs:
                    raise QiskitOptimizationError(
                        'Cannot substitute by variable that gets substituted itself: '
                        '{} <- {} {}'.format(i, j, v))
                subs[i_2] = (j_2, v)

        self._subs = subs

    def _variables(self) -> SubstitutionStatus:
        # copy variables that are not replaced
        for var in self._src.variables:
            name = var.name
            vartype = var.vartype
            lowerbound = var.lowerbound
            upperbound = var.upperbound
            if name not in self._subs:
                self._dst._add_variable(name, lowerbound, upperbound, vartype)

        for i, (j, v) in self._subs.items():
            lb_i = self._src.get_variable(i).lowerbound
            ub_i = self._src.get_variable(i).upperbound
            if j == self.CONST:
                if not lb_i <= v <= ub_i:
                    logger.warning(
                        'Infeasible substitution for variable: %s', i)
                    return SubstitutionStatus.infeasible
            else:
                # substitute i <- j * v
                # lb_i <= i <= ub_i  -->  lb_i / v <= j <= ub_i / v if v > 0
                #                         ub_i / v <= j <= lb_i / v if v < 0
                if v == 0:
                    raise QiskitOptimizationError(
                        'Coefficient of variable substitution should be nonzero: '
                        '{} {} {}'.format(i, j, v))
                if abs(lb_i) < infinity:
                    new_lb_i = lb_i / v
                else:
                    new_lb_i = lb_i if v > 0 else -lb_i
                if abs(ub_i) < infinity:
                    new_ub_i = ub_i / v
                else:
                    new_ub_i = ub_i if v > 0 else -ub_i
                var_j = self._dst.get_variable(j)
                lb_j = var_j.lowerbound
                ub_j = var_j.upperbound
                if v > 0:
                    var_j.lowerbound = max(lb_j, new_lb_i)
                    var_j.upperbound = min(ub_j, new_ub_i)
                else:
                    var_j.lowerbound = max(lb_j, new_ub_i)
                    var_j.upperbound = min(ub_j, new_lb_i)

        for var in self._dst.variables:
            if var.lowerbound > var.upperbound:
                logger.warning(
                    'Infeasible lower and upper bound: %s %f %f', var, var.lowerbound,
                    var.upperbound)
                return SubstitutionStatus.infeasible

        return SubstitutionStatus.success

    def _linear_expression(self, lin_expr: LinearExpression) \
            -> Tuple[List[float], LinearExpression]:
        const = []
        lin_dict = defaultdict(float)
        for i, w_i in lin_expr.to_dict(use_name=True).items():
            repl_i = self._subs[i] if i in self._subs else (i, 1)
            prod = w_i * repl_i[1]
            if repl_i[0] == self.CONST:
                const.append(prod)
            else:
                k = repl_i[0]
                lin_dict[k] += prod
        new_lin = LinearExpression(quadratic_program=self._dst,
                                   coefficients=lin_dict if lin_dict else {})
        return const, new_lin

    def _quadratic_expression(self, quad_expr: QuadraticExpression) \
            -> Tuple[List[float], Optional[LinearExpression], Optional[QuadraticExpression]]:
        const = []
        lin_dict = defaultdict(float)
        quad_dict = defaultdict(float)
        for (i, j), w_ij in quad_expr.to_dict(use_name=True).items():
            repl_i = self._subs[i] if i in self._subs else (i, 1)
            repl_j = self._subs[j] if j in self._subs else (j, 1)
            idx = tuple(x for x, _ in [repl_i, repl_j] if x != self.CONST)
            prod = w_ij * repl_i[1] * repl_j[1]
            if len(idx) == 2:
                quad_dict[idx] += prod
            elif len(idx) == 1:
                lin_dict[idx[0]] += prod
            else:
                const.append(prod)
        new_lin = LinearExpression(quadratic_program=self._dst,
                                   coefficients=lin_dict if lin_dict else {})
        new_quad = QuadraticExpression(quadratic_program=self._dst,
                                       coefficients=quad_dict if quad_dict else {})
        return const, new_lin, new_quad

    def _objective(self) -> SubstitutionStatus:
        obj = self._src.objective
        const1, lin1 = self._linear_expression(obj.linear)
        const2, lin2, quadratic = self._quadratic_expression(obj.quadratic)

        constant = fsum([obj.constant] + const1 + const2)
        linear = lin1.coefficients + lin2.coefficients
        if obj.sense == obj.sense.MINIMIZE:
            self._dst.minimize(constant=constant, linear=linear, quadratic=quadratic.coefficients)
        else:
            self._dst.maximize(constant=constant, linear=linear, quadratic=quadratic.coefficients)
        return SubstitutionStatus.success

    def _linear_constraints(self) -> SubstitutionStatus:
        for lin_cst in self._src.linear_constraints:
            constant, linear = self._linear_expression(lin_cst.linear)
            rhs = -fsum([-lin_cst.rhs] + constant)
            if linear.coefficients.nnz > 0:
                self._dst.linear_constraint(name=lin_cst.name, linear=linear.coefficients,
                                            sense=lin_cst.sense, rhs=rhs)
            else:
                if not self._feasible(lin_cst.sense, rhs):
                    logger.warning('constraint %s is infeasible due to substitution', lin_cst.name)
                    return SubstitutionStatus.infeasible

        return SubstitutionStatus.success

    def _quadratic_constraints(self) -> SubstitutionStatus:
        for quad_cst in self._src.quadratic_constraints:
            const1, lin1 = self._linear_expression(quad_cst.linear)
            const2, lin2, quadratic = self._quadratic_expression(quad_cst.quadratic)
            rhs = -fsum([-quad_cst.rhs] + const1 + const2)
            linear = lin1.coefficients + lin2.coefficients

            if quadratic.coefficients.nnz > 0:
                self._dst.quadratic_constraint(name=quad_cst.name, linear=linear,
                                               quadratic=quadratic.coefficients,
                                               sense=quad_cst.sense, rhs=rhs)
            elif linear.nnz > 0:
                name = quad_cst.name
                lin_names = set(lin.name for lin in self._dst.linear_constraints)
                while name in lin_names:
                    name = '_' + name
                self._dst.linear_constraint(name=name, linear=linear, sense=quad_cst.sense, rhs=rhs)
            else:
                if not self._feasible(quad_cst.sense, rhs):
                    logger.warning('constraint %s is infeasible due to substitution', quad_cst.name)
                    return SubstitutionStatus.infeasible

        return SubstitutionStatus.success
