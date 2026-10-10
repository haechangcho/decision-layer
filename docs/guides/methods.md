# Develop your first Method

A Method is one analytical capability. Use a Recipe when existing Methods already
cover the calculation. You need Python 3.11+ to start; a Web server and semantic
source are optional for the first test.

## Install and run

From the repository root:

```bash
make setup
make example
```

Without Make:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q examples/methods/first_method
```

Open `examples/methods/first_method/`:

| File | Edit it to |
| --- | --- |
| `method.py` | Change the input contract and analytical implementation |
| `fixtures.py` | Supply independently expected semantic queries and data |
| `test_method.py` | Check the expected answer |
| `explore.ipynb` | Optionally explore a live Cube source in Jupyter/VS Code |

Change the implementation, rerun the test, and inspect the failure. The test checks
that group values are 30, 20 and 10 and that the exact period, dimension, ordering and
limit were requested. It does not treat the Method's own output as a reference.

## Understand the code

```python
from decision_layer.methods import (
    Method, MethodOutput, MethodManifest, RoleSpec, ParamSpec, Artifact, DatasetSpec,
)
```

`manifest` declares roles, parameters, outputs and interpretation. `run(ctx, bindings,
params)` requests data through `ctx.dataset()` and returns `MethodOutput`. Keep metric
formulas, joins and permissions in the semantic source. Declare all emitted primary
and supporting artifact types; the shared Registry rejects undeclared types.

The example uses an isolated `MethodSession` to register and execute the Method.
It applies ordinary registry/context validation and records each query attempt.
It is trusted local Python development, not a code sandbox or server installer.

## Several queries in one Method

```bash
.venv/bin/python -m pytest -q examples/methods/peer_comparison
```

This imports the real `methods/peer_comparison.py` implementation and supplies three
expected queries: subject inside peer conditions, peers excluding subject, and the
accessible overall population excluding subject. Provider-computed fixture rates
12%, 8% and 6% give differences 4 and 6 percentage points. No significance or causal
effect is claimed. A Method can execute several queries and combine them internally.

For failures, budgets and output contracts:

```bash
.venv/bin/python -m pytest -q tests/unit/test_method_dev.py
```

## Connect real data when needed

```python
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope
from decision_layer.semantic.credentials import RequestCredentials

session = await MethodSession.cube(cube_url, RequestCredentials(token))
session.metrics()
session.dimensions(metric_ref)
session.register(my_method)
trial = await session.run(
    my_method.manifest.name,
    bindings=bindings, params=params,
    scope=Scope(date_range=("2026-09-01", "2026-09-30"), time_dimension=time_ref),
)
trial.result
trial.attempts
trial.queries
```

Select real references from the visible catalog. Declared dimension relationships
are discovery hints; provider execution validates combinations. Keep credentials
outside cells and outputs. Direct execution stays in the current event loop for
breakpoints and creates no stored Run. After a provider/code exception, inspect
`session.last_trial.attempts`; the exception is re-raised.

`session.preview(recipe, step_index=..., scope=...)` runs a new Recipe prefix through
the canonical RunEngine, in workers with local memory storage. It issues fresh queries
and never uploads a Run or Method to the Web server. Call `session.close()` afterwards.
Re-register edited implementations with `replace=True`; refresh provider metadata
with `refresh_catalog()`. See the example notebook for an executable two-step preview.

## Register and contribute

Add the reviewed implementation under `src/decision_layer/methods/` and add it to
`register_builtins()` in that package's `__init__.py`. Modules do not register themselves
on import. Logical IDs such as `query.peer_comparison` remain independent of folders.

Run relevant tests, then `make test`. Submit the source, manifest, independent answer,
failure tests and a small invocation example together. Add dependencies explicitly;
do not install libraries at runtime.

Next: [detailed input/result contracts](../reference/method-contract.md),
[testing](testing.md), [contribution workflow](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md).
