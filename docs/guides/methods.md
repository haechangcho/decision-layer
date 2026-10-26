# Understand Methods

A Method is a reusable analysis. A **Python Method** executes a calculation; a **Skill Method** provides analysis instructions for AI.

## Default Methods

- **Metric lookup**: a Skill for querying metrics over selected dates
- **Group breakdown**: a Skill for inspecting groups and investigating a selected group
- **OLS regression**: a Python function for analyzing relationships while accounting for other variables
- **Matching**: a Python function for comparing groups with similar observed covariates

Test Python Methods in the admin UI. Run Skills through an MCP-connected AI client.

## Registration and execution

- **Register** the function and its data requirements.
- **Execute** with selected metrics, dimensions and dates.

For example, register OLS once, then connect customer purchases and ad exposures to analyze their relationship. The semantic layer owns metric definitions and aggregation.

## Execution flow

**Select a Method → connect data → query and calculate → record results**

AI reads the Method's input requirements and semantic catalog to choose data, asking about ambiguous meanings or dates. Decision Layer queries the data, calls the function and records inputs, queries and results in a Run.

Read [the Python Method example](../tutorials/write-your-method), then [register it in a project](method-projects.md). Look up registration options in [Method API](../reference/method-contract.md).
