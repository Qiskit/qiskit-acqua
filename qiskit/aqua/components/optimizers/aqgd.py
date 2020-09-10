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

"""The implementation of the Analytical Quantum Gradient Descent (AQGD)."""

from typing import Callable, Tuple, List, Dict
import logging
import numpy as np
from qiskit.aqua import AquaError
from qiskit.aqua.utils.validation import validate_range_exclusive_max
from qiskit.aqua.components.optimizers import Optimizer

logger = logging.getLogger(__name__)


class AQGD(Optimizer):
    """Analytic Quantum Gradient Descent (AQGD) with Epochs optimizer.
    Performs gradient descent optimization with a momentum term, analytic gradients,
    and customized step length schedule for parametrized quantum gates, i.e.
    Pauli Rotations. See, for example:

    * K. Mitarai, M. Negoro, M. Kitagawa, and K. Fujii. (2018).
      Quantum circuit learning. Phys. Rev. A 98, 032309.
      https://arxiv.org/abs/1803.00745

    * Maria Schuld, Ville Bergholm, Christian Gogolin, Josh Izaac, Nathan Killoran. (2019).
      Evaluating analytic gradients on quantum hardware. Phys. Rev. A 99, 032331.
      https://arxiv.org/abs/1811.11184

    for further details on analytic gradients of parametrized quantum gates.

    Gradients are computed "analytically" using the quantum circuit when evaluating
    the objective function.

    """
    _OPTIONS = ['maxiter', 'eta', 'momentum', 'ptol', 'otol', 'averaging']

    def __init__(self,
                 maxiter: List[int] = [1000],
                 eta: List[float] = [1.0],
                 momentum: List[float] = [0.5],
                 ptol: float = 1e-6,
                 otol: float = 1e-6,
                 averaging: int = 10) -> None:
        """
        Constructor.

        Performs Analytical Quantum Gradient Descent (AQGD) with Epochs.

        Args:
            maxiter: Maximum number of iterations (full gradient steps)
            eta: The coefficient of the gradient update. Increasing this value
                results in larger step sizes: param = previous_param - eta * deriv
            momentum: Bias towards the previous gradient momentum in current
                update. Must be within the bounds: [0,1)
            ptol: Tolerance for change in norm of parameters.
            otol: Tolerance for change in windowed average of objective values. Convergence
                occurs when either objective tolerance is met OR parameter tolerance is met
            averaging: Length of window over which to average objective values for objective
                convergence criterion

        Raises:
            AquaError: If the number of iterations doesn't match momentum or eta for the
                       desired steps.
        """
        if len(maxiter) != len(eta) or len(maxiter) != len(momentum):
            raise AquaError("AQGD input parameter length mismatch")
        for m in momentum:
            validate_range_exclusive_max('momentum', m, 0, 1)
        super().__init__()

        self._eta = eta
        self._maxiter = maxiter
        self._momenta_coeff = momentum
        self._ptol = ptol if ptol is not None else 1e-6
        self._otol = otol if otol is not None else 1e-6
        self._averaging = averaging
        self._avg_objval = None
        self._prev_param = None

    def get_support_level(self) -> Dict[str, int]:
        """ Support level dictionary

        Returns:
            Dict[str, int]: gradient, bounds and initial point
                            support information that is ignored/required.
        """
        return {
            'gradient': Optimizer.SupportLevel.ignored,
            'bounds': Optimizer.SupportLevel.ignored,
            'initial_point': Optimizer.SupportLevel.required
        }

    def compute_objective_fn_and_gradient(self, params: List[float],
                                          obj: Callable) -> Tuple[float, np.array]:
        """
        Obtains the objective function value for params and the analytical quantum derivatives of
        the objective function with respect to each parameter. Requires
        2*(number parameters) + 1 objective evaluations

        Args:
            params: Current value of the parameters to evaluate the objective function
            obj: Objective function of interest

        Returns:
            Tuple containing the objective value and array of gradients for the given parameter set.
        """
        num_params = len(params)
        param_sets_to_eval = params + np.concatenate(
            (np.zeros((1, num_params)),    # copy of the parameters as is
             np.eye(num_params)*np.pi/2,   # copy of the parameters with the positive shift
             -np.eye(num_params)*np.pi/2),  # copy of the parameters with the negative shift
            axis=0)
        # Evaluate,
        # reshaping to flatten, as expected by objective function
        values = np.array(obj(param_sets_to_eval.reshape(-1)))

        # Update number of objective function evaluations
        self._eval_count += 2*num_params + 1

        # return the objective function value
        obj_value = values[0]

        # return the gradient values
        gradient = 0.5*(values[1:num_params+1] - values[1+num_params:])
        return obj_value, gradient

    def update(self, params: np.array, gradient: np.array, mprev: np.array,
               step_size: float, momentum_coeff: float) -> Tuple[List[float], List[float]]:
        """
        Updates full parameter array based on a step that is a convex
        combination of the gradient and previous momentum

        Args:
            params: Current value of the parameters to evaluate the objective function at
            gradient: Gradient of objective wrt parameters
            mprev: Momentum vector for each parameter
            step_size: The scaling of step to take
            momentum_coeff: Bias towards previous momentum vector when updating current
                momentum/step vector

        Returns:
            Tuple of the updated parameter and momentum vectors respectively.
        """
        # Momentum update:
        # Convex combination of previous momentum and current gradient estimate
        mnew = (1-momentum_coeff) * gradient + momentum_coeff * mprev
        params -= step_size * mnew
        return params, mnew

    def converged_objective(self, objval: float, tol: float, n: int) -> bool:
        """
        Tests convergence based on the change in a moving windowed average of past objective values

        Args:
            objval: Current value of the objective function
            tol: tolerance below which (average) objective function change must be
            n: size of averaging window

        Returns:
            Bool indicating whether or not the optimization has converged.
        """
        # If we haven't reached the required window length,
        # append the current value, but we haven't converged
        if len(self._prev_loss) < n:
            self._prev_loss.append(objval)
            return False

        # Update last value in list with current value
        self._prev_loss.append(objval)
        # (length now = n+1)

        # Calculate previous windowed average
        # and current windowed average of objective values
        prev_avg = np.mean(self._prev_loss[:n])
        curr_avg = np.mean(self._prev_loss[1:n+1])
        self._avg_objval = curr_avg

        # Update window of objective values
        # (Remove earliest value)
        self._prev_loss.pop(0)

        if np.absolute(prev_avg - curr_avg) < tol:
            # converged
            logger.info("Previous obj avg: %f\nCurr obj avg: %f", prev_avg, curr_avg)
            return True
        # else
        return False

    def converged_parameter(self, parameter: List[float], tol: float) -> bool:
        """
        Tests convergence based on change in parameter

        Args:
            parameter: current parameter values
            tol: tolerance for change in norm of parameters

        Returns:
            Bool indicating whether or not the optimization has converged
        """
        if self._prev_param is None:
            self._prev_param = np.copy(parameter)
            return False

        order = np.inf
        p_change = np.linalg.norm(self._prev_param - parameter, ord=order)
        if p_change < tol:
            # converged
            logger.info("Change in parameters (%f norm): %f", order, p_change)
            return True
        # else
        return False

    def converged_alt(self, gradient: List[float], tol: float, n: int) -> bool:
        """
        Tests convergence from norm of windowed average of gradients

        Args:
            gradient: current gradient
            tol: tolerance for average gradient norm
            n: size of averaging window

        Returns:
            Bool indicating whether or not the optimization has converged
        """
        # If we haven't reached the required window length,
        # append the current value, but we haven't converged
        if len(self._prev_grad) < n-1:
            self._prev_grad.append(gradient)
            return False

        # Update last value in list with current value
        self._prev_grad.append(gradient)
        # (length now = n)

        # Calculate previous windowed average
        # and current windowed average of objective values
        avg_grad = np.mean(self._prev_grad, axis=0)

        # Update window of values
        # (Remove earliest value)
        self._prev_grad.pop(0)

        if np.linalg.norm(avg_grad, ord=np.inf) < tol:
            # converged
            logger.info("Avg. grad. norm: %f", np.linalg.norm(avg_grad, ord=np.inf))
            return True
        # else
        return False

    def optimize(self,
                 num_vars: int,
                 objective_function: Callable,
                 gradient_function: Callable = None,
                 variable_bounds: Callable = None,
                 initial_point: List[float] = None) -> Tuple[np.ndarray[float], float, int]:
        """
        Perform optimization

        Args:
            num_vars: Number of variables/parameters
            objective_function: Objective function evaluator
            gradient_function: Function that calculates gradients of the
                objective or None if not available/used.
            variable_bounds: List of variable bounds, given as (lower, upper).
                None means unbounded.
            initial_point (array): Initial parameters at which to start

        Returns:
            Set of parameters, objective value and number of objective function
            calls/evaluations.
        """
        super().optimize(num_vars, objective_function, gradient_function, variable_bounds,
                         initial_point)

        params = np.array(initial_point)
        momentum = np.zeros(shape=(num_vars,))
        # empty out history of previous objectives/gradients/parameters
        # (in case this object is re-used)
        self._prev_loss = []
        self._prev_grad = []
        self._prev_param = None
        self._eval_count = 0    # function evaluations
        self._iter = 0          # running iteration

        logger.info("Initial Params: %s", params)

        epoch = 0
        self._converged = False
        for (eta, mom_coeff) in zip(self._eta, self._momenta_coeff):
            logger.info("Epoch: {:4d} | Stepsize: {:6.4f} | Momentum: {:6.4f}".format(
                epoch, eta, mom_coeff))

            sum_max_iters = sum(self._maxiter[0:epoch+1])
            while self._iter < sum_max_iters:
                # update the iteration count
                self._iter += 1

                # Check for parameter convergence before potentially costly function evaluation
                self._converged = self.converged_parameter(params, self._ptol)
                if self._converged:
                    break

                # Calculate objective function and estimate of analytical gradient
                objval, gradient = \
                    self.compute_objective_fn_and_gradient(params, objective_function)

                logger.info(" Iter: {:4d} | Obj: {:11.6f} | Grad Norm: {}".format(
                    self._iter, objval, np.linalg.norm(gradient, ord=np.inf)))

                # Check for objective convergence
                self._converged = self.converged_objective(objval, self._otol, self._averaging)
                if self._converged:
                    break

                # Update parameters and momentum
                params, momentum = self.update(params, gradient, momentum, eta, mom_coeff)
            # end inner iteration
            # if converged, end iterating over epochs
            if self._converged:
                break
            epoch += 1
        # end epoch iteration

        # return last parameter values, objval estimate, and objective evaluation count
        return params, objval, self._eval_count
