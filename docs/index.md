---
title: Quickstart
description: Run the sample, inspect governed metrics and record your first analysis.
---

# Quickstart

Choose a Cube or dbt MetricFlow example with an empty Recipe library. Both use the same multi-table retail dataset, so you can follow the full path from metric to recorded analysis.

## 1. Start the sample

You need Docker with Compose. From a terminal:

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer/examples/complete-journey
```

Choose one provider, then run the command in its tab:

::: code-group

```bash [Cube]
docker compose up -d --build --wait --wait-timeout 900
```

```bash [dbt MetricFlow]
docker compose -f compose.yaml -f compose.dbt.yaml up -d --build --wait --wait-timeout 900
```

:::

Both options start Web on `localhost:3000` and API on `localhost:8000`. The Cube example adds Cube on `localhost:4000`; the dbt example adds MetricFlow on `localhost:4100`. The first run downloads and imports the source data; allow several minutes. The selected source is configured automatically on a fresh installation. Run one example at a time; see the [sample guide](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.md) for switching and teardown.

The dbt example runs locally without an account, using a bundled MetricFlow gateway. To connect your company's existing dbt environment, choose **dbt Semantic Layer** in Sources and use the [official API connection](./guides/dbt.md). No local gateway is needed for that connection.

## 2. Inspect a metric

Open [the local Web app](http://localhost:3000). Go to **Metrics**, select **Retailer receipts**, and inspect its definition and available dimensions. The selected semantic provider owns the definition; Decision Layer reads it from the catalog.

## 3. Ask through MCP

Install the local adapter and connect [Claude or Codex](./guides/mcp.md). Ask:

> Across all available data, which product department has the largest retailer receipts? Show the analysis steps and evidence.

Open **Runs** in Web. The record shows the original question, which Method answered each step, the result, and the queries. From a completed Run, **Register as Recipe** saves the same procedure and settings for reuse.

## Choose your next step

- [Connect an existing Cube](./guides/cube.md) to use your own governed metrics.
- [Connect dbt Semantic Layer](./guides/dbt.md) to use your organization's official API.
- [Explore the local dbt example](./guides/metricflow.md) and its SQL/YAML models.
- [Create a Recipe](./guides/recipes.md) for a question your team asks repeatedly.
- [Review Runs and evidence](./guides/runs.md) before reusing a procedure.
- [Add a Method](./guides/methods.md) when the existing analytical capabilities are insufficient.

::: info About the sample
The source day indices are mapped to example calendar dates, not actual purchase years. The data is observational and does not establish causal effects. See the [sample notes](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.md) before interpreting its business results.
:::
