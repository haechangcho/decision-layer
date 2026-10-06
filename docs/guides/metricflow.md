# Local dbt example

For your organization's existing dbt platform, use [dbt Semantic Layer](dbt.md). This page covers the bundled local example and its development runtime.

The local example runs dbt MetricFlow through a small HTTP gateway. MetricFlow compiles and executes the governed queries; the same Decision Layer Methods, Recipes, Runs and MCP tools work above it.

This integration currently targets **dbt Core + MetricFlow + PostgreSQL**. It is not a dbt Cloud GraphQL endpoint. Other warehouses require adapter-specific verification before claiming support.

## Try the example

From the repository root:

```bash
cd examples/complete-journey
docker compose -f compose.yaml -f compose.dbt.yaml up -d --build --wait --wait-timeout 900
```

This starts the dbt example with PostgreSQL, dbt setup, MetricFlow, API and Web. Cube is a separately selected example using the same source tables. The dbt setup task creates views in `journey_dbt`; it does not reload or copy the source dataset. A fresh installation selects MetricFlow automatically.

1. Open [Source settings](http://localhost:3000/sources).
2. Choose **dbt MetricFlow**. The example fills in `http://metricflow:4100`, instance `journey`, and local anonymous authentication.
3. Select **Test connection**, then **Save settings**.
4. Open Metrics or ask your connected MCP client to discover the current catalog and analyze it.

The browser-facing gateway address is `http://localhost:4100`. The API container uses `http://metricflow:4100`. Switching back to Cube preserves its saved connection. One connection is active at a time; a single query cannot mix providers. Recipes keep their original fully qualified semantic references and must be explicitly rebound to a different provider. Existing Runs retain their recorded results and provenance; visibility follows their recorded owner and access rules.

The dbt example defines transactions, products, households, campaign descriptions, campaign contacts and coupon redemptions. It exposes receipts, units, baskets, transaction counts, coupon-line rates, campaign counts, contact counts and redemption counts. Foreign entities connect each fact to its applicable product, household or campaign model. Campaign contacts use campaign start date, not a fabricated contact timestamp. Household definitions have no event date; the example does not fabricate one to expose a standalone time-based household-count metric.

Each analytical model has a SQL file and a YAML file under `examples/complete-journey/dbt/models/`. SQL creates the queryable view; YAML declares entities, dimensions and metrics. `sources.yml` locates the raw tables. The raw coupon-product and promotion bridges stay outside both providers' analytical models to avoid multiplying transaction rows.

## Run against your own dbt project

Use a separate Python 3.12 environment so dbt dependencies do not constrain the API server:

```bash
python3.12 -m venv .venv-metricflow
.venv-metricflow/bin/pip install -e '.[metricflow]'
export DBT_PROJECT_DIR=/absolute/path/to/dbt-project
export DBT_PROFILES_DIR=/absolute/path/to/dbt-profiles
export DL_METRICFLOW_INSTANCE=production
export DL_METRICFLOW_TOKEN=your-gateway-access-token
.venv-metricflow/bin/uvicorn decision_layer.semantic.providers.metricflow.gateway:create_gateway \
  --factory --host 127.0.0.1 --port 4100
```

Build your dbt models first. The gateway uses the profile's default target; use a read-only warehouse role. Point Sources at the gateway, use the matching instance, and enter its access token. In Docker, use a reachable service hostname or `host.docker.internal`, not the container's own localhost.

The gateway token authorizes one shared warehouse profile. It does not implement per-person row permissions or interpret authentik/JWT claims. Deployments requiring those controls must enforce them at the semantic gateway/warehouse boundary. Do not expose the anonymous example gateway publicly. Warehouse credentials and dbt project files stay with the gateway; Decision Layer receives catalog metadata and bounded datasets.

## Metadata and supported analysis

Existing semantic models need no Decision Layer-specific `meta`. The adapter discovers queryable dimensions from MetricFlow itself and reads labels, descriptions and aggregations from the native semantic manifest. Native `count` metrics identify their own count; native `ratio` metrics expose numerator and denominator through `type_params`. Custom `config.meta.decision_layer` is not used to assign analytical semantics.

A derived calculation is not automatically treated as a statistical proportion. The example preserves the existing percentage calculation and its values without adding annotations or guessing its denominator. Drilldown, trend and descriptive peer comparisons remain available. Confidence intervals, sample-size filtering and matched comparisons require confirmed sample semantics; an unavailable count is not replaced with a nearby count metric. The example's derived coupon-line rate therefore cannot run CEM and returns a clear refusal rather than an unsupported statistical answer.

Drilldown, trend, peer comparison and categorical-condition CEM use aggregate queries. Entity-level extraction is currently unavailable and fails explicitly. Unsupported filters/date bases also fail rather than falling back to raw SQL. The gateway accepts typed dataset requests, not caller-supplied SQL or code. Queries are capped at 50,000 rows and retain native MetricFlow requests and optional compiled SQL.

## Verify parity

With both services running, from the repository root:

```bash
DL_METRICFLOW_TEST_URL=http://127.0.0.1:4100 \
  .venv/bin/pytest tests/provider/test_metricflow_live.py -q
```

This compares three descriptive Methods through Cube and MetricFlow and verifies that CEM fails closed when sample semantics are unavailable. It tests provider compatibility, not whether observational data identifies a causal effect.
