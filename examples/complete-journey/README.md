# Complete Journey

The multi-table retail example used by the linked [Databricks data preparation notebook](https://www.databricks.com/notebooks/segment-p13n/sg_01_data_prep.html), loaded into local PostgreSQL and Cube.
No Databricks account, Spark installation or manually issued local token is needed.

## Start

From the repository root:

```bash
cd examples/complete-journey
docker compose up -d --build --wait --wait-timeout 900
```

Open **http://127.0.0.1:3000/catalog**. Cube is configured automatically; Recipes start empty.
First startup downloads the official 128 MB archive and streams all eight source tables into PostgreSQL.
The promotion table is large, so allow several minutes. Later starts reuse the cache and database.
For offline setup, place the original archive at `data/complete-journey.zip`; its checksum is still checked.

| Service | Image | Host port |
| --- | --- | --- |
| Web | Built from this repository | 3000 |
| API | Built from this repository | 8000 |
| Cube | cubejs/cube:v1.6.25 | 4000 |
| Source PostgreSQL | postgres:16.4 | 5433 |

If ports are occupied, copy `.env.example` to `.env` and change host ports.
Keep Compose commands in this folder. All ports bind to 127.0.0.1.
Cube uses a SELECT-only source role; public credentials are local-development credentials.

## Model

Eight original tables: transactions, products, coded household demographics, campaign descriptions,
household campaign contacts, coupon-product mappings, coupon redemptions and store-week promotion placements.
An additional household key table is derived from transactions so missing demographics do not exclude shoppers.

The initial Catalog exposes transaction receipts, units, transaction-line count, basket count and coupon-line rate;
product department/brand, household codes and store identifiers; campaign contacts and redemption counts.
Campaigns and redemptions are separate facts, not joined onto every transaction line.
The raw promotion and coupon-product bridge remain loaded for later modeling; they are not blindly joined to sales.

**Important:** source DAY is relative. The model maps day 1 to 2000-01-01 for time queries, not an actual year.
The official 2023 package has coded demographic fields; codes are not inferred to be actual ages/incomes.
Retailer receipts are not profit or necessarily customer out-of-pocket spend. Read [NOTICE](NOTICE.md).

## Ask through MCP

Install and connect using the [MCP guide](../../docs/guides/mcp.md), with `DL_API_URL=http://127.0.0.1:8000`.

> Over all available data, which product department has the largest retailer receipts? Break it down by brand and show the evidence.

> Compare the coupon-line rate of one store with the other stores in the same product department and with the overall accessible population.

For a time query, explicitly use the mapped example dates and the transaction date dimension.
Open Runs to inspect the question, graph and results. Review selected steps as a Recipe draft before saving.

The dataset supports observational investigation, not a guaranteed campaign causal effect.
Do not equate coupon users with randomized treatment or condition on redemption to define a causal control group.
A causal Recipe needs pre-treatment covariates, explicit treatment/outcome windows, overlap and an identification argument.

## Verify and troubleshoot

```bash
docker compose run --rm --no-deps import python verify.py
docker compose logs --tail=100 import cube api
docker compose down
```

The verifier reports independent SQL totals and checks a product join does not multiply lines.
`down` preserves named data/cache/Run volumes and local Recipe files; `down -v` deletes named volumes.
The importer records a digest and row counts transactionally; interrupted imports roll back rather than presenting partial data.

See [local development](../../docs/guides/development.md), [Method contribution](../../docs/guides/methods.md)
and [tests](../../docs/guides/testing.md). Keep the source data private to your environment; review publisher terms before redistribution.
