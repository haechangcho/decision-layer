# Contributing to Decision Layer

Contributions to analytical methods, Recipe examples, provider contracts, documentation and usability are welcome. Open an issue for a bug or a proposed change; discuss changes to execution or semantic ownership before implementing them.

Read [AGENTS.md](AGENTS.md), [product context](docs/PRODUCT_CONTEXT.md), [architecture](docs/ARCHITECTURE.md) and [ADRs](docs/DECISIONS.md) first. ADRs take precedence over older proposals.

## Local development

Use Python 3.11+ and Node.js 22. From the repository root:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

Start the API in one terminal. Supply your Cube URL and caller token through your deployment/client configuration; the API does not need a live Cube to start.

```bash
.venv/bin/uvicorn decision_layer.api.app:app --reload --port 8000
```

Start the Web in another terminal:

```bash
cd web
npm ci
DL_API_URL=http://localhost:8000 npm run dev
```

Open http://localhost:5210. Configure a Cube connection through Sources or environment variables. For a complete model and data, use the [Docker example](examples/ecommerce/README.md).

## Verification

```bash
.venv/bin/pytest
```

The default suite excludes live Cube tests. To run those against the example stack:

```bash
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 \
CUBE_API_SECRET=example-secret-change-me-0123456789 \
.venv/bin/pytest -m cube
```

From `web/`:

```bash
npm run typecheck
npm run build
```

Browser tests use Playwright and a running Web server. Some existing journey tests are being updated alongside Recipe UX changes; do not describe a mocked API test as a live integration test.

```bash
npx playwright install chromium
PLAYWRIGHT_BASE_URL=http://localhost:5210 npm run test:e2e
```

## Add a Method or Recipe

A Method is an atomic analytical capability. A Recipe combines existing Methods into a reusable procedure. Prefer a Recipe when existing Methods are sufficient.

1. Read `methods/base.py`, the registry in `methods/__init__.py`, and an existing implementation under `methods/query/` or `methods/causal/`.
2. Declare typed roles, parameters, defaults, interpretation and outputs in the Method manifest.
3. Request data through the shared execution context and semantic provider. Do not redefine metric SQL, joins or access policy inside a Method.
4. Return structured artifacts, validation and warnings, including refusal when required assumptions cannot be checked.
5. Register the Method and add focused tests for valid inputs, missing data, invalid inputs and interpretation limits. Include an example and explain its assumptions in the pull request.

Methods are reviewed Python code installed with the server. A separate downloadable plugin runtime or automatic plugin installer is not implemented. Web, REST and MCP must use the same contract.

## Pull requests

Describe the user problem, the behavior change and the checks you ran. Keep changes scoped. Record architecture changes in `docs/DECISIONS.md` and distinguish implemented features from planned work.

Use synthetic data in examples. Do not commit credentials, private models, query results from customer data, local databases or internal infrastructure notes. The Docker example contains clearly labeled development credentials only.
