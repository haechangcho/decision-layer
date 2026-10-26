# Register in a project

Save your function and registration code in a project to use them through the admin UI and AI.

## Create a project

Run in the environment where you [installed Decision Layer](quickstart.md).

```bash
decision-layer init my_team
cd my_team
python -m pip install -e '.[test]'
```

Two editable Skills and two Python Methods are created:

```text
my_team/
├── decision-layer.yaml
├── pyproject.toml
├── recipes/
└── methods/
    ├── metric_lookup/SKILL.md
    ├── drilldown/SKILL.md
    ├── ols/
    │   ├── method.py
    │   ├── checks.py
    │   └── test_method.py
    └── matching/
        ├── method.py
        ├── checks.py
        └── test_method.py
```

- `SKILL.md`: analysis instructions for AI
- `method.py`: calculation and `METHOD = python_method(...)` registration
- `checks.py`: optional checks before calculation
- `test_method.py`: tests for the calculation and checks

See [the Python Method example](../tutorials/write-your-method) for function and registration code.

## Edit and test

```bash
decision-layer check
decision-layer test
decision-layer list
decision-layer serve --reload
```

- `check`: validate registration and references without executing analysis
- `test`: run project tests; the starter calculation tests need no Cube
- `list`: show registered Methods and file paths
- `serve --reload`: start the admin UI and reload when files change

[Connect Cube](cube.md), then choose **Methods → Choose inputs and test**.
Run tests and increment the Method version when changing a calculation.

## Add a Method

```bash
decision-layer new python rank
decision-layer new skill metric_review
```

These create `methods/rank/method.py` and `methods/metric_review/SKILL.md`.
Use `decision-layer init my_team --empty` to start without defaults.

## Register checks

Checks are optional. Keep short checks in `method.py`, or move longer ones to `checks.py`.

```python
from .checks import check_data

METHOD = python_method(
    ols,
    name="my_team.ols",
    version="1.0.0",
    inputs={"data": DataInput(columns={...})},
    checks=[check_data],
)
```

Execution follows **query data → check input requirements → run registered checks → calculate**.
A check that raises `ValueError` or returns `False` stops the calculation and records the reason.
See [Method API](../reference/method-contract.md#checks-and-errors) for details.

## Write a Skill

Put analysis steps and decision rules in `SKILL.md`:

```markdown
# Inspect revenue by department

1. Query revenue by department.
2. Select the highest-revenue department. Ask the user if tied.
3. Inspect that department's revenue by store.
4. Explain the results and what remains unknown.
```

The product supplies shared tool and recording instructions; do not repeat them in each Skill.

## Use through AI

Keep the server running and [connect MCP](mcp.md). AI can discover and execute the project's Methods.

## Manage with your team

Keep project files in Git. Package upgrades preserve your files.
Start the server with `decision-layer serve --project /path/to/my_team` to select the project.

Recipes live in `recipes/`; Runs are stored in `.decision-layer/decision_layer.db`.
Local notebook results are not automatically stored on the server.
