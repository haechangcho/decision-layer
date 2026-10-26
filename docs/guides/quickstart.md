---
title: Install and start
description: Run the sample and connect your AI client.
---

# Install and start

You need **Python 3.11+** and **Docker running**. Start in an empty directory.

## 1. Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install decision-layer
decision-layer demo
```

This prepares sample data and starts the server. The first run takes time to download and load the data.

## 2. Explore the UI and files

Open [the admin UI](http://127.0.0.1:8000/ui/recipes) to explore the prepared analysis. Review its results and queries in [Runs](http://127.0.0.1:8000/ui/runs).

Editable Skills and Python Methods appear in your working directory:

```text
workspace/
├── decision-layer.yaml
├── recipes/
└── methods/
    ├── metric_lookup/SKILL.md
    ├── drilldown/SKILL.md
    ├── ols/method.py
    └── matching/method.py
```

- `SKILL.md`: analysis instructions for AI
- `method.py`: Python calculation function
- `recipes/`: saved analysis procedures

See [Register in a project](method-projects.md) to edit or add Methods.

## 3. Connect your AI client

Keep the server running and follow [MCP setup](mcp.md).

> For February 2001 in the sample, find the department with the highest retailer receipts and show its receipts by store.

## Stop and restart

Press `Ctrl+C` to stop. Data and execution history are kept.
Run `decision-layer demo` from the same directory to start again.

For your own data, [connect Cube](cube.md). For the sample's source and structure, see [Sample data](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.md).
