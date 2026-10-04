# Evaluate analysis quality

Public sample questions are regression checks, not a blind benchmark. Complete Journey is observational data, not causal ground truth. Do not claim an accuracy improvement from passing its known reference cases.

## Actual AI-client trial

Start the [sample](../../examples/complete-journey/README.md), install the MCP adapter and sign in to Claude Code. From the repository root:

```bash
DL_API_URL=http://127.0.0.1:8000 .venv/bin/python evals/run_eval.py \
  examples/complete-journey/evals/scenarios.json --repeats 3
```

Use your actual API port. This invokes a real AI client and consumes its usage allowance; it is not part of CI. The runner records tool calls, answers and heuristic checks under the sample's ignored `evals/results/` directory. Human review is still required for unsupported interpretation and correct population/denominator. These public questions are development checks, not evidence of general analytical accuracy.

## Comparative experiment

Run the same independently reviewed questions with the same model/version, language, tool/time budget and read-only permissions. Randomize condition order and repeat questions. Compare:

| Condition | Available context and tools |
| --- | --- |
| Direct analysis | Read-only source database, schema and publisher documentation |
| Semantic + Methods | Cube catalog and registered Decision Layer Methods |
| Semantic + Methods + Recipe | The same catalog and Methods plus a reviewed Recipe |

The runner above covers Decision Layer execution, not a complete direct-SQL baseline. Comparing the first two conditions changes both semantics and execution contracts; it does not isolate the effect of Recipes. Compare the latter two to assess reusable procedures.

Keep reviewer-held validation questions separate from public development questions. Grade numeric results against independent SQL, semantic references, period, grain, denominator, warnings, justified refusal and unsupported causal claims. Include campaign selection, missing demographics, relative source dates, unequal population sizes and retailer receipts versus profit. A confident wrong answer is a critical failure.

Before publishing quantitative claims, use a sufficiently broad reviewed question set, retain complete transcripts and Run IDs, and report client/model versions, conditions, repeat count, scoring, uncertainty, time, cost, failures and limitations. Do not provide reference answers to the evaluated agent or imply one retail dataset establishes causal accuracy across domains.
