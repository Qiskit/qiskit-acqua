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

"""Parallelized Limited-memory BFGS optimizer"""

from typing import Optional
import multiprocessing
import platform
import logging

import numpy as np
from scipy import optimize as sciopt

from qiskit.aqua import aqua_globals
from qiskit.aqua.utils.validation import validate_min
from .optimizer import Optimizer

logger = logging.getLogger(__name__)

# pylint: disable=invalid-name


class P_BFGS(Optimizer):
    """
    Parallelized Limited-memory BFGS optimizer.

    P-BFGS is a parallelized version of :class:`L_BFGS_B` with which it shares the same parameters.
    P-BFGS can be useful when the target hardware is a quantum simulator running on a classical
    machine. This allows the multiple processes to use simulation to potentially reach a minimum
    faster. The parallelization may also help the optimizer avoid getting stuck at local optima.

    Uses scipy.optimize.fmin_l_bfgs_b.
    For further detail, please refer to
    https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.fmin_l_bfgs_b.html
    """

    _OPTIONS = ['maxfun', 'factr', 'iprint']

    # pylint: disable=unused-argument
    def __init__(self,
                 maxfun: int = 1000,
                 factr: float = 10,
                 iprint: int = -1,
                 max_processes: Optional[int] = None) -> None:
        r"""
        Args:
            maxfun: Maximum number of function evaluations.
            factr : The iteration stops when (f\^k - f\^{k+1})/max{\|f\^k\|,
                \|f\^{k+1}|,1} <= factr * eps, where eps is the machine precision,
                which is automatically generated by the code. Typical values for
                factr are: 1e12 for low accuracy; 1e7 for moderate accuracy;
                10.0 for extremely high accuracy. See Notes for relationship to ftol,
                which is exposed (instead of factr) by the scipy.optimize.minimize
                interface to L-BFGS-B.
            iprint: Controls the frequency of output. iprint < 0 means no output;
                iprint = 0 print only one line at the last iteration; 0 < iprint < 99
                print also f and \|proj g\| every iprint iterations; iprint = 99 print
                details of every iteration except n-vectors; iprint = 100 print also the
                changes of active set and final x; iprint > 100 print details of
                every iteration including x and g.
            max_processes: maximum number of processes allowed, has a min. value of 1 if not None.
        """
        if max_processes:
            validate_min('max_processes', max_processes, 1)
        super().__init__()
        for k, v in locals().items():
            if k in self._OPTIONS:
                self._options[k] = v
        self._max_processes = max_processes

    def get_support_level(self):
        """ return support level dictionary """
        return {
            'gradient': Optimizer.SupportLevel.supported,
            'bounds': Optimizer.SupportLevel.supported,
            'initial_point': Optimizer.SupportLevel.required
        }

    def optimize(self, num_vars, objective_function, gradient_function=None,
                 variable_bounds=None, initial_point=None):
        num_procs = multiprocessing.cpu_count() - 1
        num_procs = \
            num_procs if self._max_processes is None else min(num_procs, self._max_processes)
        num_procs = num_procs if num_procs >= 0 else 0

        if platform.system() == "Windows":
            num_procs = 0
            logger.warning("Using only current process. Multiple core use not supported in Windows")

        queue = multiprocessing.Queue()
        # bounds for additional initial points in case bounds has any None values
        threshold = 2 * np.pi
        if variable_bounds is None:
            variable_bounds = [(-threshold, threshold)] * num_vars
        low = [(l if l is not None else -threshold) for (l, u) in variable_bounds]
        high = [(u if u is not None else threshold) for (l, u) in variable_bounds]

        def optimize_runner(_queue, _i_pt):  # Multi-process sampling
            _sol, _opt, _nfev = self._optimize(num_vars, objective_function,
                                               gradient_function, variable_bounds, _i_pt)
            _queue.put((_sol, _opt, _nfev))

        # Start off as many other processes running the optimize (can be 0)
        processes = []
        for _ in range(num_procs):
            i_pt = aqua_globals.random.uniform(low, high)  # Another random point in bounds
            p = multiprocessing.Process(target=optimize_runner, args=(queue, i_pt))
            processes.append(p)
            p.start()

        # While the one _optimize in this process below runs the other processes will
        # be running to. This one runs
        # with the supplied initial point. The process ones have their own random one
        sol, opt, nfev = self._optimize(num_vars, objective_function,
                                        gradient_function, variable_bounds, initial_point)

        for p in processes:
            # For each other process we wait now for it to finish and see if it has
            # a better result than above
            p.join()
            p_sol, p_opt, p_nfev = queue.get()
            if p_opt < opt:
                sol, opt = p_sol, p_opt
            nfev += p_nfev

        return sol, opt, nfev

    def _optimize(self, num_vars, objective_function, gradient_function=None,
                  variable_bounds=None, initial_point=None):
        super().optimize(num_vars, objective_function, gradient_function,
                         variable_bounds, initial_point)

        approx_grad = bool(gradient_function is None)
        sol, opt, info = sciopt.fmin_l_bfgs_b(objective_function, initial_point,
                                              bounds=variable_bounds,
                                              fprime=gradient_function,
                                              approx_grad=approx_grad, **self._options)
        return sol, opt, info['funcalls']
