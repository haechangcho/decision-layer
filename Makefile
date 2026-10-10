PYTHON ?= python3
VENV := .venv/bin/python

.PHONY: setup example test setup-web api web check
setup:
	$(PYTHON) -m venv .venv
	$(VENV) -m pip install -e '.[dev]'

example:
	$(VENV) -m pytest -q examples/methods/first_method

test:
	$(VENV) -m pytest -q

setup-web:
	npm --prefix web ci

api:
	$(VENV) -m uvicorn decision_layer.api.app:app --reload --port 8000

web:
	DL_API_URL=http://localhost:8000 npm --prefix web run dev

check: test
	npm --prefix web run typecheck
	npm --prefix web run build
	npm run docs:build
