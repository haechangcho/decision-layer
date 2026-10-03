# Example: ecommerce

A synthetic ecommerce domain for trying and testing Decision Layer end to end. The core does not use
any of it (ADR-028); it shows how an organisation plugs in its own semantic model and procedures.

```bash
cd examples/ecommerce
docker compose up --build        # Postgres + Cube OSS + Decision Layer API + web
open http://localhost:3000       # web UI   (ports: WEB_PORT, API_PORT, CUBE_PORT)
curl localhost:8000/health       # API      (docs at /docs)
```

The local-only connection screen uses `local-demo-change-me` as its source-admin key. Set
`DL_SOURCE_ADMIN_TOKEN` before starting Compose to replace it. Recipe editing has no separate key; keep this demo private. The example's Cube URL and service
secret are fixed by environment variables, so the UI labels them as locked. For a non-demo deployment,
set a private `DL_SOURCE_CONFIG_KEY` (Fernet key) before saving an API secret; never rotate or lose
that key without first replacing the encrypted secret.

Recipes are saved as immutable `name@version.yaml` files in the mounted `recipes/` directory. The
Compose mount is writable so new versions remain in the checkout and can be reviewed or committed.

| Path | What |
|---|---|
| `data/ecom.sql` | seeded synthetic data (orders, products, sellers, customers, deliveries, returns) with planted effects |
| `cube/model/` | Cube data model; ratio measures declare `meta.numerator` / `meta.denominator` |
| `recipes/` | Recipes: an investigation session, a sales-change pipeline, a two-level drill-down pipeline |
| `evals/scenarios.json` | model eval scenarios for `evals/run_eval.py` |
| `EXPECTED.md` | the answers the planted effects should produce |

Checks against this stack:

```bash
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 CUBE_API_SECRET=example-secret-change-me-0123456789 pytest -m cube
DL_API_URL=http://localhost:8000 python evals/run_eval.py examples/ecommerce/evals/scenarios.json   # needs the Claude Code CLI
```

Titles and descriptions in the model and recipes are Korean because the example was built for a Korean team;
Decision Layer's own messages follow the request language (English or Korean).

Postgres is pinned to 14.x: `random()` changed in PostgreSQL 15, and the expected answers depend on the seeded
sequence.
