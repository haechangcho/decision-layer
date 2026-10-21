---
title: Install and start
description: Install, run the sample and connect your AI client.
---

# Install and start

Prepare **Python 3.11 or later** and **a running Docker installation**. Start in an empty working directory.

## 1. Install and run

Run these commands in order:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --pre 'decision-layer[stats,mcp]'
decision-layer demo
```

This installs the admin UI and analysis libraries, prepares sample data and starts the server.
The first run may take a few minutes to download the required files.

## 2. Explore the UI and files

Open [the admin UI](http://127.0.0.1:8000/ui/recipes) to explore the prepared revenue analysis.
Inspect the queried data and results in [Runs](http://127.0.0.1:8000/ui/runs).

Editable Skills and Python Methods are created in your working directory:

```text
workspace/
├── decision-layer.yaml
└── sample_shop/methods/
    ├── metric_lookup/SKILL.md
    ├── drilldown/SKILL.md
    ├── ols/method.py
    └── matching/method.py
```

`SKILL.md` contains analysis instructions for AI; `method.py` contains the Python calculation.
See [Method projects](./method-projects.md) to edit or add definitions.

## 3. Connect your AI client

Keep the server running and follow [MCP setup](./mcp.md) to connect your AI client.
Then try asking:

> Find the highest-revenue department in February 2026 and explain its revenue by region.

## Stop and restart

Press `Ctrl+C` in the terminal to stop. Code, data and execution history are kept.
Run `decision-layer demo` from the same project directory to start again.

To analyze your own data, see [Connect Cube](./cube.md).
