# Statistical Methods with ordinary Python

New Method authors declare data roles and use native library APIs. They do not need an `AnalysisDesign` object, assumption checkboxes, seed input or direct manifest manipulation. Python calls use the same argument names as the function. Internal contracts still govern semantic access, scope, limits and provenance.

## Install once

Optional libraries are installed in the development/server environment, never during Method execution. Use the tested Python 3.11 constraints; actual runtime versions are recorded.

```bash
python3.11 -m venv .venv-method
.venv-method/bin/python -m pip install -c examples/methods/statistics/constraints-py311.txt -e '.[dev,stats,dowhy,econml]'
```
## Register and use

Use a fresh fixture session or a real Cube connection. The four data roles are outcome, treatment, confounders and unit; current period and shared filters belong to execution scope.

```python
from decision_layer.methods import Scope, register_builtins
from examples.methods.scenarios.scenarios import M, TREAT, BASELINE, UNIT, DATE, FEB

register_builtins(session.registry)
trial = await session.run(
    "stats.binary_regression",  # Use "stats.linear_dml" for constant binary DML.
    outcome=M,
    treatment=TREAT,
    confounders=[BASELINE],
    unit=UNIT,
    scope=Scope(FEB, DATE),
)
print(trial.result.primary.data)
```
Measure confounders can be passed directly under `confounders`; the catalog determines which fields become native measures or dimensions. Map-style and legacy canonical inputs remain accepted for REST/MCP and existing Recipes.

## Author with the native library API

Write ordinary Python calculation functions, use `ctx.entities` for governed extraction and `ctx.compute` for computation. The calculation also accepts a DataFrame without Decision Layer. DoWhy calls remain explicit:

```python
from dowhy import CausalModel

model = CausalModel(data=observations, treatment="treatment", outcome="outcome", graph=graph)
estimand = model.identify_effect(proceed_when_unidentifiable=False)
estimate = model.estimate_effect(
    estimand, method_name="backdoor.linear_regression",
    control_value=0, treatment_value=1, target_units="ate", confidence_intervals=False,
)
```

The hands-on `docs/tutorials/methods/advanced_method.en.ipynb` contains native DoWhy calculation and a small Method wrapper. Reviewed server functions must live in importable Python modules. No generic estimator facade is required.

<<< @/../src/decision_layer/methods/advanced.py#binary_regression

## Data checks and interpretation

Check primary unit, non-null unique keys, finite values, missingness, treatment groups, bounded encoding, regression rank and observed support. Native binary regression requires at least 30 observations per arm and fitted propensities in [0.05, 0.95]; these thresholds are diagnostics, not proof of positivity. DML has its own fit conditions. Inadequate data refuses estimation.

The reviewed Methods always report association, `assumptions_status="not_verified"` and `causal_claim="not_established"`. They record the assumed graph, estimator, contrast, fixed seed/folds and diagnostics where applicable. No confidence interval is reported. A graph, refutation or a note does not establish identification. Treatment/covariate timing, unmeasured confounding, independence and interference still need evidence before any causal claim. Notes cannot override validation or semantic definitions.

## Two-period group contrast

`stats.two_period_contrast` requires a complete unit × time panel with exactly two ordered buckets, fixed treatment groups and finite outcomes. The earlier bucket is pre and later bucket is post; a longer panel refuses rather than silently choosing endpoints. Parallel trends are not claimed. Optional `windows` partitions extraction without overlap; `granularity` controls the requested month/day buckets. These are meaningful data-shape inputs, not assumption flags.

## Compatibility

`stats.adjusted_difference`, `stats.dml` and `stats.did` retain their original 1.0.0 contracts for pinned Recipes. Their old design-object schema is compatibility-only, not the authoring API. New callers use `stats.binary_regression`, `stats.linear_dml` and `stats.two_period_contrast`. Existing Runs and versions are not rewritten or automatically aliased.

## Python, pytest and notebook

Use the same calculation in Python and pytest; the optional notebook shows writing, registration, direct arguments and table results. Local calculation stays in the caller process for debugging. Server calculation uses the existing bounded child process without provider credentials; it is not an arbitrary-code sandbox. See [manual scenarios](method-scenarios.md).

## Current Method list

Optional statistical implementations include `stats.binary_regression`, `stats.linear_dml` and `stats.two_period_contrast`; enable them explicitly through reviewed Python registration. Retired `stats.adjusted_difference`, `stats.dml` and `stats.did` are excluded from the Web/REST/MCP lists and candidate search. Explicit lookup and execution retain their original 1.0.0 contracts for existing pinned Recipes. No automatic aliasing or historical Run rewrite is performed. OLS, regression adjustment, DML and CEM remain separate analytical methods.

`causal.cem` is likewise compatibility-only and excluded from the default list and AI discovery. Existing explicit references keep version 1.1.1.

## MVP DoWhy matching and OLS adjustment

Two small Methods are in the default catalog. Both use `outcome`, `treatment`,
`confounders`, `unit` and the ordinary execution `scope`:

| Method | Native estimator | Contrast |
| --- | --- | --- |
| `stats.binary_matching` | `backdoor.distance_matching` | ATT: treated units, 1 vs 0 |
| `stats.regression_adjustment` | `backdoor.linear_regression` | Stored-unit slope, or an explicit population contrast |

These are different target populations. OLS here adjusts for covariates in a binary
contrast; optional `stats.ols` returns ordinary association coefficients. Neither
DoWhy identification under an assumed DAG nor a placebo check establishes causality.
See the [official estimator documentation](https://www.pywhy.org/dowhy/v0.14/dowhy.causal_estimators.html).
Implementation and experiments remain pinned to 0.13.

Run the known-effect example after installing `.[stats,dowhy]`:

```bash
.venv/bin/python -m examples.methods.statistics.dowhy_basics
.venv/bin/python -m pytest tests/unit/test_dowhy_matching.py
```

It uses the same registered Methods and entity queries as production. The 200 synthetic
units have equal pre-treatment covariate distributions and outcome `3*x + 2*treatment`.
Both estimates return 2.0. This is synthetic ground truth, not a claim about Journey data.

Use existing semantic references in a connected session:

```python
trial = await session.run(
    "stats.binary_matching",  # Or stats.binary_regression
    outcome=outcome_ref,
    treatment=treatment_ref,
    confounders=[baseline_ref],
    unit=unit_ref,
    scope=scope,
)
```

This call fragment assumes a connected session with registered builtins and resolved
references; the executable example supplies these. Matching treatment must be 0/1. Regression also supports continuous numeric values. Each unit
must have one complete observation, at least 30 units per arm, and covariates measured
before treatment. Outcome timing, no unmeasured confounding, independence and no
interference require domain evidence. The Method cannot infer those facts from refs.

Matching standardizes encoded covariates and uses one nearest control with replacement.
It refuses fitted propensity outside [0.05,0.95], fewer than 30 distinct matched controls,
a match distance above 1.0 or any absolute post-match standardized mean difference
above 0.1. These are conservative Method policies, not statistical proofs. Categorical
only/tied datasets can fail the distinct-control policy. It never silently discards
unmatched treated units to change ATT's population. Diagnostics record reuse counts,
distances, encoding and before/after balance. Missing/duplicate units, nonbinary treatment,
small arms and insufficient observed support refuse. No matching CI or significance is
reported for reused units. Results label assumptions unverified and causal claims not
established. A new policy or contrast would need a reviewed version rather than free-form options.

Complete Journey's Docker API builds with stats and dowhy extras by default. Other
installations explicitly install these extras; dependencies are never installed during
an analysis request. Standard query Methods still work in a core-only installation.

## Continuous treatment without extra inputs

`stats.regression_adjustment` is the preferred default OLS Method. Existing
`stats.binary_regression` remains explicitly executable with its original contract.

```python
trial = await session.run(
    "stats.regression_adjustment",
    outcome=purchase_amount,
    treatment=discount_rate,
    confounders=[baseline_amount],
    unit=customer,
    scope=scope,
)
```

The connected session and refs above are supplied by the caller. The default value
is the adjusted slope per stored treatment unit. If discount is stored as 0–1,
a slope of 50 corresponds to 0.5 per percentage point. If stored as 0–100, the
same data give slope 0.5. The Method does not invent unit conversions.

For a specific contrast, add both `control_value=0.10` and `treatment_value=0.20`;
the example then returns 5. Optional values must be inside the observed range.
Range checks do not verify conditional overlap. Continuous input requires at least
60 units and 10 distinct values; binary input requires 30 per arm. Missing values,
duplicate units, nonnumeric categories, constant treatment, nonfinite inputs,
rank deficiency, partial endpoint input and unsupported extrapolation refuse.

The default result is a constant additive model slope, not proof of an actual +1
intervention beyond observed treatment values. Details report `result_scale`,
`slope`, `contrast`, `estimation_contrast`, treatment reference and support limits.
Temporal and identification assumptions remain unverified; no interval is reported.
The matching Method remains binary and targets the treated population.

Execute the same implementation used by both workshop notebooks:

```bash
.venv/bin/python -m examples.methods.statistics.continuous_regression
.venv/bin/python -m pytest tests/unit/test_regression_adjustment.py
```
