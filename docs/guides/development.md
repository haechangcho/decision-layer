# Local development

Use **Python 3.11+**, **Node.js 22**, and Docker with Compose for live sample data. Docker-only users can stay with the [quickstart](../index.md).

## Install

From the repository root:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

From `web/`:

```bash
npm ci
```

## API

From the repository root:

```bash
mkdir -p data recipes
DL_RECIPES_DIR=./recipes DL_DATABASE_URL=sqlite:///./data/development.db \
  .venv/bin/uvicorn decision_layer.api.app:app --reload --port 8000
```

The API starts without Cube. Open **http://localhost:8000/docs** for REST contracts and `/health` for health. Configure a source through Web before live analysis.

## Web

In another terminal, from `web/`:

```bash
DL_API_URL=http://localhost:8000 npm run dev
```

Open **http://localhost:5210**. Web proxies to the API; it does not run a separate analysis engine. If port 8000 is occupied, change the API port and `DL_API_URL` in Web and [MCP](mcp.md).

## Sample source

From `examples/complete-journey/`, start only the data services:

```bash
docker compose up -d --build --wait postgres import cube
```

If the full sample is already running, first stop its API and Web with `docker compose stop api web` from that directory to free their ports. Do not stop unrelated stacks.

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

For dbt development, start its data services from the example folder instead:

```bash
docker compose -f compose.yaml -f compose.dbt.yaml up -d --build --wait postgres import dbt-setup metricflow
```

Start the native API from the repository root with `DL_DEFAULT_SOURCE_PROVIDER=metricflow`, `DL_DEFAULT_METRICFLOW_URL=http://localhost:4100`, `DL_DEFAULT_METRICFLOW_INSTANCE=journey`, `METRICFLOW_AUTH_METHOD=none` and `DL_ALLOW_SERVICE_CREDENTIALS=true`, along with the same Recipe and DB settings above. Use a separate Run database for a fresh provider default; saved connections otherwise take precedence. SQL and YAML live in `examples/complete-journey/dbt/models/`. After editing them, rebuild and run `dbt-setup`, then recreate `metricflow` using the same Compose files. See the [MetricFlow guide](metricflow.md).

## Code map

| Area | Location |
| --- | --- |
| Canonical models | `src/decision_layer/core/models.py` |
| REST surface | `src/decision_layer/api/app.py` |
| MCP adapter | `src/decision_layer/mcp/server.py` |
| Methods and registry | `src/decision_layer/methods/` |
| Recipe authoring | `src/decision_layer/recipes/` |
| Run execution and storage | `src/decision_layer/runs/` |
| Web routes and shared UI | `web/app/`, `web/components/` |

Next: [test a change](testing.md), [add a Method](methods.md), or [submit a contribution](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md).
