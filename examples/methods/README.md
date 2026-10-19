# Method examples

1. Follow the [Python Method notebook](../../docs/tutorials/methods/write_your_method.en.ipynb)
   ([한국어](../../docs/tutorials/methods/write_your_method.ko.ipynb)).
2. Use [project/](project/README.md) to save Methods and Skills for the server.
3. Explore [authoring/](authoring/README.md), [statistics/](statistics/README.md)
   or [scenarios/](scenarios/README.md) for a specific need.

The notebook uses prepared data and needs no Cube server or AI connection.
Use a Python environment with this checkout installed and the `stats` extra.
Launch it from this repository so it can import the example modules.

`first_method/` and `peer_comparison/` demonstrate the advanced SDK contracts.
`pywhy_review/` contains optional estimator experiments. These are supporting
examples, not additional setup steps for writing a Method.

Run example checks from the repository root:

```bash
.venv/bin/python -m pytest -q tests/examples
```

See the [repository example map](../README.md) and
[Method development guide](../../docs/guides/methods.md).
