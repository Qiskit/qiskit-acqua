# -*- coding: utf-8 -*-

# Copyright 2018 IBM.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================

import numpy as np

from sklearn.metrics.pairwise import rbf_kernel
import copy
from qiskit_aqua import QuantumAlgorithm
from qiskit_aqua.svm_qkernel import (get_points_and_labels, optimize_SVM)
from qiskit_aqua.svm_classical.svm_classical_binary import SVM_Classical_Binary
from qiskit_aqua.svm_classical.svm_classical_multiclass import SVM_Classical_Multiclass

class SVM_Classical(QuantumAlgorithm):
    SVM_Classical_CONFIGURATION = {
        'name': 'SVM_Classical',
        'description': 'SVM_Classical Algorithm',
        'classical': True,
        'input_schema': {
            '$schema': 'http://json-schema.org/schema#',
            'id': 'SVM_Classical_schema',
            'type': 'object',
            'properties': {
                'multiclass_alg': {
                    'type': 'string',
                    'default': 'all_pairs'
                },
                'print_info': {
                    'type': 'boolean',
                    'default': False
                }
            },
            'additionalProperties': False
        },
        'problems': ['svm_classification']
    }

    def __init__(self, configuration=None):
        super().__init__(configuration or copy.deepcopy(SVM_Classical.SVM_Classical_CONFIGURATION))
        self._ret = {}

    def init_params(self, params, algo_input):
        SVM_Classical_params = params.get(QuantumAlgorithm.SECTION_KEY_ALGORITHM)
        is_multiclass = (len(algo_input.training_dataset.keys()) > 2)
        if is_multiclass:
            self.instance = SVM_Classical_Multiclass()
        else:
            self.instance = SVM_Classical_Binary()
        self.instance.init_args(algo_input.training_dataset, algo_input.test_dataset, algo_input.datapoints, SVM_Classical_params.get('print_info'), SVM_Classical_params.get('multiclass_alg'))

    def run(self):
        self.instance.run()
        return self.instance._ret
