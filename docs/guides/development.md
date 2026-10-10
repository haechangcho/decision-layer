# Local development

For Method work, start with [First Method](methods.md). To change Web or API,
use Python 3.11+ and Node.js 22. Run these commands from the repository root.

## Install

```bash
make setup
make setup-web
```

## Start API and Web

In one terminal:

```bash
make api
```

In another:

```bash
make web
```

Open Web at **http://localhost:5210** and the REST API reference at
**http://localhost:8000/docs**. The Docker sample uses Web port 3000 instead.

The API starts without a semantic source. Connect [Cube](cube.md) or
[dbt Semantic Layer](dbt.md) for live analysis. Runs use local SQLite by default;
set `DL_RECIPES_DIR=./recipes make api` to save Recipe files in that folder.

If port 8000 is occupied, start the API with an available port:

```bash
.venv/bin/python -m uvicorn decision_layer.api.app:app --reload --port 8001
DL_API_URL=http://localhost:8001 npm --prefix web run dev
```

Use separate terminals. Update the [MCP connection](mcp.md) to the same API port.

::: details Connect the sample (optional)
From `examples/complete-journey/`, start only the data services:

```bash
docker compose -p decision-layer-cube up -d --build --wait postgres import cube
```

If the full sample is already running, first stop its API and Web with `docker compose -p decision-layer-cube stop api web` from that directory to free their ports. Do not stop unrelated stacks.

Return to the repository root and start the native API with the sample connection:

```bash
mkdir -p data examples/complete-journey/recipes
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 \
CUBE_INSTANCE=journey \
CUBE_API_SECRET=local-example-secret-change-me-0123456789 \
DL_ALLOW_SERVICE_CREDENTIALS=true \
DL_RECIPES_DIR=examples/complete-journey/recipes \
DL_DATABASE_URL=sqlite:///./data/journey-development.db \
  .venv/bin/uvicorn decision_layer.api.app:app --reload --port 8000
```

Use your actual host Cube port if customized. Start Web as above. Cube models under `examples/complete-journey/cube/model/` are mounted directly into Cube. Keep Compose commands in the example directory so its `.env` settings load consistently.

The sample's PostgreSQL stores source data, not Runs. The native API uses its own SQLite database and does not automatically share the container API's Run history. Recipes live in the specified folder. Do not commit local datasets or credentials.

For dbt development, use an existing dbt Semantic Layer environment and the [official API connection](dbt.md). The adapter contract tests use mocked GraphQL responses; production verification requires real credentials.
:::

## Verify your change

```bash
make test
npm --prefix web run typecheck
npm --prefix web run build
```

For documentation, run `npm ci` and `npm run docs:build` in the repository root.
See [Testing](testing.md) for browser and live integration checks,
[Architecture](../ARCHITECTURE.md) for the code map, and
[Contributing](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md) for PRs.
