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
from qiskit_aqua.svm import (get_points_and_labels, optimize_SVM)
from qiskit_aqua.multiclass.allpairs import AllPairs
from qiskit_aqua.multiclass.error_correcting_code import ErrorCorrectingCode
from qiskit_aqua.multiclass.one_against_rest import OneAgainstRest
from qiskit_aqua.multiclass.multiclass_classicalsvm.rbf_svc_estimator import RBF_SVC_Estimator
from qiskit_aqua.multiclass.data_preprocess import *

class SVM_Multiclass_RBF(QuantumAlgorithm):
    SVM_CLASSICAL_MULTICLASS_CONFIGURATION = {
        'name': 'SVM_Multiclass_RBF',
        'description': 'SVM_Multiclass_RBF Algorithm',
        'classical': True,
        'input_schema': {
            '$schema': 'http://json-schema.org/schema#',
            'id': 'SVM_Multiclass_RBF_schema',
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
        super().__init__(configuration or copy.deepcopy(SVM_Multiclass_RBF.SVM_CLASSICAL_MULTICLASS_CONFIGURATION))
        self._ret = {}

    def init_params(self, params, algo_input):
        svm_params = params.get(QuantumAlgorithm.SECTION_KEY_ALGORITHM)
        self.init_args(algo_input.training_dataset, algo_input.test_dataset,
                       algo_input.datapoints, svm_params.get('print_info'), svm_params.get('multiclass_alg')
                       )

    def init_args(self, training_dataset, test_dataset, datapoints, print_info, multiclass_alg):
        self.training_dataset = training_dataset
        self.test_dataset = test_dataset
        self.datapoints = datapoints
        self.class_labels = list(self.training_dataset.keys())
        self.print_info = print_info
        self.multiclass_alg = multiclass_alg


    def run(self):
        if self.training_dataset is None:
            self._ret['error'] = 'training dataset is missing! please provide it'
            return self._ret


        X_train, y_train, label_to_class = multiclass_get_points_and_labels(self.training_dataset, self.class_labels)
        X_test, y_test, label_to_class = multiclass_get_points_and_labels(self.test_dataset, self.class_labels)

        if self.multiclass_alg == "all_pairs":
            multiclass_classifier = AllPairs(RBF_SVC_Estimator)
        elif self.multiclass_alg == "one_against_all":
            multiclass_classifier = OneAgainstRest(RBF_SVC_Estimator)
        elif self.multiclass_alg == "error_correcting_code":
            multiclass_classifier = ErrorCorrectingCode(RBF_SVC_Estimator, code_size=4)
        else:
            self._ret['error'] = 'the multiclass alg should be one of {"all_pairs", "one_against_all", "error_correcting_code"}. You did not specify it correctly!'
            return self._ret
        if self.print_info:
            print("You are using the multiclass alg: " + self.multiclass_alg)

        multiclass_classifier.train(X_train, y_train)

        if self.test_dataset is not None:
            success_ratio = multiclass_classifier.test(X_test, y_test)
            self._ret['test_success_ratio'] = success_ratio

        if self.datapoints is not None:
            predicted_labels = multiclass_classifier.predict(X_test)
            predicted_labelclasses = [label_to_class[x] for x in predicted_labels]
            self._ret['predicted_labels'] = predicted_labelclasses
        return self._ret
