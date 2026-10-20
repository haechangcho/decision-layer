# Create a Recipe

A Recipe records a recurring analysis as a procedure. For example: find the highest-revenue product, then compare its revenue by region.

## Start from a metric

In the admin console:

1. Select a metric in **Metrics** and choose **Create Recipe**.
2. Add analysis steps and select each step's Method and inputs.
3. Choose **Check result** and review the result and validation.
4. Save a draft, then publish it.

The graph shows analysis order and input connections. **Code view** exposes detailed settings.

## Save an existing analysis

Choose **Register as Recipe** on a completed [Run](runs.md) to save its procedure. Choose **Edit before saving** to adjust the configuration first.

The next execution can request a new period or target instead of fixing the dates and products from the original analysis.

## Save how to choose, rather than the previous winner

Product A may lead revenue in January and product B in February.

Saving “analyze product A” selects A again. Saving **“find and analyze the highest-revenue product”** checks the ranking each time.

A tie or insufficient result asks for input rather than selecting a target automatically.

<details>
<summary>YAML for a previous step's selection</summary>

```yaml
params:
  drill_path:
    source: step
    step_id: by_group
    output: ranked_groups
    select: first
    project: path
```

`path` selects the full branch, `condition` selects the group, and `parents` selects parent conditions. For peer comparison, use `condition` for the subject and `parents` for peers.

This connection uses selection outputs declared by the Method. Failed or incomplete results cannot choose the next target.

</details>

## Reuse it with your team

Recipes are versioned YAML files. Results are recorded in separate Runs, so the same procedure can execute with different dates and inputs.

Manage project files in Git for team review. Saving in the admin console does not automatically create a Git commit.

See [Runs and evidence](runs.md) to inspect the inputs and queries behind each analysis.
