# Run the Method test scenarios yourself

Run from the repository root. Each CLI checks its result and exits nonzero on mismatches. The environment below installs all libraries; statistical cases are not skipped.

## 1. Install and verify all known answers

```bash
python3.11 -m venv .venv-method
.venv-method/bin/python -m pip install -c examples/methods/statistics/constraints-py311.txt -e '.[dev,stats,dowhy,econml]'
.venv-method/bin/python -m examples.methods.scenarios --all
.venv-method/bin/python -m examples.methods.scenarios.failures --all
```

| case | Pattern | Queries | Independent expected values |
| --- | --- | --- | --- |
| by_group | A | 1 | 30, 20, 10 |
| trend | A | 1 | 20, 30 |
| period | B | 2 | 10 |
| peer | B | 3 | 4, 6 |
| ols | C | 1 | 2, 3 ± 0.15 |
| dowhy | C | 1 | 2 ± 0.15 |
| econml | C | 1 | 2 ± 0.15 |
| unit-change | D | 2 | 3, 5 |
| unit-change-wide | D | 2 | 3, 5 |
| did | E | 1 | 3 |
| did-split | F | 2 | 3 |
| mixed | G | 2 | 60; 10; 30; 3 |

Use `--case peer` instead of `--all` to isolate a case. `scenarios.py` holds independent full requests; `methods.py` holds authored functions; `verify()` checks answers. Output exposes aliases and comparison units. OLS values are treatment/baseline coefficients; mixed values are aggregate/min/max/unit count. The DoWhy/EconML target of 2 comes from the known generating process, not a ground truth for observational sample data.

```bash
.venv-method/bin/python -m examples.methods.scenarios --case peer
.venv-method/bin/python -m pytest -q tests/examples/test_scenarios.py tests/unit/test_method_authoring.py tests/unit/test_advanced_methods.py
```

## 2. Verify failures and refusals

| case | Attempts | Expected outcome |
| --- | --- | --- |
| wrong-kind | 0 | InvalidBinding |
| wrong-query | 1 | AssertionError |
| no-period | 0 | Refused |
| query-budget | 1 | refused |
| provider-failure | 2 | ProviderError |
| row-overflow | 1 | refused |
| non-primary-unit | 0 | InvalidBinding |
| missing-data | 1 | refused |
| duplicate-unit | 1 | refused |
| missing-cohort | 2 | refused |
| unsupported-option | 0 | InvalidBinding |
| duplicate-panel | 1 | refused |
| overlapping-windows | 0 | refused |

Wrong kinds, missing periods and unsupported options fail before queries. Budget refusal preserves earlier successes. Provider failures re-raise exceptions; inspect failed labels/specs in `session.last_trial.attempts`. Answer mismatches are never converted into analytical success.

## 3. Run against the existing Complete Journey data

This is the dunnhumby Complete Journey PostgreSQL/Cube sample built with reference to a Databricks example. It is not a Databricks backend integration test. No new download or volume deletion is needed. Follow [sample connection](quickstart.md), then ensure Cube reads the **current checkout’s model**. Services started from another checkout do not automatically use this code.

The new `campaign_panel` is a native Cube view using UNION ALL over existing eligible campaign-household pre/post 30-day values. Refresh its model and public observation key; no DB-row migration is needed. Dates are window starts, not actual treatment receipt dates.

If the existing local demo uses Compose project `decision-layer-cube`, retain its PostgreSQL and refresh **only Cube** from the current checkout. Match custom project/port settings first. This does not update the existing API/Web.

```bash
cd examples/complete-journey
docker compose -p decision-layer-cube -f compose.yaml -f compose.override.yaml up -d --no-deps cube
cd ../..
```

```bash
export DL_JOURNEY_CUBE_URL=http://127.0.0.1:4000/cubejs-api/v1
export DL_JOURNEY_DATABASE_URL='postgresql://journey_reader:local-read-only@127.0.0.1:5433/journey'
.venv-method/bin/python -m examples.methods.scenarios.journey --all --verify-sql
.venv-method/bin/python -m examples.methods.scenarios.journey --case did --verify-sql
.venv-method/bin/python -m examples.methods.scenarios.journey --case did-split --verify-sql
.venv-method/bin/python -m examples.methods.scenarios.journey --case dowhy
.venv-method/bin/python -m examples.methods.scenarios.journey --case econml
```

Use the URL above only for the local demo reader; replace server/user/token for other environments. SQL oracles run on a read-only connection. Methods do not gain a raw SQL execution path.

Expected: by_group, trend, period, peer, OLS, unit-change and mixed succeed and match independent SQL. Campaign 8 has 2,008 eligible observations. The OLS pre-sales coefficient is about 0.80675065; the mixed mean is about 186.39861554. The new two-period contrast reports an associational difference. DoWhy/EconML check observed support after extraction; no assumption checkbox is required.

The previous Journey experiment found a single/partitioned window contrast of about 5.45823535 matching SQL and inadequate fitted propensity support for campaign 8. That live result was not rerun for this refactor. The new APIs retain data checks and label assumptions unverified; they do not establish causality.

## 4. Execute the same implementation through the recorded API

This development bootstrap explicitly registers the four reviewed tutorial Methods. It runs on a separate port with empty memory storage and does not overwrite an existing server. Service credentials are used only for the local sample development mode.

```bash
export CUBE_API_URL=http://127.0.0.1:4000/cubejs-api/v1
export CUBE_INSTANCE=journey
export CUBE_API_SECRET=local-example-secret-change-me-0123456789
export DL_ALLOW_SERVICE_CREDENTIALS=true
export DL_DATABASE_URL=memory
.venv-method/bin/python -m uvicorn examples.methods.scenarios.server:create_app --factory --host 127.0.0.1 --port 8011
```

In another terminal, export the SQL URL and run:

```bash
.venv-method/bin/python -m examples.methods.scenarios.journey --api http://127.0.0.1:8011 --all --verify-sql
.venv-method/bin/python -m examples.methods.scenarios.journey --api http://127.0.0.1:8011 --case did --verify-sql
```

Use `run_id` with `GET /runs/{id}` to inspect canonical bindings, attempts, versions, validation and warnings. Web Run viewers and MCP `run_step` use the same RunEngine/Registry. There is no automatic function upload or separate executor. Stop the development server with Ctrl-C.

## 5. Edit and debug

Change `group_metric` order or limit; the full-spec fixture identifies the mismatched field. Put a breakpoint before the second peer call to observe all three requests in one function. Inspect attempts/queries/result in `session.last_trial`. `docs/tutorials/methods/query_scenarios.ipynb` imports the same functions and CLI verification helpers, with no duplicate implementation.

The existing data is sufficient for descriptive calculations, input mapping, joins/grain, multiple requests, extraction and failure paths. Known synthetic generating processes are needed for estimator accuracy. Real causal validation additionally needs treatment receipt times, assignment design, overlapping-campaign/interference review, unit-level period completeness and identification assumptions.
