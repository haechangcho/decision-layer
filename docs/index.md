---
title: Quickstart
description: Run the sample, inspect governed metrics and record your first analysis.
---

# Quickstart

Run Decision Layer with a connected Cube and an empty Recipe library. The sample uses a multi-table retail dataset, so you can follow the full path from metric to recorded analysis.

## 1. Start the sample

You need Docker with Compose. From a terminal:

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer/examples/complete-journey
docker compose up -d --build --wait
```

The first run downloads and imports the source data. Allow several minutes. The stack starts Web on `localhost:3000`, the API on `localhost:8000`, and Cube on `localhost:4000`. No Cube account or local access token is needed for this sample.

## 2. Inspect a metric

Open [the local Web app](http://localhost:3000). Go to **Metrics**, select **Retailer receipts**, and inspect its definition and available dimensions. The metric definition stays in Cube; Decision Layer reads it from the semantic catalog.

## 3. Ask through MCP

Install the local adapter and connect [Claude or Codex](./guides/mcp.md). Ask:

> Across all available data, which product department has the largest retailer receipts? Show the analysis steps and evidence.

Open **Runs** in Web. The record shows the original question, which Method answered each step, the result, and the queries. From a completed Run, **Register as Recipe** saves the same procedure and settings for reuse.

## Choose your next step

- [Connect an existing Cube](./guides/cube.md) to use your own governed metrics.
- [Create a Recipe](./guides/recipes.md) for a question your team asks repeatedly.
- [Review Runs and evidence](./guides/runs.md) before reusing a procedure.
- [Add a Method](./guides/methods.md) when the existing analytical capabilities are insufficient.

::: info About the sample
The source day indices are mapped to example calendar dates, not actual purchase years. The data is observational and does not establish causal effects. See the [sample notes](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.md) before interpreting its business results.
:::
