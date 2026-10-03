# Evaluation protocol, not results

The public [`cases.json`](cases.json) checks that this pinned dataset and its reference answers do not drift. It is intentionally visible to contributors and **cannot** serve as a blind benchmark. A performance claim needs additional questions and independent review before publication.

## Conditions

Run the same natural-language questions with the same AI model and version, temperature, tool/time budget, prompt language, and read-only data permissions. Randomize condition order and repeat each question. Record the complete transcript, tool calls, Run IDs, model settings, elapsed time and costs.

| Condition | Available context and tools | What it isolates |
| --- | --- | --- |
| A: direct analysis | The example's `retail_reader` account on read-only Postgres, its raw schema and the same source documentation | Ungoverned baseline |
| B: semantic + Methods | Cube semantic catalog and Decision Layer MCP Methods, no Recipes | Contribution of governed definitions, contracts and validation |
| C: semantic + Methods + Recipe | Everything in B plus a reviewed Recipe file | Incremental value of reusable procedure |

The comparison is of **workflows**, not LLM models. A versus B changes both semantic context and execution contracts, so it must not be described as the isolated effect of Recipes. B versus C is the relevant Recipe comparison. Do not give one condition reference answers or evaluation-specific hints that the others lack. Keep all database credentials read-only and isolated from production data.

## Questions and grading

Extend the set to at least 30 independently written business questions before a quantitative README claim. Cover straightforward values, period-length differences, country and item drill-down, cancellation versus sale semantics, invoice versus line grain, missing customer IDs, incomplete periods, unsupported profit/margin, and unjustified causal questions. Keep a development set separate from a reviewer-held validation set. Public questions are for regression, not the final held-out score.

Grade each answer on these separate axes:

1. Numeric result against reviewed reference SQL, with an explicit tolerance.
2. Correct metric, filters, period, grain and denominator.
3. Required limitations, warnings and justified refusal.
4. Unsupported causal or business assertions (a critical failure).
5. Repeatability of the path and answer, tool calls, time and cost.

Use two reviewers for ambiguous interpretations and keep disagreement notes. A wrong confident answer is worse than an explicit inability to answer. Report per-question results and uncertainty (for example, paired bootstrap intervals), not only one aggregate percentage. Preserve failures and raw transcripts. Source SQL reference queries are an independent oracle, not instructions given to the evaluated agent.

## Publishing results

Only after completing the experiment, add a compact table to the root README with the dataset pin, number and split of questions, model/client versions, three conditions, repeat count, scoring rubric, uncertainty, date, exact reproduction commands, failures and limitations. Do not reuse the synthetic ecommerce experiment in ADR-032 as evidence of general real-data improvement. Do not imply this single dataset proves performance across domains or causal Methods.
