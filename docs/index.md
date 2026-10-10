---
title: Quickstart
description: Run the sample, inspect governed metrics and record your first analysis.
---

# Quickstart

Run the local Cube example with an empty Recipe library. Follow the full path from metric to recorded analysis.

Method contributors can start with the [Python-only tutorial](./guides/methods.md) without this sample.

## 1. Start the sample

You need Docker with Compose. From a terminal:

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer/examples/complete-journey
```

```bash
docker compose -p decision-layer-cube up -d --build --wait --wait-timeout 900
```

Web runs on localhost:3000, API on localhost:8000 and Cube on localhost:4000. The first run downloads and imports the data; allow several minutes. New installations start without Runs or Recipes; restarting preserves records.

Connect your organization's dbt environment through its [official Semantic Layer API](./guides/dbt.md). That hosted API is not part of the Docker sample. See the [sample guide](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.md) for teardown.

## 2. Inspect a metric

Open [the local Web app](http://localhost:3000). Go to **Metrics**, select **Retailer receipts**, and inspect its definition and available dimensions. The selected semantic provider owns the definition; Decision Layer reads it from the catalog.

## 3. Ask through MCP

Install the local adapter and connect [Claude or Codex](./guides/mcp.md). Ask:

> Across all available data, which product department has the largest retailer receipts? Show the analysis steps and evidence.

Open **Runs** in Web. The record shows the original question, which Method answered each step, the result, and the queries. From a completed Run, **Register as Recipe** saves the same procedure and settings for reuse.

## Choose your next step

- [Connect an existing Cube](./guides/cube.md) to use your own governed metrics.
- [Connect dbt Semantic Layer](./guides/dbt.md) to use your organization's official API.
- [Create a Recipe](./guides/recipes.md) for a question your team asks repeatedly.
- [Review Runs and evidence](./guides/runs.md) before reusing a procedure.
- [Add a Method](./guides/methods.md) when the existing analytical capabilities are insufficient.

::: info About the sample
The source day indices are mapped to example calendar dates, not actual purchase years. The data is observational and does not establish causal effects. See the [sample notes](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.md) before interpreting its business results.
:::
