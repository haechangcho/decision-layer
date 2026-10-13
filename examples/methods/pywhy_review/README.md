# PyWhy review lab

Executed evaluation code, not production builtin support. Read the paired reports:
[English](../../../docs/guides/pywhy-review.md) · [한국어](../../../docs/ko/guides/pywhy-review.md).

From the repository root, use Python 3.11 and install `.[dev,stats,dowhy,econml]`
with `constraints-013-py311.txt`, as shown in those guides. Then:

```bash
python -m examples.methods.pywhy_review.experiment
python -m examples.methods.pywhy_review.session
python -m pytest -q examples/methods/pywhy_review/test_review.py
```

`explore.ipynb` imports the same implementation. The two result JSON files capture
actual numerical estimates, package versions and backend warnings. The 0.14 setup
is an isolated upgrade experiment; it is not compatible with the existing builtin
0.13/NumPy<2 policy. Constraints snapshot review environments, not every supported
platform. Do not treat point-estimate checks as inference or real-world causal proof.
