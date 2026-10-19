# Contribute to the product

To add your team's calculation, start with [Write a Method](methods.md). This guide
covers changes to Decision Layer itself. Use Python 3.11+ and Node.js 22.

## Install and run

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer
make setup
make setup-web
```

Run the API and Web in separate terminals:

```bash
make api
```

```bash
make web
```

Open Web at `http://localhost:5210` and API docs at `http://localhost:8000/docs`.
Live queries require [Cube](cube.md). To try the installed sample, use
`decision-layer demo` from [Install and start](quickstart.md).

## Code map

```text
src/decision_layer/
├── methods/       # Method registration, input contracts and calculations
├── recipes/       # Reusable analysis procedures
├── runs/          # Execution, authorization and recorded evidence
├── semantic/      # Cube connection and canonical queries
├── api/           # REST API
├── mcp/           # AI tools using that API
└── demo/          # Installed sample resources and launcher
web/
├── app/           # Routes
├── features/      # Method, Recipe and Run screens
└── components/    # Shared UI
docs/              # Guides and the bilingual Method notebook
examples/          # Authoring tutorial, complete project and product demos
tests/             # Unit, API, provider and tutorial checks
└── support/       # Shared fixtures and known-answer cases
```

Change execution rules in the shared Python code. Web, REST and MCP use the same
execution model. See [Architecture](../ARCHITECTURE.md) for detailed ownership.
Frontend builds generate `src/decision_layer/static/`; edit source files rather than generated assets.

Read `AGENTS.md`, `docs/PRODUCT_CONTEXT.md`, `docs/ARCHITECTURE.md` and
`docs/DECISIONS.md` before changing product behavior. Record architecture changes in the decisions log.

## Tests {#tests}

Run focused tests, then the full checks:

```bash
.venv/bin/python -m pytest -q tests/unit/test_method_project.py
make test
npm --prefix web run typecheck
npm --prefix web run build:console
npm ci
npm run docs:build
```

`tests/examples/` checks the retained notebook and complete project.
`tests/support/` owns shared inputs and known-answer cases. Optional statistical
tests skip when their dependencies are missing; statistical CI installs the
stack in `tests/requirements-statistics.txt`.

For screen changes, start the development server, then:

```bash
cd web
npx playwright install chromium
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5210 npm run test:e2e
```

Default browser checks mock API responses. Follow the
[Complete Journey example](https://github.com/haechangcho/decision-layer/tree/main/examples/complete-journey)
for live Cube integration. `scripts/smoke_distribution.py` checks an installed
package, and `scripts/smoke_demo.py` checks the installed Docker sample. CI runs both.

## Submit your change

Run `make format-methods` and include relevant test results in your PR. Include
screenshots for screen changes and inputs with expected results for analysis changes.
See [CONTRIBUTING.md](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md)
for issue reports and review expectations.
