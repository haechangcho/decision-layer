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
pip install decision-layer
decision-layer demo
```

The package includes the admin UI, statistical libraries and MCP adapter. `demo` prepares sample data and starts the server.
The sample uses dunnhumby’s **The Complete Journey** retail dataset. It imports **all eight tables** into PostgreSQL, including purchases, products, households and campaigns. The first run downloads about 135 MB and imports the data. Later starts reuse the saved database.

The source uses relative day numbers. The example maps day one to `2000-01-01`; these are artificial dates, not actual purchase years.

## 2. Explore the UI and files

Open [the admin UI](http://127.0.0.1:8000/ui/recipes) to explore the prepared revenue analysis.
Inspect the queried data and results in [Runs](http://127.0.0.1:8000/ui/runs).

Editable Skills and Python Methods are created in your working directory:

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

`SKILL.md` contains analysis instructions for AI; `method.py` contains the Python calculation.
Recipes live in `recipes/`; demo services and execution history stay in `.decision-layer/`.
See [Method projects](./method-projects.md) to edit or add definitions.

## 3. Connect your AI client

Keep the server running and follow [MCP setup](./mcp.md) to connect your AI client.
Then try asking:

> Using the example calendar, find the department with the highest retailer receipts in February 2001 and show its receipts by store.

## Stop and restart

Press `Ctrl+C` in the terminal to stop. Code, data and execution history are kept.
Run `decision-layer demo` from the same project directory to start again.

To analyze your own data, see [Connect Cube](./cube.md).
