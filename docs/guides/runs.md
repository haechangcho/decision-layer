---
title: Runs and evidence
description: Understand a result, inspect how it was produced and reuse the procedure.
---

# Runs and evidence

A Run records one executed analysis, whether started from Web, REST, Python or MCP. It keeps the original question when supplied, the selected Method for each step, semantic references, applied settings, results, validation and executed queries.

## Read a result

### Analysis period

An omitted or null period waits for a choice; it no longer means all data.
Pass `scope.date_range` for explicit ISO dates, or `scope.period: {mode: all}`
for an explicit all-period request. Server policy must allow the latter.
Relative defaults can use `{mode: relative, preset: last_complete_month, timezone: UTC}`
or `{mode: relative, preset: last_n_days, days: 30, timezone: UTC}`. Rules resolve
at execution time; the actual dates and reported selection source remain in the Run.

Web asks inline when a period is needed. MCP uses `set_run_scope`; REST uses
`PUT /runs/{id}/scope` with `scope` and the latest `base_revision`. A waiting
execution continues in the same Run. Once analysis has started, use a new Run
to change its period. Source labels from AI clients are not authenticated approval.

Operators configure `DL_EXECUTION_POLICY` as JSON. The default disallows all-period
execution, limits ranges to 366 days, asynchronous execution to 120 seconds,
queries to 30 and result rows to 50,000. The bundled example opts into all-period
queries and allows 1,096-day ranges. These limits do not estimate warehouse cost
or guarantee cancellation of provider queries. Cooperative application deadlines
also do not forcibly interrupt synchronous CPU work. Native estimates, cancellation
and distributed budgets are future work.

![Run review interface with illustrative test values](../assets/run-review.png)

The screenshot uses illustrative test values, not benchmark results.

Open **Runs** in the [local Web app](http://localhost:3000/runs). Select a record to see:

1. The question and recorded conclusion at the top.
2. The analysis path, from governed metric to the Methods used.
3. The selected step's result and chart, followed by its table.
4. **Applied settings**, **Queries** and **Sources** in adjacent tabs.

The step purpose describes what the caller intended to check; it is not a validated finding. The graph shows execution order, not a claim that one step caused another.

## Reuse or remove a record

For a completed analysis, **Register as Recipe** saves immediately without a dialog. Group targets default to runtime selection; previous winners are not fixed defaults. **Edit before saving** opens the candidate in the normal Recipe editor for custom settings. Review the question, semantic objects, limits and warnings before your team relies on it.

The owner can delete a Run from the list or its detail page after confirming. This removes its results, queries and validation evidence. An active Run can be deleted after its job finishes. A Recipe already registered from that Run remains a separate file.

A calculated step rejected by analytical validation can still be saved as a procedure.
Saving does not approve its findings or relax thresholds. Re-execution stops if validation
fails again; a later exploratory comparison is not an automatic fallback branch.
Input-waiting steps and refusals without a calculated output must be edited or excluded.

## Access and limits

Runs belong to the caller identity accepted by Cube. A shared reader must still have semantic access to the referenced objects. In the local sample, Web and MCP use one development service identity; production authentication and author roles require a separate deployment decision.

Next: [create a Recipe](./recipes.md) or [connect an AI client](./mcp.md).
