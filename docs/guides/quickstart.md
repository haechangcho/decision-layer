---
title: Quickstart
description: Save an analysis and apply the same procedure to a new period.
---

# Quickstart

With Git and running Docker Compose v2, try a small synthetic sample through a real
Cube server and the normal execution engine. No company account or model API key is needed.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer
bash scripts/demo.sh
```

Open [Runs](http://localhost:3100/runs). The script executes an analysis, saves its
Recipe, replays it and prints direct links. First builds download dependencies and
can take several minutes.

1. January: Home leads revenue at 6,200; inspect its regions.
2. Save: register the recorded analysis as a Recipe.
3. February: the same Recipe selects Grocery at 6,720.
4. March: equal leaders require input before querying a regional branch.

Inspect the rule, resolved selection, queries and warnings in each Run. This is a
descriptive ranking of synthetic data, not a causal explanation. The scripted
walkthrough is not an LLM benchmark.

## Reuse with your AI

Install the local adapter using [MCP setup](./mcp.md). Set `DL_API_URL=http://localhost:8100`
and `DL_WEB_URL=http://localhost:3100` for this sample.

> Reuse the saved department investigation for February 2026. Find the leading
> revenue department, then show its regional breakdown, evidence and limitations.

Your AI client supplies its own model connection.

```bash
bash scripts/demo.sh replay
bash scripts/demo.sh stop
```

[Ports, reset and sample details](https://github.com/haechangcho/decision-layer/blob/main/examples/quickstart/README.md)
· [Larger Complete Journey sample](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.md)

## Next steps

[Connect Cube](./cube.md) · [Create Recipes](./recipes.md) · [Contribute a Method](./methods.md)
