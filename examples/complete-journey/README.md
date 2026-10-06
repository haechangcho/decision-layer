# Complete Journey

The multi-table retail example used by the linked [Databricks data preparation notebook](https://www.databricks.com/notebooks/segment-p13n/sg_01_data_prep.html), loaded into local PostgreSQL. Choose Cube or self-hosted dbt MetricFlow.
No Databricks account, Spark installation or manually issued local token is needed.

The dbt option includes a local gateway for this account-free example. To connect a company's existing dbt deployment, use the [official Semantic Layer API connection](../../docs/guides/dbt.md); the product does not require installing this example gateway there.

## Start

From the repository root:

```bash
cd examples/complete-journey
docker compose up -d --build --wait --wait-timeout 900
```

This starts the **Cube example**. For the **dbt example**, use instead:

```bash
docker compose -f compose.yaml -f compose.dbt.yaml up -d --build --wait --wait-timeout 900
```

Each option starts PostgreSQL, the selected semantic provider, API and Web. Open **http://127.0.0.1:3000/catalog**. The selected provider is configured automatically on a fresh installation; Recipes start empty. Existing saved connections take precedence: use [Sources](http://localhost:3000/sources) to select the new provider, test and save. Use only one example stack at a time because Web and API ports are shared.
See the [MetricFlow guide](../../docs/guides/metricflow.md) for dbt model layout and connection details.
First startup downloads the official 128 MB archive and streams all eight source tables into PostgreSQL.
The promotion table is large, so allow several minutes. Later starts reuse the cache and database.
For offline setup, place the original archive at `data/complete-journey.zip`; its checksum is still checked.

| Service | Image | Host port |
| --- | --- | --- |
| Web | Built from this repository | 3000 |
| API | Built from this repository | 8000 |
| Cube (Cube example) | cubejs/cube:v1.6.25 | 4000 |
| dbt MetricFlow (dbt example) | Built from this repository; dbt-metricflow 0.15.0 | 4100 |
| Source PostgreSQL | postgres:16.4 | 5433 |

If ports are occupied, copy `.env.example` to `.env` and change host ports.
Keep Compose commands in this folder. All ports bind to 127.0.0.1.
Both providers query with a SELECT-only source role; public credentials are local-development credentials.

## Model

Eight original tables: transactions, products, coded household demographics, campaign descriptions,
household campaign contacts, coupon-product mappings, coupon redemptions and store-week promotion placements.
An additional household key table is derived from transactions so missing demographics do not exclude shoppers.

The initial Catalog exposes transaction receipts, units, transaction-line count, basket count and coupon-line rate;
product department/brand, household codes and store identifiers; campaign contacts and redemption counts.
Both providers define the six analytical models: transactions, products, households, campaigns, campaign contacts and redemptions. Campaigns and redemptions are separate facts, not joined onto every transaction line.
The raw promotion and coupon-product bridge remain loaded for later modeling; they are not blindly joined to sales.

The importer adds PostgreSQL `DATE` columns: `transaction_date`, `redemption_date`, `start_date` and `end_date`.
The source day indices are preserved. Day 1 maps to 2000-01-01 using a fixed example calendar, not the actual purchase year.
Transactions span **2000-01-01 to 2001-12-11**. Cube exposes these columns as time dimensions;
Web uses provider period suggestions when available. Calendar conversion details are documented here rather than repeated in every dimension description.
The official 2023 package has coded demographic fields; codes are not inferred to be actual ages/incomes.
Retailer receipts are not profit or necessarily customer out-of-pocket spend. Read [NOTICE](NOTICE.md).

## Ask through MCP

Install and connect using the [MCP guide](../../docs/guides/mcp.md), with `DL_API_URL=http://127.0.0.1:8000`.

> Over all available data, which product department has the largest retailer receipts? Break it down by brand and show the evidence.

> Compare the coupon-line rate of one store with the other stores in the same product department and with the overall accessible population.

> How did retailer receipts change between July and September 2001? Show the monthly trend and break it down by product department.

Use **Transaction date** for purchase-period questions. Campaign start/end and redemption dates describe separate events.
Open Runs to inspect the question, graph, settings and queries. **Register as Recipe** saves the completed procedure with its recorded settings; **Edit before saving** opens a candidate for changes first.

The dataset supports observational investigation, not a guaranteed campaign causal effect.
Do not equate coupon users with randomized treatment or condition on redemption to define a causal control group.
A causal Recipe needs pre-treatment covariates, explicit treatment/outcome windows, overlap and an identification argument.

## Verify and troubleshoot

```bash
docker compose run --rm --no-deps import python verify.py
docker compose logs --tail=100 import cube api
docker compose down
```

For dbt, use the same selected files for management commands:

```bash
docker compose -f compose.yaml -f compose.dbt.yaml logs --tail=100 dbt-setup metricflow api
docker compose -f compose.yaml -f compose.dbt.yaml down
```

To switch examples, stop the current stack with its `down` command, then start the other. This preserves the shared source database and Run volume. Test and save the selected connection in Sources if settings were previously saved.

The verifier reports independent SQL totals and checks a product join does not multiply lines.
`down` preserves named data/cache/Run volumes and local Recipe files; `down -v` deletes named volumes.
The importer records a digest and row counts transactionally; interrupted imports roll back rather than presenting partial data.
Existing volumes are upgraded on the next import without reloading or deleting source rows:

```bash
docker compose build import
docker compose run --rm --no-deps import
docker compose restart cube api
```

See [local development](../../docs/guides/development.md), [Method contribution](../../docs/guides/methods.md)
and [tests](../../docs/guides/testing.md). Keep the source data private to your environment; review publisher terms before redistribution.
