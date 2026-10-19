PYTHON ?= python3
VENV := .venv/bin/python

.PHONY: setup example test setup-web api web check format-methods check-method-format
setup:
	$(PYTHON) -m venv .venv
	$(VENV) -m pip install -e '.[dev,stats]'

example:
	$(VENV) -m pytest -q tests/examples/test_method_tutorial.py

test:
	$(VENV) -m pytest -q

setup-web:
	npm --prefix web ci

api:
	$(VENV) -m uvicorn decision_layer.api.app:app --reload --port 8000

web:
	DL_API_URL=http://localhost:8000 npm --prefix web run dev

format-methods:
	$(VENV) scripts/format_methods.py

check-method-format:
	$(VENV) scripts/format_methods.py --check

check: check-method-format test
	npm --prefix web run typecheck
	npm --prefix web run build
	npm run docs:build
