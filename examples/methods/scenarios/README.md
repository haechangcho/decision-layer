# Execution scenarios

This directory exercises query shapes and advanced SDK contracts. To write your
first Method, start with the [tutorial](../../../docs/tutorials/methods/write_your_method.en.ipynb).

| File | Responsibility |
| --- | --- |
| `methods.py` | Advanced Method implementations |
| `scenarios.py` | Independently specified queries and expected results |
| `__main__.py` | Offline scenario runner |
| `failures.py` | Invalid input and refusal cases |
| `discovery.py` | Method discovery example |
| `journey.py` | Live Cube and SQL comparisons |
| `server.py` | API bootstrap for live scenarios |

```bash
.venv/bin/python -m examples.methods.scenarios --case by_group
.venv/bin/python -m pytest -q tests/examples/test_scenarios.py
```

The [scenario guide](../../../docs/guides/method-scenarios.md) covers the full
statistical environment and opt-in live checks. The optional
[notebook](../../../docs/tutorials/methods/query_scenarios.ipynb) imports the same code.
