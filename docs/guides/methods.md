# Understand Methods

A Method is an analytical capability applied to data. A data scientist registers a function, and users and AI reuse it with the metrics they need.

A Python Method executes a calculation function. A Skill Method provides analysis guidance for AI. This guide explains the Python function path.

## Define the calculation, then select the data

Registration defines **how to calculate**. Execution selects **which data to analyze**.

| When | What is selected | Example |
|---|---|---|
| Register a Method | Function and input requirements | OLS requiring a numeric outcome and explanatory variables |
| Execute an analysis | Metrics, variables and dates | Customer purchases, ad exposures and February data |

The semantic layer owns definitions and aggregations. The Method calculates using data queried from those definitions.

## When AI requests an analysis

1. AI discovers a registered Method and reads its input requirements.
2. It selects metrics and dimensions from the semantic catalog, asking about ambiguous inputs or dates.
3. Decision Layer validates the inputs, queries the data and passes it to the function.
4. The server records inputs, queries and results in a Run. AI reads and explains the result.

Web, REST and MCP share the same execution code. A local notebook session lets a developer inspect querying and calculation without creating a server Run.

## See an example

[Connect a Python function](../tutorials/write-your-method) shows ranking and OLS with code and results.

Continue with [Register in a project](method-projects.md) to make a function available in the service. If existing Methods cover the analysis, compose them in a [Recipe](recipes.md).

See [Method API](../reference/method-contract.md) to look up registration arguments and input options.
