# Reuse benchmark pilot

Compare **a read-only Cube MCP with a detailed procedure** against **the Decision
Layer MCP with a saved executable Recipe**. Both conditions receive the same
system instructions and month question. This evaluates the product bundle, not
the isolated causal effect of Recipes.

## Protocol fixed before measurement

- One explicit model ID, medium effort, a new client session per trial.
- User/project settings, personal hooks and slash-command skills disabled.
- Three public synthetic cases: January, February and tied leaders in March.
- Three repeats per case and condition: 18 trials total.
- Sequential trials; seed 42 randomizes case and within-pair condition order.
- Identical per-trial limits: 20 turns, 300 seconds, $2 CLI budget cap.
- Check both MCP servers initialize and expose their tools before invoking a model.
- Do not provide reference answers to the evaluated model.
- Keep every trial, including wrong answers and timeouts. Do not report a failed
  MCP connection as an analytical quality or efficiency result.

The semantic baseline exposes native Cube catalog discovery and JSON metric
queries. It is a small transparent baseline, not an official vendor MCP benchmark.
Decision Layer exposes its ordinary MCP tools; no benchmark-only execution shortcut.

## Run in an isolated environment

Requires the development environment (`make setup`), a signed-in Claude Code CLI,
and Docker. Live model calls consume the signed-in account's allowance.

```bash
DL_DEMO_API_PORT=8101 BENCH_CUBE_PORT=4101 docker compose -p decision-layer-benchmark \
  -f examples/quickstart/compose.yaml \
  -f examples/quickstart/evals/compose.benchmark.yaml up -d --build --wait api
.venv/bin/python examples/quickstart/replay.py --api http://127.0.0.1:8101
DL_API_URL=http://127.0.0.1:8101 BENCH_CUBE_URL=http://127.0.0.1:4101/cubejs-api/v1 \
  .venv/bin/python examples/quickstart/evals/compare.py --model YOUR_EXACT_MODEL_ID --repeats 3
```

Do not run setup/rebuilds against the same Compose project while measuring.
Use the same two Compose files and project name with `down -v` to discard only
benchmark data after exporting evidence. The benchmark project has no Web service
unless explicitly started; walkthrough Web links are not used for grading.

## Measurement and review

Report uncached input, cache creation, cache reads and output separately. `total_tokens`
is their sum across model requests, including repeatedly read cached context. It is
not unique context size, and a cache token does not have the same price as an output
token. Cost is the CLI's reported list-price estimate, not a subscription invoice.
Elapsed time includes client/MCP startup, tool execution and model latency.

Numeric screening is deliberately labelled a screen. Read transcripts to check
period, selected department, regional totals, tie handling and unsupported causal
claims. For March, confirm no regional query ran before asking for input.
Also report whether Decision Layer preserved a Run, Recipe and evidence; those
extra outputs are not required from the plain metric-query baseline.

This is steady-state reuse: a Recipe is already available. Installation, human
review/authoring, initial Recipe creation and server infrastructure are excluded.
Do not call it an end-to-end cost reduction. If the setup cost is measured later,
calculate amortization only when per-reuse savings are positive.

The public three-month sample is tiny and known to developers. It does not support
claims about general analytical accuracy, unseen schemas, long investigations,
other models, causal inference or production reliability. Report regressions too.
Raw trial files can include local client metadata; review/redact before publication.
