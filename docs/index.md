---
title: Start here
description: Reuse analytical procedures on governed semantic data.
---

# Decision Layer

Decision Layer connects your semantic layer to reusable analytical procedures.
Run them through Web, Python, REST or MCP, and inspect the inputs, queries and results.

The semantic layer defines metrics, dimensions and access. Decision Layer defines how to analyze them.

## Start with your task

| Task | Guide | Requirements |
| --- | --- | --- |
| Try the product with sample data | [Run the sample](guides/quickstart.md) | Docker and Compose |
| Write and test a Method | [First Method](guides/methods.md) | Python 3.11+ |
| Work on Web or API | [Local development](guides/development.md) | Python 3.11+, Node.js 22 |

## Three concepts

- **Method**: one analytical capability, such as trend or peer comparison. It can combine several queries.
- **Recipe**: your team's procedure, built from existing Methods and semantic references.
- **Run**: a recorded execution with versions, inputs, query evidence and limitations.

Use a Recipe when existing Methods cover the analysis. Add a Method when a new calculation is needed.

## Use your data

[Connect Cube](guides/cube.md) or [dbt Semantic Layer](guides/dbt.md), then
[connect an AI client](guides/mcp.md) or use the Web app.
Learn to [create a Recipe](guides/recipes.md) and [review a Run](guides/runs.md).

For implementation details, see [Architecture](ARCHITECTURE.md) and the
[Method contract](reference/method-contract.md).
