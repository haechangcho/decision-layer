# Development and tests

To add your team's calculation, start with [Register in a project](method-projects.md). This guide
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

## Find the code to change

See [Code structure](../ARCHITECTURE.md) for execution flow and module ownership. Change execution rules in shared Python code rather than adding separate calculations to Web, REST or MCP.

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
npm run docs:test
npm run docs:build
```

For screen changes, start the development server, then:

```bash
cd web
npx playwright install chromium
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5210 npm run test:e2e
```

Browser tests mock API responses. For live data integration, use the
[Complete Journey example](https://github.com/haechangcho/decision-layer/tree/main/examples/complete-journey).

## Submit your change

Run `make format-methods` and include relevant test results in your PR. Include
screenshots for screen changes and inputs with expected results for analysis changes.
See [CONTRIBUTING.md](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md)
for issue reports and review expectations.

## UI layout verification

Run `npm --prefix web run test:e2e -- ui-layout-audit.spec.ts` with the local
Web server running. The shared-console audit covers 1440px desktop, 817px compact
and 390px mobile layouts with controlled API fixtures. It checks the five main
pages, Method/Recipe details, shared-login chrome, long names, query/SQL insets,
local code scrolling, copy feedback and modal focus/escape behavior. Existing
product scenarios also cover loading, empty, denied, retry, Recipe editing and
Run evidence flows.

A visible heading alone does not establish a usable layout. Query evidence tests
must assert heading/code alignment and the card's inner spacing. List tests check
column positions; page tests check that controls stay within the viewport. Keep
technical records unchanged when improving their presentation. Review captured
screenshots as well as assertions, including the installed Vite console after
building and deploying an image; Next development pages alone are insufficient.
Run one Playwright command at a time, or give concurrent runs separate `--output`
directories so their traces and screenshots cannot overwrite each other.
