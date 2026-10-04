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
4. Set the inputs that matter to this procedure. Use the preview to check a step against Cube before saving.
5. Save a draft, review it, then publish it when it is ready for others to use.

The graph represents execution order and semantic bindings. It is not a general workflow engine or a causal graph. The advanced editor exposes the underlying YAML and full Method parameters when you need them.

## Start from a Run

An analyst or MCP client may have already performed the right investigation. Open its [Run](./runs.md) and select **Register as Recipe**. A completed Run with successful steps can become a Recipe with its metric bindings, step purposes, applied parameters, filters, period and Method versions preserved.

Choose **Edit before saving** to change the candidate first. Registration is an explicit action; exploration is not automatically approved as team procedure.

## Where Recipes live

Recipes are versioned YAML files under the configured Recipe directory. Runs and results live separately in the Run database. Deleting a Recipe leaves historical Runs intact; deleting a Run leaves any Recipe already registered from it intact.

The local Web editor saves Recipe files but does not create Git commits or pull requests. A team can mount a Git-managed Recipe directory and review file changes through its normal repository workflow. Application login and author roles are not yet implemented, so keep authoring endpoints on a trusted network.

Next: [execute and review a Run](./runs.md).
