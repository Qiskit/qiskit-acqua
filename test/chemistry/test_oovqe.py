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

""" Test of the OOVQE ground state calculations """
import unittest
from test.chemistry import QiskitChemistryTestCase

from qiskit.chemistry.drivers import HDF5Driver
from qiskit.providers.basicaer import BasicAer
from qiskit.aqua import QuantumInstance
from qiskit.aqua.algorithms import VQE
from qiskit.chemistry.components.variational_forms import UCCSD
from qiskit.chemistry.components.initial_states import HartreeFock
from qiskit.aqua.components.optimizers import COBYLA
from qiskit.chemistry.ground_state_calculation import VQEUCCSDFactory, OOVQE
from qiskit.chemistry.qubit_transformations import FermionicTransformation
from qiskit.chemistry.qubit_transformations.fermionic_transformation import QubitMappingType


class TestOOVQE(QiskitChemistryTestCase):
    """ Test OOVQE Ground State Calculation. """

    def setUp(self):
        super().setUp()

        file1 = 'test_oovqe_h4.hdf5'
        file2 = 'test_oovqe_lih.hdf5'
        file3 = 'test_oovqe_h4_uhf.hdf5'

        self.driver1 = HDF5Driver(hdf5_input=self.get_resource_path(file1))
        self.driver2 = HDF5Driver(hdf5_input=self.get_resource_path(file2))
        self.driver3 = HDF5Driver(hdf5_input=self.get_resource_path(file3))

        self.energy1_rotation = -3.0104
        self.energy1 = -2.77  # energy of the VQE with pUCCD ansatz and LBFGSB optimizer
        self.energy2 = -7.70
        self.energy3 = -2.50
        self.initial_point1 = [0.039374, -0.47225463, -0.61891996, 0.02598386, 0.79045546,
                               -0.04134567, 0.04944946, -0.02971617, -0.00374005, 0.77542149]

        self.seed = 50

        self.optimizer = COBYLA(maxiter=1)
        self.transformation1 = FermionicTransformation(qubit_mapping=QubitMappingType.JORDAN_WIGNER,
                                                       two_qubit_reduction=False)
        self.transformation2 = FermionicTransformation(qubit_mapping=QubitMappingType.JORDAN_WIGNER,
                                                       two_qubit_reduction=False,
                                                       freeze_core=True)

    def make_solver(self):
        """ Instantiates a solver for the test of OOVQE. """

        quantum_instance = QuantumInstance(BasicAer.get_backend('statevector_simulator'),
                                           shots=1,
                                           seed_simulator=self.seed,
                                           seed_transpiler=self.seed)
        solver = VQEUCCSDFactory(quantum_instance)

        def get_custom_solver(self, transformation):
            """Customize the solver."""

            num_orbitals = transformation._molecule_info['num_orbitals']
            num_particles = transformation._molecule_info['num_particles']
            qubit_mapping = transformation._qubit_mapping
            two_qubit_reduction = transformation._molecule_info['two_qubit_reduction']
            z2_symmetries = transformation._molecule_info['z2_symmetries']
            initial_state = HartreeFock(num_orbitals, num_particles, qubit_mapping,
                                        two_qubit_reduction, z2_symmetries.sq_list)
            # only paired doubles excitations
            var_form = UCCSD(num_orbitals=num_orbitals,
                             num_particles=num_particles,
                             initial_state=initial_state,
                             qubit_mapping=qubit_mapping,
                             two_qubit_reduction=two_qubit_reduction,
                             z2_symmetries=z2_symmetries,
                             excitation_type='d',
                             same_spin_doubles=False,
                             method_doubles='pucc')
            vqe = VQE(var_form=var_form, quantum_instance=self._quantum_instance,
                      optimizer=COBYLA(maxiter=1))
            return vqe

        # pylint: disable=no-value-for-parameter
        solver.get_solver = get_custom_solver.__get__(solver, VQEUCCSDFactory)
        return solver

    def test_orbital_rotations(self):
        """ Test that orbital rotations are performed correctly. """

        solver = self.make_solver()
        calc = OOVQE(self.transformation1, solver, self.driver1, iterative_oo=False,
                     initial_point=self.initial_point1)
        calc._vqe.optimizer.set_options(maxiter=1)
        algo_result = calc.compute_groundstate(self.driver1)
        self.assertAlmostEqual(algo_result.computed_electronic_energy, self.energy1_rotation, 4)

    def test_oovqe(self):
        """ Test the simultaneous optimization of orbitals and ansatz parameters with OOVQE using
        BasicAer's statevector_simulator. """

        solver = self.make_solver()
        calc = OOVQE(self.transformation1, solver, self.driver1, iterative_oo=False,
                     initial_point=self.initial_point1)
        calc._vqe.optimizer.set_options(maxiter=3, rhobeg=0.01)
        algo_result = calc.compute_groundstate(self.driver1)
        self.assertLessEqual(algo_result.computed_electronic_energy, self.energy1, 4)

    def test_iterative_oovqe(self):
        """ Test the iterative OOVQE using BasicAer's statevector_simulator. """

        solver = self.make_solver()
        calc = OOVQE(self.transformation1, solver, self.driver1, iterative_oo=True,
                     initial_point=self.initial_point1, iterative_oo_iterations=2)
        calc._vqe.optimizer.set_options(maxiter=2, rhobeg=0.01)
        algo_result = calc.compute_groundstate(self.driver1)
        self.assertLessEqual(algo_result.computed_electronic_energy, self.energy1)

    def test_oovqe_with_frozen_core(self):
        """ Test the OOVQE with frozen core approximation. """

        solver = self.make_solver()
        calc = OOVQE(self.transformation2, solver, self.driver2, iterative_oo=False)
        calc._vqe.optimizer.set_options(maxiter=2, rhobeg=1)
        algo_result = calc.compute_groundstate(self.driver2)
        self.assertLessEqual(algo_result.computed_electronic_energy +
                             self.transformation2._energy_shift +
                             self.transformation2._nuclear_repulsion_energy, self.energy2)

    def test_oovqe_with_unrestricted_hf(self):
        """ Test the OOVQE with unrestricted HF method. """

        solver = self.make_solver()
        calc = OOVQE(self.transformation1, solver, self.driver3, iterative_oo=False)
        calc._vqe.optimizer.set_options(maxiter=2, rhobeg=0.01)
        algo_result = calc.compute_groundstate(self.driver3)
        self.assertLessEqual(algo_result.computed_electronic_energy, self.energy3)


if __name__ == '__main__':
    unittest.main()
