# Reuse benchmark pilot — 2026-10-14

**This pilot found no token, cost or latency savings from Decision Layer.** A strong
model following detailed instructions through a small Cube MCP answered these simple
questions correctly and used fewer resources. This is a diagnostic result, not a launch claim.

## Results

Three synthetic month questions × three repeats × two conditions = 18 live trials.
Both conditions used `claude-opus-4-8`, medium effort, the same detailed procedure,
fresh client sessions, and the same governed Cube data. Values below are medians
across nine trials per condition.

| Measure | Semantic MCP + instructions | Decision Layer + saved Recipe |
| --- | ---: | ---: |
| Reported total tokens, including cached reads | 16,726 | 143,704 |
| Uncached input tokens | 8 | 10 |
| Cache creation tokens | 6,730 | 19,419 |
| Cache read tokens | 8,836 | 121,230 |
| Output tokens | 1,152 | 2,333 |
| CLI estimated cost per trial | $0.1006 | $0.3080 |
| Wall time | 17.23 seconds | 33.41 seconds |
| MCP calls | 3 | 5 |
| Numeric screen passed | 9/9 | 9/9 |
| March tie: no regional query before user choice | 3/3 | 3/3 |

Median paired changes were **+764.7% tokens, +199.2% estimated cost, and +97.1%
wall time** for Decision Layer. Paired changes are computed for matching month/repeat;
they differ from ratios of the aggregate medians. Component medians need not sum to
the total median. Total estimated cost across all 18 trials was $3.5561.

Token totals sum uncached input, cache writes, cache reads and output across requests;
they are not unique context size. Cache tokens and output tokens have different prices.
CLI costs are list-price estimates, not a subscription invoice. Wall time includes
client and MCP startup, model latency and tool execution.

## What quality review actually established

January's unique leader was Home (6,200; North 3,720 / South 2,480). February's leader
changed to Grocery (6,720; North 4,032 / South 2,688). March tied at 3,720 each.
Both conditions produced these expected numbers and asked for a choice in March.
Direct SQL checks independently verified the fixture totals. Tool traces confirmed
all three baseline March trials queried only departments, while all three Recipe
trials recorded `needs_input` and zero queries for the regional step.

**9/9 numeric passes does not mean 9/9 fully correct answers.** Transcript review found
an unsupported minimum-sample-size claim in `march-0-recipe`, despite the result's
explicit warning that the check was not applied. That answer later contradicted itself
with the correct caveat. Three Recipe answers also used dollar signs even though the
semantic metric specified only example currency units. Execution validation does not
by itself guarantee faithful LLM narration. Review was performed by the implementation
assistant, not an independent human reviewer.

Decision Layer additionally persisted versioned Recipe references, Run steps,
validation and evidence. These are inspectable product outputs; this experiment did
not measure their business value or show that the baseline could not implement them.

## Scope and reproducibility

This is a **product-bundle comparison**: a transparent custom Cube MCP with two tools
versus Decision Layer's ordinary MCP with 20 tools. It does not isolate the causal
effect of Recipes, and it is not an official Cube/vendor MCP benchmark. Procedure
instructions were identical. A Recipe already existed, so setup, authoring, review,
initial Recipe creation and infrastructure costs are excluded from both trial totals.
There is no positive per-reuse saving from which to calculate amortization.

Trials ran sequentially in seeded randomized order on one machine. User/project
settings, personal hooks and slash-command skills were disabled, and both MCP servers
were checked before measurement. Three public cases and one model are too small to
support claims about unseen schemas, complex investigations, production reliability
or general analytical accuracy. Shared cache/server state and network latency remain
sources of variation. This was a dirty development checkout, not a released revision.

Earlier attempts were excluded because one shared a rebuilding demo environment and
another had a baseline MCP import failure. No metrics from those attempts appear here.
The final batch used an isolated Compose project and all 18 trials are retained.

- [Protocol and reproduction commands](https://github.com/haechangcho/decision-layer/tree/main/examples/quickstart/evals)
- [Per-trial metrics CSV](https://github.com/haechangcho/decision-layer/blob/main/examples/quickstart/evals/pilot-2026-10-14/metrics.csv)
- [Sanitized answers and tool transcripts](https://github.com/haechangcho/decision-layer/blob/main/examples/quickstart/evals/pilot-2026-10-14/transcripts.json)
- [Review findings and environment](https://github.com/haechangcho/decision-layer/tree/main/examples/quickstart/evals/pilot-2026-10-14)

These evidence files are included in this working tree; GitHub links become available
when the changes are published. Sanitized transcripts omit thinking and client initialization
metadata. They preserve tool arguments, tool responses and answer text.

## Next actions and acceptance criteria

1. **Reduce repeated MCP payloads.** Return concise execution status, result, warnings
   and evidence references; fetch full specs/provenance on demand. Keep the same
   canonical Run and validation model. Acceptance: identical results and warnings,
   lower measured payload and token usage on this frozen protocol.
2. **Reduce unnecessary tool discovery.** Measure schema cost and redundant
   list/search calls before changing the exposed tool surface. Acceptance: fewer
   calls without hiding required discovery or changing baseline instructions.
3. **Prevent unsupported narration.** Preserve explicit validation-not-applied and
   metric-unit fields in concise outputs; add regression cases for the observed
   minimum-count and currency errors. Acceptance: no such claims in reviewed reruns.
4. **Run the same paired benchmark after those changes.** Keep current evidence,
   include failed trials, and publish before/after metrics. Do not advertise savings
   unless the measured result supports them.
5. **Measure the actual reuse thesis separately.** Add held-out multi-step procedures,
   changed leaders, missing bindings, ambiguous groups and incompatible inputs; count
   silent wrong execution, manual corrections, provenance completeness and authoring
   cost. Hold data/model/instructions fixed. Report where detailed instructions are
   already sufficient, not only cases that favor the product.
