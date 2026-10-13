# Method development and manual tests

```bash
python3.11 -m venv .venv-method
.venv-method/bin/python -m pip install -c examples/methods/patterns/constraints-py311.txt -e '.[dev,stats,dowhy,econml]'
.venv-method/bin/python -m examples.methods.patterns --all
.venv-method/bin/python -m examples.methods.patterns.failures --all
```

[All scenarios](../../../docs/guides/method-scenarios.md) · [Authoring flow](../../../docs/guides/methods.md) · [Advanced analysis](../../../docs/guides/statistical-methods.md)

`methods.py` contains actual functions; `scenarios.py` independent queries/answers; `failures.py` failure cases; `journey.py` live-data/SQL comparisons; `server.py` canonical API bootstrap; `explore.ipynb` optional experiments. These are implemented examples, not design pseudocode.
