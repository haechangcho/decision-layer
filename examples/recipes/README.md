# Recipe examples

`skill_chain.py` defines a campaign investigation using registered query Skills.
`skill_chain_demo.py` replays recorded queries with prepared data. Run it with:

```bash
.venv/bin/python -m examples.recipes.skill_chain_demo
```

`skill_chain.py` uses the current drilldown and metric-lookup Skills. The hidden
three-step compatibility procedure and its calculation have been removed.

`evals/` preserves historical external-client protocols and evidence verifiers.
Those older runners require their original checkout/release; they cannot execute
the retired Methods against the current package.
See the [Recipe guide](../../docs/guides/recipes.md) and the
[complete journey](../complete-journey/README.md) for server usage.
