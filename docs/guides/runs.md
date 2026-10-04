---
title: Runs and evidence
description: Understand a result, inspect how it was produced and reuse the procedure.
---

# Runs and evidence

A Run records one executed analysis, whether started from Web, REST, Python or MCP. It keeps the original question when supplied, the selected Method for each step, semantic references, applied settings, results, validation and executed queries.

## Read a result

![Run review interface with illustrative test values](../assets/run-review.png)

The screenshot uses illustrative test values, not benchmark results.

Open **Runs** in the [local Web app](http://localhost:3000/runs). Select a record to see:

1. The question and recorded conclusion at the top.
2. The analysis path, from governed metric to the Methods used.
3. The selected step's result and chart, followed by its table.
4. **Applied settings**, **Queries** and **Sources** in adjacent tabs.

The step purpose describes what the caller intended to check; it is not a validated finding. The graph shows execution order, not a claim that one step caused another.

## Reuse or remove a record

For a completed analysis, **Register as Recipe** saves the recorded procedure with its settings. **Edit before saving** opens the candidate in the normal Recipe editor. Review the question, semantic objects, limits and warnings before your team relies on it.

The owner can delete a Run from the list or its detail page after confirming. This removes its results, queries and validation evidence. An active Run can be deleted after its job finishes. A Recipe already registered from that Run remains a separate file.

## Access and limits

Runs belong to the caller identity accepted by Cube. A shared reader must still have semantic access to the referenced objects. In the local sample, Web and MCP use one development service identity; production authentication and author roles require a separate deployment decision.

Next: [create a Recipe](./recipes.md) or [connect an AI client](./mcp.md).
