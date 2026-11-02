# Complete Journey procedure reuse comparison — preparation

The pilot uses the registered `benchmark.group_change` calculation and a saved
Recipe in `reuse-project`. The Method queries all department-by-brand groups
for each period before calculating the largest change; it does not query only
the selected branch. It requires complete retrieval; a bounded single-page
Cube response records query exhaustion, but does not prove source ingestion or
cross-query snapshot consistency. Multi-page retrieval remains unknown and is
refused by this Method.

## Reproduce the diagnostic pilot

Use this repository's development environment, a signed-in Codex CLI and a
local Complete Journey demo with Cube on port 4100. Hold the data and endpoint
fixed throughout the comparison. Start the experiment API in a separate
terminal; the credentials below are for the packaged local demo only:

```sh
DL_DEPLOYMENT_MODE=demo DL_ALLOW_SERVICE_CREDENTIALS=true DL_SOURCE_PROVIDER=cube \
  CUBE_API_URL=http://127.0.0.1:4100/cubejs-api/v1 CUBE_INSTANCE=journey \
  CUBE_API_SECRET=local-quickstart-secret-change-me-0123456789 \
  DL_DATABASE_URL=sqlite:////private/tmp/dl-reuse-benchmark.db \
  DL_METHOD_ASSETS_DIR=/private/tmp/dl-reuse-methods \
  .venv/bin/decision-layer serve --project examples/complete-journey/evals/reuse-project --port 8127 --api-only
```

In another terminal, use unique output directories:

```sh
.venv/bin/python examples/complete-journey/evals/codex_pilot.py --task sales --output /private/tmp/dl-pilot-sales
.venv/bin/python examples/complete-journey/evals/codex_pilot.py --task campaign --output /private/tmp/dl-pilot-campaign
```

Each command runs Cube and Decision Layer in that order with fresh sessions and
the CLI default model, which is not a pinned benchmark model. Supply `--model`
with an account-supported exact model ID for reproducibility. These calls consume
Codex usage. Review transcripts for sensitive metadata before publishing them.
Stop the experiment API after the run.

## Conditions

Use the same frozen Complete Journey data, Cube catalog, model, effort and
limits. Compare (1) `cube_baseline.py` with the procedure below in the prompt,
where Codex writes and executes its own Python using standard libraries, and
(2) Decision Layer MCP with an equivalent saved Recipe and registered Method.
The baseline's generic CSV export only retrieves Cube data and does not contain
OLS or task-specific calculations. It has no Decision Layer code. This is a
bundle comparison, not an isolated estimate of the effect of Recipes. The
adapter is not an official Cube MCP. Never commit a token or the original dataset.

## Procedure

Compare total receipts and units over two complete specified months. For every department
calculate current minus previous receipts, treating an absent group as zero only
when the query proves the groups were completely retrieved. Select the largest
absolute change, preserving its sign; if exactly tied ask the user. Compare the
selected department by brand and units for both periods. Report both periods, values,
selection, evidence and limitations. Receipts are not profit, and differences
do not establish causality. Do not invent unavailable regions.

## Cases and grading

The candidate prompts in `reuse-scenarios.json` require independently checked
SQL results before the protocol can be frozen. The first pilot's reference SQL
is in `july-august-reference.sql`. Check correct semantic refs,
complete group retrieval, both period totals and department/brand values, plus
appropriate clarification and limitations. Review tool traces and answers; a
numeric match alone is not a pass. Ask predetermined identical follow-ups across
arms. Run a separate synthetic tie test and report it separately.

Randomize order, use fresh sessions, keep failures and report per-question
results. Record input, output, cache creation/read tokens, estimated CLI cost,
elapsed time and the number of correction prompts. Version the data, Recipe,
model and scripts. Authoring and infrastructure costs are excluded from the
per-run comparison and should be measured separately.
