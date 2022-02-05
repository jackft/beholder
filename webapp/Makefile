PYTHON_INTERPRETER = python3.8
VIRTUALENV = .venv
VENV_FLASK = ${VIRTUALENV}/bin/flask
PYTHON = .venv/bin/python
PIP = .venv/bin/pip

.DEFAULT_GOAL := build
.PHONY: dependencies

.venv:
	virtualenv --python $(PYTHON_INTERPRETER) .venv

build: dependencies install

dependencies: .venv
	$(PIP) install -r requirements.txt


install: dependencies
	mkdir -p uwsgi_metrics

test: install
	echo "HI"

clean:
	rm -fr ${VIRTUALENV}
