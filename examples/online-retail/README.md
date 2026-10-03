# Online Retail II example

A reproducible, real-data example for trying Decision Layer and testing Method contributions. It is separate from the [synthetic ecommerce example](../ecommerce/README.md), which still covers joins and planted effects. This example covers time comparisons, drill-downs, invoice-versus-line grain, cancellations, missing customer identifiers, and questions that must not be answered from the available data.

The source is [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii), Daqing Chen (2012), DOI [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). It contains 1,067,371 invoice lines dated 2009-12-01 through 2011-12-09. This checkout does **not** redistribute the source workbook. The importer downloads the official archive, checks its SHA-256, and caches it in a Docker volume. If the upstream file changes, the import stops until someone reviews and updates the pin.

## Start

From this directory:

```bash
docker compose up -d --build
docker compose run --rm import python verify.py
```

The first start downloads about 44 MB and imports about 1.1 million rows; allow a few minutes. Open [Decision Layer](http://localhost:3000), or inspect the [API](http://localhost:8000/docs). The example runs Postgres, Cube, the Decision Layer API and Web separately; Cube is an external semantic provider, not part of Decision Layer's core. Host ports can be changed with `WEB_PORT`, `API_PORT`, `CUBE_PORT`, and `POSTGRES_PORT`, for example:

```bash
WEB_PORT=3012 API_PORT=8012 CUBE_PORT=4012 docker compose up -d --build
```

For an offline install, download the official UCI ZIP once as `data/online-retail-ii.zip` before starting. The importer still checks the pinned checksum. Source files under `data/` are Git-ignored. `docker compose down` stops the example without deleting imported data or Runs; do not use `down -v` if you want to keep them.

For a direct-SQL baseline, Postgres is bound only to `127.0.0.1:5433` (override with `POSTGRES_PORT`). Use database `retail`, user `retail_reader`, password `local-read-only`. That role has `SELECT` on the source lines and no table-write grant. These are public-example credentials, not a production security pattern.

The default connection uses a **local-development-only** Cube secret and shared service identity. Keep these ports on localhost; this is not a production authentication example. The `recipes/` directory is deliberately empty so you can ask an MCP question without a Recipe first.

## Try a question

In the Web, open the metric catalog and inspect **Positive sale value (GBP)**. It counts only positive, non-cancellation invoice lines; it is not profit or net revenue. Ask an MCP client:

> In March 2011, what was the positive sale value outside the United Kingdom, and which country had the highest value? Show the analysis steps and evidence.

Install the adapter from the repository root with `pip install -e '.[mcp]'` and configure your MCP client to launch `decision-layer-mcp` with `DL_API_URL=http://localhost:8000` (or your overridden API port). The local example does not require a caller token. After the answer, open **Runs** in the Web: the question, selected Methods, each step's purpose, result charts and query evidence should be in one Run. A Run remains exploration until you deliberately review it as a Recipe draft.

The deterministic MCP protocol check does not use an LLM and does not claim that an AI selected the right Methods:

```bash
DL_RETAIL_API_URL=http://127.0.0.1:8000 pytest -q -s tests/provider/test_online_retail_live.py
```

Run that command from the repository root with the development dependencies installed. It requires an empty `recipes/` directory. For Recipe authoring, copy `templates/sales-change.yaml` into `recipes/`, refresh the Web, and inspect or edit the resulting procedure. That template is **not** included in the Recipe-free test.

## Reference questions

[`evals/cases.json`](evals/cases.json) contains nine public questions, independent SQL reference answers and important interpretation limits. The importer image runs [`evals/verify.py`](evals/verify.py) against Postgres to check seven numeric answers. Two additional cases require an explicit limitation: profit cannot be calculated without costs, and transactions alone cannot establish a causal effect.

| Question | Verified reference | Important boundary |
| --- | --- | --- |
| February to March 2011 sales | GBP 523,631.89 to 717,639.36 | 28 versus 31 days; per-day change is 23.79%, not the raw 37.05% |
| Top non-UK country in March | Netherlands, GBP 22,416.49 | Source country is the customer's country |
| March cancellation invoice share | 318 / 1,983 = 16.0363% | Count distinct invoices, not invoice lines |
| March lines without customer ID | 8,926 / 36,748 = 24.2898% | Missing IDs are not distinct customers |
| March invoices versus lines | 1,983 invoices versus 36,748 lines | Different grains; they are not interchangeable |
| December 2011 full month | Latest source date is December 9 | Do not call the partial month complete |

The [evaluation protocol](evals/PROTOCOL.md) explains how to compare a direct analysis, Cube plus Methods, and Cube plus Methods and a Recipe. **No improvement percentage is claimed yet.** These public cases are functional regression checks, not an unseen benchmark. The source is one denormalized transaction table and has no cost, delivery, experimental assignment or credible causal treatment data. Keep using the synthetic ecommerce example for join and causal Method tests.
