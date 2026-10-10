# Testing

Run the smallest relevant check first. Install [development dependencies](development.md). Live tests create Runs and draft candidates; use an isolated sample, not production.

## Unit and API contracts

From the repository root:

```bash
make test
.venv/bin/python -m pytest -q examples/methods
```

No running Cube is needed. Live tests skip unless their opt-in environment variables are set. Skipped tests do not verify integration. The synthetic metadata in `tests/fixtures/` is a self-contained contract fixture, not another deployable sample.

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

## Live Complete Journey

Start the [default sample](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.md) with Recipes empty. From its directory:

```bash
docker compose -p decision-layer-cube run --rm --no-deps import python verify.py
```

From the repository root:

```bash
DL_JOURNEY_API_URL=http://127.0.0.1:8000 \
  .venv/bin/pytest -q -s tests/provider/test_complete_journey_live.py
```

The live check records Recipe-free MCP drill-down and peer comparison, then reviews a Recipe candidate.
Method example tests need no Cube.


From `web/`, use the printed `JOURNEY_MCP_RUN_ID` for desktop/mobile review:

```bash
JOURNEY_RUN_ID=run_replace_with_printed_id PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 \
  npm run test:e2e -- tests/product/complete-journey-live.spec.ts
```

Use your actual API/Web ports. Do not delete your Recipes to satisfy a test; use an isolated sample folder. The browser test reviews an unsaved candidate, not a published Recipe.

## Hosted dbt API

`tests/unit/test_dbt_provider.py` tests the official GraphQL contract with mocked responses, including Method execution and Run-to-Recipe conversion. The real hosted API has a separate read-only smoke test:

```bash
# Configure these privately: DL_DBT_TEST_URL, DL_DBT_TEST_ENVIRONMENT_ID,
# DL_DBT_TEST_TOKEN, DL_DBT_TEST_METRIC (a metric name in your environment).
.venv/bin/pytest tests/provider/test_dbt_live.py -q
```

Without those settings the test skips. Hosted authentication and warehouse behavior require a real dbt environment.

## Interpret the checks

| Check | Demonstrates | Does not demonstrate |
| --- | --- | --- |
| Unit / mocked API | Contracts and known behavior | Live source compatibility |
| Mocked browser | UI states and interactions | Real queries or AI planning |
| SQL reference + live MCP | Import integrity and explicit tool execution | Natural-language tool selection |
| Actual AI-client trial | One client's behavior on a question | General improvement or causal accuracy |

Try a question through [your AI client](mcp.md) separately. Record client/model, question, Run ID, Methods, warnings and reference comparison. Use the [evaluation protocol](evaluation.md) for comparative claims.

CI checks Python contracts and the Method examples, Web typechecking/build, Docker onboarding, and Complete Journey SQL/MCP execution. Browser checks above are explicit local checks, not implied CI coverage. The full sample job downloads the source archive and therefore requires upstream availability.
