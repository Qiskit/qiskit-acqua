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

OS := $(shell uname -s)

ifeq ($(OS), Linux)
  NPROCS := $(shell grep -c ^processor /proc/cpuinfo)
else ifeq ($(OS), Darwin)
  NPROCS := 2
else
  NPROCS := 0
endif # $(OS)

ifeq ($(NPROCS), 2)
	CONCURRENCY := 2
else ifeq ($(NPROCS), 1)
	CONCURRENCY := 1
else ifeq ($(NPROCS), 3)
	CONCURRENCY := 3
else ifeq ($(NPROCS), 0)
	CONCURRENCY := 0
else
	CONCURRENCY := $(shell echo "$(NPROCS) 2" | awk '{printf "%.0f", $$1 / $$2}')
endif

# You can set this variable from the command line.
SPHINXOPTS    =

.PHONY: lint style test test_ci spell

lint:
	pylint -rn --ignore=gauopen qiskit/aqua qiskit/chemistry qiskit/finance qiskit/ml qiskit/optimization test

style:
	pycodestyle --max-line-length=100 --exclude=gauopen qiskit/aqua qiskit/chemistry qiskit/finance qiskit/ml qiskit/optimization test

test:
	python -m unittest discover -v test

test_ci:
	echo "Detected $(NPROCS) CPUs running with $(CONCURRENCY) workers"
	stestr run --concurrency $(CONCURRENCY)

spell:
	pylint -rn --disable=all --enable=spelling --spelling-dict=en_US --spelling-private-dict-file=.pylintdict --ignore=gauopen qiskit/aqua qiskit/chemistry qiskit/finance qiskit/ml qiskit/optimization test

html:
	make -C docs html SPHINXOPTS=$(SPHINXOPTS)
	
coverage:
	coverage3 run --source qiskit/aqua,qiskit/chemistry,qiskit/finance,qiskit/ml,qiskit/optimization -m unittest discover -s test -q
	coverage3 report

coverage_erase:
	coverage erase

clean: coverage_erase ;
