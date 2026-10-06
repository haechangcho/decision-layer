---
title: Create a Recipe
description: Turn registered Methods and Cube metrics into a reusable analysis procedure.
---

# Create a Recipe

A **Method** performs one analytical task, such as a trend or drill-down. A **Recipe** records which Methods to run, with which governed metrics and settings, for a question your team asks repeatedly.

## Start from a metric

1. Open **Metrics** in the [local Web app](http://localhost:3000/catalog).
2. Select a metric and choose **Create Recipe**.
3. Add analysis steps to the graph. Choose a dimension for a drill-down or a measure for a trend, then review the proposed Method.
4. Select the required inputs and choose **Check result**. A period or runtime input is requested only when needed. Ranking and source rules remain in **Code view**, not the basic form.
5. Save a draft, review it, then publish it when it is ready for others to use.

The graph represents execution order and semantic bindings. It is not a general workflow engine or a causal graph. The advanced editor exposes the underlying YAML and full Method parameters when you need them.

## Start from a Run

Open a completed [Run](./runs.md) and select **Register as Recipe**. It saves immediately, without a configuration dialog. The default procedure reselects groups at execution time instead of remembering the previous winners. Recorded rules remain intact; matching semantic dimension paths connect to earlier registered selection outputs. If no earlier output can supply a target, the Recipe requires a typed runtime input with no fixed default. MCP callers provide those inputs when starting a Run; Web uses the same contract.

Explicit fixed Method policies remain fixed. Other analytical settings are retained. Run-specific dates and shared filters are not automatically fixed into the Recipe. Existing published Recipes are returned without being overwritten.

Choose **Edit before saving** to change the candidate first. Registration is an explicit action; exploration is not automatically approved as team procedure.

## Reuse a Rule, Not a Previous Winner

For “find the highest group, then compare its leading member,” the next execution must discover the winners again. A step can reference a previous declared selection:

```yaml
params:
  drill_path:
    source: step
    step_id: by_group
    output: ranked_groups
    select: first
    project: path
```

`path` uses the full branch, `condition` uses only the selected group, and `parents` uses its parent conditions. For peer comparison, use `condition` for the subject and `parents` for peers. Keep the Run's global filters separate so the overall population is not accidentally restricted to the branch.

Ordinary drilldown exports this selection independently of its displayed row limit. Empty, unsuccessful or truncated results cannot choose a winner. Ties ask for input; period-contribution drilldowns do not yet export ranked group selections. Old explicit `$steps` expressions remain supported but do not establish selection completeness.

Declare user-supplied values under `inputs` in the advanced editor and reference them with `{source: input, name: selected_group}`. The Web and MCP `start_run(inputs=...)` supply these typed values at execution. Runs retain both the requested rule and actual applied values. Re-registering the procedure preserves the rule; it does not freeze the last result.

## Where Recipes live

Recipes are versioned YAML files under the configured Recipe directory. Runs and results live separately in the Run database. Deleting a Recipe leaves historical Runs intact; deleting a Run leaves any Recipe already registered from it intact.

The local Web editor saves Recipe files but does not create Git commits or pull requests. A team can mount a Git-managed Recipe directory and review file changes through its normal repository workflow. Application login and author roles are not yet implemented, so keep authoring endpoints on a trusted network.

Next: [execute and review a Run](./runs.md).
