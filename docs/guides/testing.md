# Testing

Run the smallest relevant check first. Install [development dependencies](development.md). Live tests create Runs and draft candidates; use an isolated sample, not production.

## Unit and API contracts

From the repository root:

```bash
.venv/bin/pytest
.venv/bin/pytest tests/unit/test_methods.py
```

No running Cube is needed. The default suite excludes the `cube` marker; other live tests skip unless their opt-in environment variables are set. Skipped tests do not verify integration.

## Web

From `web/`:

```bash
npm run typecheck
npm run build
npx playwright install chromium
```

Start Web in one terminal with `npm run dev`. In another, from `web/`:

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5210 npm run test:e2e
```

Default product tests use mocked API responses on desktop and mobile. They need Web, not live Cube. Live scenarios skip without their specific environment values. Failure screenshots and traces are in `web/test-results/`.

## Live Chinook

Start the [sample](../../examples/chinook/README.md) with an empty Recipe folder. From `examples/chinook/`:

```bash
docker compose run --rm --no-deps import python verify.py
```

This checks the pinned import, 11 tables, independent SQL totals and the read-only source role. From the repository root:

```bash
DL_CHINOOK_API_URL=http://127.0.0.1:8000 \
  .venv/bin/pytest -q -s tests/provider/test_chinook_live.py
```

The tests exercise real Cube joins, grain reconciliation, Recipe preview and explicit Recipe-free MCP tool execution through the API. Copy the printed `CHINOOK_MCP_RUN_ID`. From `web/`, verify the live graph and Recipe review flow:

```bash
CHINOOK_RUN_ID=run_replace_with_printed_id \
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 \
  npm run test:e2e -- tests/product/chinook-live.spec.ts
```

Use your actual API/Web ports. Do not delete your Recipes to satisfy a test; use an isolated sample folder. The browser test reviews an unsaved candidate, not a published Recipe.

## Other datasets

For [synthetic ecommerce](../../examples/ecommerce/README.md), the `cube` marker specifically expects that model:

```bash
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 \
CUBE_API_SECRET=example-secret-change-me-0123456789 \
  .venv/bin/pytest -m cube
```

For [Online Retail II](../../examples/online-retail/README.md), run the verifier from that example directory:

```bash
docker compose run --rm --no-deps import python verify.py
```

Then from the repository root:

```bash
DL_RETAIL_API_URL=http://127.0.0.1:8000 \
  .venv/bin/pytest -q -s tests/provider/test_online_retail_live.py
```

## Interpret the checks

| Check | Demonstrates | Does not demonstrate |
| --- | --- | --- |
| Unit / mocked API | Contracts and known behavior | Live source compatibility |
| Mocked browser | UI states and interactions | Real queries or AI planning |
| SQL reference + live MCP | Import integrity and explicit tool execution | Natural-language tool selection |
| Actual AI-client trial | One client's behavior on a question | General improvement or causal accuracy |

Try a question through [your AI client](mcp.md) separately. Record client/model, question, Run ID, Methods, warnings and reference comparison. Use the [evaluation protocol](../../examples/online-retail/evals/PROTOCOL.md) for comparative claims.

CI currently checks Python contracts, Web typechecking/build, Docker onboarding and synthetic Cube execution. Chinook and browser checks above are explicit local checks, not implied CI coverage.
