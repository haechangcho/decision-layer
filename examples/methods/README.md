# Method examples

From the repository root, install Python 3.11+ development dependencies and run:

```bash
make setup
make example
```

Start with `first_method/method.py`. Its fixture supplies independently known group
values and an exact semantic query; `test_method.py` registers and executes the Method
through the public SDK. Edit the implementation or expected query and rerun the test.

For an existing Method with three queries:

```bash
.venv/bin/python -m pytest -q examples/methods/peer_comparison
```

The production implementation is `src/decision_layer/methods/peer_comparison.py`.
The example checks subject/peer/overall populations and expected 4/6 percentage-point
differences. Fixtures are single-use and verify requests/combination, not warehouse
aggregation, authentication, joins or causal validity.

Each example has an optional `explore.ipynb`. Launch Jupyter from the repository root
with a kernel containing the editable package. Notebooks import ordinary Python
modules; there are no duplicated percent-cell sources or generation scripts. Restart
or reload the module after editing, then register with `replace=True`.

The peer notebook needs no credentials. The first-Method notebook uses Cube. Set
`CUBE_API_URL`, `CUBE_TOKEN`, and optionally `CUBE_INSTANCE` (default `local`) in the
kernel environment. The discovery cell lists refs; set `CUBE_METRIC`,
`CUBE_DIMENSION`, `CUBE_TIME_DIMENSION`, `ANALYSIS_START` and `ANALYSIS_END` from those
visible refs, or edit the selection variables directly. Do not save tokens in cells
or outputs. Preview requires a Cube-accepted token with a subject claim.

Direct trials stay in the kernel for breakpoints. Query attempts and results are
inspectable; exceptions propagate. Recipe previews execute in workers and store Runs
only in memory. Neither uploads code/results to an API server. Call `session.close()`
after preview. See [the Method guide](../../docs/guides/methods.md) for the full workflow.
