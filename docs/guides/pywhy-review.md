# CEM and PyWhy: an execution-based review

Reviewed 2026-10-12. **Separate some CEM responsibilities and retain the existing version; do not standardize everything on DoWhy.** The `review.*` Methods below are executed local experiments, not production builtins. Existing CEM, Recipes, Runs and dependency pins remain unchanged. Implemented examples and proposed extensions are explicitly distinguished.

## 1. Diagnosis and recommendation

Current `cem.py` and `matching.py` do more than estimate an effect. In particular, their provider-aggregate path has different cost and permission requirements from PyWhy estimators that materialize entity observations. Replacement cost cannot be measured by matching-function line count.

| Current responsibility | Behavior and limitation | Recommendation |
| --- | --- | --- |
| Subject/comparison definition | Dimension values, exclusions, numeric ranges, disjointness checks | Reuse semantic conditions and scope; declare treatment contrast and analysis population separately |
| Confounder coarsening/matching | Quantile/explicit bins and categorical strata; common strata selection | Retain as a distinct algorithm; distance matching/DML are not equivalent replacements |
| Selection/weighting | Weight both group means by target counts in shared strata | Keep small pure calculation functions; record exclusions, retention, weights and actual population |
| Balance | Coarsened-stratum distribution imbalance; adjusted zero is structural | Propose original-variable SMD, distribution and support diagnostics; say unavailable without sufficient data |
| Comparison/effect | Raw/adjusted differences; restricted verified-proportion intervals | Separate matched comparison from causal claims; offer regression/DML as distinct Methods |
| Validation/provenance | Semantics, counts/denominators, extraction limits, quality and query evidence | Retain in Decision Layer; DoWhy does not validate provider authorization or grain |

The native-average path requires explicit counts, a shared provider unit, and finite per-unit outcomes, among other checks. The measure-treatment path may produce unit averages with a different denominator from the provider metric. Removing these safeguards makes incorrect answers easier.

The current CEM difference is `Σ n_target,s × (mean_target,s − mean_comparison,s) / Σ n_target,s`, summed over **retained common strata**. It is not automatically the full-population ATE or original treated-population ATT. Residual within-bin confounding also prevents matching alone from justifying causality. Current `causal_conditional` labeling is stronger than the new statistical Methods' `associational` labeling. Correct this in a new contract without retroactively reinterpreting historical results.

Retain CEM 1.1.1 for compatibility and aggregate-based comparisons, but stop making it the default causal route. Separate an explicit `matched_comparison` contract from estimator-specific effect estimation. Keep ordinary OLS in statsmodels; use DoWhy native estimators or direct EconML for reviewed effect Methods. Do not introduce a generic estimator plugin runtime.

## 2. Specify the question before choosing by treatment type

| Question | Explicit inputs | Candidate/support boundary |
| --- | --- | --- |
| Binary treatment | 0→1, target population, ATE or ATT | Choose matching, regression adjustment or DML using assumptions and diagnostics |
| Multiple categories | Full category order, encoding reference, actual comparison pair | Example: reference control, contrast basic→plus; categorical DML experimentally verified |
| Continuous treatment | Units and actual contrast such as 0.5→1.5 | Continuous DML experimentally verified; declare LinearDML's linear treatment-response assumption |
| Binned continuous treatment | Boundaries, inclusion rules, within-bin intervention meaning | A new question, not the original fixed-dose effect; general support deferred |
| Regression without treatment | Outcome, features, unit | Associational OLS coefficients; no artificial treatment or DAG required |

Treatment binning changes the question and estimand. Comparing discounts of 0–10% against 10–20% differs from intervening at 5% versus 15%. Unless the intervention within each bin is defined, consistency is ambiguous. Report information loss, boundary sensitivity and within-bin distribution differences. Reusable business bins belong to the semantic layer; analyst-chosen experimental bins belong in analysis configuration and provenance.

In contrast, coarsening a **confounder**, such as prior spending, changes adjustment resolution without redefining treatment. Coarser bins may retain more observations while leaving imbalance. Do not choose favorable boundaries after inspecting outcomes.

ATE averages a contrast over the specified target population; ATT averages it over the explicitly treated population; CATE conditions it on pretreatment modifiers X. For multiple categories, state “plus versus basic among plus recipients.” The population used to average CATE predictions determines ATE versus ATT. A unique unit key does not prove independence.

## 3. Distinguish the methods

| Method | Sample/estimand | Additional assumptions and costs |
| --- | --- | --- |
| Current CEM | Retained target distribution in common bins; unmatched observations excluded | Coarsening, residual confounding, population change; aggregate pushdown possible |
| DoWhy distance matching | Nearest comparison observations for ATT/ATC/ATE | Binary only; inspect scale, distance, sparse strata and neighbor reuse. Source contains an unimplemented caliper TODO, so distant neighbors can still match |
| Regression adjustment | Model contrasts averaged over an evaluation population | Functional form, interactions and extrapolation; different from selecting common strata |
| LinearDML | Cross-fit nuisance models and fit effects linear in X | Adequate fold-level observations, residual treatment variation, overlap and nuisance quality; cross-fitting does not remove unmeasured confounding |

Effect interpretation requires identification assumptions for all these methods. A more advanced algorithm does not supply them. [Official DistanceMatchingEstimator source](https://www.pywhy.org/dowhy/v0.14/_modules/dowhy/causal_estimators/distance_matching_estimator.html), [official LinearDML contract](https://www.pywhy.org/EconML/_autosummary/econml.dml.LinearDML.html).

## 4. What the three execution routes actually do

1. **DoWhy native:** DAG and identification → reviewed matching/regression → optional refutation. Identification is conditional on the supplied DAG. This experiment explicitly assumes all W variables are pretreatment common causes of T and Y.
2. **DoWhy → EconML:** Retains identification evidence and maps Y/T/X/W through a wrapper. It works, but population and effect-modifier forwarding need their own contract tests.
3. **Direct EconML:** Makes Y/T/W/X, contrasts and evaluation samples explicit. Recommended as the primary DML authoring route. Decision Layer must retain identification assumptions, evidence and diagnostics; direct invocation does not acquire automatic identification.

The `backdoor.econml.dml.LinearDML` string route ran on both versions but emitted a deprecation warning. Move to the instance-based `backdoor.econml` route only after separate regression tests. `discrete_treatment=True` alone is insufficient. The experiment specifies category order, classifier/regressor treatment models, outcome model, seed, three folds, X/W, actual T0/T1, and `inference=None`.

**Observed forwarding trap:** In the heterogeneous experiment, `target_units="att"` returned ATE 1.973 on both 0.13 and 0.14. True ATT was 2.564; direct estimation returned 2.559. Explicitly passing `effect_modifiers=["x"]` to `estimate_effect` and selecting the target sample with a callable produced the matching 2.559. On 0.13, setting X only on the constructor caused estimation to re-derive modifiers from the graph and omit X in this case. Do not label a result ATT merely because the string was accepted. [Wrapper source](https://www.pywhy.org/dowhy/v0.14/_modules/dowhy/causal_estimators/econml.html), [CausalModel source](https://www.pywhy.org/dowhy/v0.14/_modules/dowhy/causal_model.html).

These functions were executed. Their restricted experimental inputs do not constitute an arbitrary-estimator selection API.

<<< @/../examples/methods/pywhy_review/experiment.py#dowhy_native

<<< @/../examples/methods/pywhy_review/experiment.py#dml_routes

DoWhy LinearRegressionEstimator uses statsmodels OLS. With the same Y/T/W and linear specification, it returned the same number as the ordinary OLS treatment coefficient. The distinction is identification question, DAG, contrast and interpretation, not the numerical brand. Wrapping all ordinary OLS in DoWhy offers little benefit. [Official implementation](https://www.pywhy.org/dowhy/v0.14/_modules/dowhy/causal_estimators/linear_regression_estimator.html).

## 5. Install and execute the same implementation

Use Python 3.11 from the repository root. Constraints snapshot transitive dependencies from the review environments; they do not guarantee every OS/Python combination. A notebook product or web code editor is unnecessary.

```bash
python3.11 -m venv .venv-pywhy-review
.venv-pywhy-review/bin/python -m pip install -e '.[dev,stats,dowhy,econml]' -c examples/methods/pywhy_review/constraints-013-py311.txt
.venv-pywhy-review/bin/python -m examples.methods.pywhy_review.experiment
.venv-pywhy-review/bin/python -m examples.methods.pywhy_review.session
.venv-pywhy-review/bin/python -m pytest -q examples/methods/pywhy_review/test_review.py
```

Executable sources are in `examples/methods/pywhy_review/`: ordinary functions in `experiment.py`, typed adapters in `methods.py`, registration/execution with independently specified query fixtures in `session.py`, and tests of the same implementation in `test_review.py`. `explore.ipynb` imports these functions too. Its cells were executed by pytest; optional Jupyter installation and kernel selection are separate, and the notebook UI itself was not tested.

```python
from examples.methods.pywhy_review.experiment import data, native, dml

matching = native(data(), "matching", "att")
regression = native(data(), "linear", "ate")
category = dml(data("categorical"), "categorical", control="basic", treated="plus")
dose = dml(data("continuous"), "continuous", control=0.5, treated=1.5)
# In an async function or Jupyter cell:
from examples.methods.pywhy_review.session import run_case
trial = await run_case("categorical")
print(trial.queries, trial.result.primary.data)
```

Set breakpoints in `calculate`/`dml`. Inspect `trial.queries` and `trial.attempts`. Do not copy implementations into notebooks.

## 6. Keep semantic inputs simple

Reuse the implemented Cube connection, object discovery, period and filter API in [First Method](./methods). Internally map outcome measures to Y, treatment to T, confounders to W, effect modifiers to X and entity to unit. An object can legitimately occur in both W and X. Outcome must be meaningful at the selected provider-defined unit; do not silently turn an aggregate ratio into a unit outcome.

These experimental Methods were registered and executed. They are restricted to a single numeric adjustment variable, fixed three categories, or continuous treatment with two W strata. This does not imply general business-data support.

<<< @/../examples/methods/pywhy_review/methods.py#typed_methods

`session.py` invokes them with `measures={"outcome": Y}`, `dimensions={"treatment": T, "confounder": W}`, `entity=UNIT`, `Scope(PERIOD, DATE)`, an eligible-population filter and contrast params. An independent DatasetSpec checks time, filters, entity, columns and row bound. Authored functions compile into the existing canonical manifest/spec; REST/MCP users cannot supply backend class paths.

**The following extension is proposed, not implemented.** Prefer short estimator-specific typed signatures over a large estimator configuration object.

```python
# DESIGN PROPOSAL ONLY — not an available registered Method.
async def reviewed_dml(ctx, *, outcome: Measure, treatment: Dimension | Measure,
                       confounders: list[Dimension | Measure],
                       effect_modifiers: list[Dimension | Measure], unit: Entity,
                       categories: list[str], control: str, treated: str,
                       target: Literal["ate", "att"]) -> Estimate:
    ...
```

Separate categorical and continuous contrast argument types in the actual implementation. Record target population as scope plus explicit evaluation population. For CATE, distinguish X-specific results from their population average and reject unsupported X extrapolation. Do not automatically choose an algorithm from treatment type.

Authors write typed functions, semantic roles and short calculation helpers. Internals retain canonical specs, provider authorization/grain checks, bounded extraction, server compute limits, alias-to-semantic-reference mappings, encoding, contrasts, folds, sample selection, assumptions, actual package versions and queries. Local direct execution and server isolation have different limits. The new adapters were verified through local canonical sessions, not deployed through Web/REST/MCP.

A Method is one analytical procedure. Multiple queries needed to construct samples or comparisons can remain inside it. Deciding which group to investigate first and which analysis to perform next belongs to a Recipe. All interfaces execute the same registered contract without duplicating estimation code.

## 7. Check successful and refused cases

Independent-unit synthetic data, n=4,000, seed=17. Both environments agreed to the precision shown. `results-0.13.json` and `results-0.14.json` record actual versions and warnings. No confidence intervals or p-values were calculated.

| Case | Known value | Executed result |
| --- | --- | --- |
| Binary matching ATT | 2 | 2.00550 |
| DoWhy regression / identical ordinary OLS coefficient | 2 | 2.00293 |
| Direct/wrapped binary DML | 2 | 1.99942 |
| basic→plus DML | 3 | 3.00689 |
| Continuous 0.5→1.5 DML | 2 | 1.99854 |
| Heterogeneous ATE / ATT | 1.974 / 2.56369 | 1.97309 / 2.55912 |
| Two-bin CEM calculation kernel | 2 | 2.24305 |

CEM retained 100% of observations and had zero coarsened imbalance, but the original W mean difference remained 0.08182. This deliberately coarse-bin counterexample is not a benchmark of all CEM settings or its provider execution path. Mean placebo effect was −0.00992; it was not used as a pass/causality verdict.

Pytest checks these numbers and the wrapper ATT trap. Refusal scenarios cover unsupported treatment types, duplicate units, missing/nonfinite values, only one arm, small arms, failed propensity support, identical contrast values, unknown categories, doses outside observed ranges and constant doses. Identical contrast values refuse before querying; all experimental estimates record unverified assumptions and remain associational. These experimental tests skip when optional libraries are absent from a core environment.

Verification: 16 experimental tests passed per environment, including notebook cell execution; 58 existing Method/documentation regression tests and the VitePress build also passed. Warnings remain recorded, not suppressed.

## 8. Distinguish data checks from assumptions

**Implemented experimental checks:** unique/non-null keys, missingness, finite values, categories, at least 30 observations per arm, fitted logistic probabilities in 0.02–0.98, and continuous treatment within-stratum min/max. These thresholds are experimental policy, not statistical sufficient conditions. Do not tune them to make a result pass.

**Required before production promotion:** matrix rank, residual treatment variation, fold-level categories/counts, nuisance-fit diagnostics, consistent categorical encoding, distance scale, continuous support density and modifier support. Reject repeated/clustered observations with the current iid template. When timestamp/window metadata is available, check covariate < treatment < outcome; otherwise do not claim automatic verification. Assumption checkboxes have been removed from new authoring APIs; evidence must be reviewed independently.

**Assumptions requiring user evidence:** no unmeasured confounding, well-defined consistent treatment, no interference, justified selection/missingness, temporal ordering and model assumptions. Library identification does not establish the DAG's truth. Refuse causal-labeled execution when unknown or explicitly restrict it to an associational experiment.

Refutation explores selected failure modes; passing does not prove causality. Support intervals only when the estimator's inference procedure matches independent/clustered/time-series sampling. Do not attach generic bootstrap/OLS intervals that ignore neighbor reuse or sample selection.

## 9. What Complete Journey can establish

The current sample serves dunnhumby Complete Journey through PostgreSQL/Cube. A Databricks-related data source does not mean the current connector was tested against Databricks.

Useful coverage: connection, catalog, permission path, time/population filters, entity grain, extraction limits, missing/duplicate observations, execution evidence, SQL comparisons for descriptive/OLS/window calculations, and refusal under inadequate support. Reuse existing journey scenarios.

Insufficient coverage: known causal effects, randomized assignment, actual campaign receipt timestamps, complete follow-up for every unit, parallel trends, or absence of unmeasured confounding. Campaign-household data has nonrandom targeting, overlapping campaigns and fixed 30-day pre/post windows. Repeated households across campaigns are not iid units. Existing sample experiments refused support even with asserted assumptions; do not weaken thresholds merely to obtain an answer.

Complete Journey was not rerun for this review. Data/scenario code and existing validation evidence were inspected; new numerical checks used synthetic data. Next, extend synthetic regression tests to nonlinear response, non-overlap, omitted confounding, heterogeneity, clusters and multiple seeds. One successful DGP cannot support general accuracy claims.

## 10. Versions, dependencies and upgrade cost

| Item | Current supported environment | Isolated upgrade experiment |
| --- | --- | --- |
| DoWhy | 0.13 | 0.14 |
| EconML | 0.16.0 | 0.16.0 |
| NumPy | 1.26.4 | 2.2.6 |
| pandas / SciPy / sklearn | 2.3.3 / 1.15.3 / 1.6.1 | Same |
| statsmodels / Python | 0.15.0 / 3.11.14 | Same |
| New experiments | Numerical/refusal/typed adapter/notebook cells | Same tests |

DoWhy 0.14 distribution metadata requires NumPy >2.0, conflicting with the current extras/builtin NumPy <2 constraint. Changing one version string is insufficient. DoWhy 0.13 itself does not require NumPy <2 on Python 3.11. EconML 0.16 also constrains sklearn <1.7 and SHAP. [0.14 distribution metadata](https://pypi.org/pypi/dowhy/0.14/json), [0.14 release](https://github.com/py-why/dowhy/releases/tag/v0.14).

```bash
python3.11 -m venv .venv-pywhy-014
.venv-pywhy-014/bin/python -m pip install -e '.[dev,stats]' 'dowhy==0.14' 'econml==0.16.0' -c examples/methods/pywhy_review/constraints-014-py311.txt
.venv-pywhy-014/bin/python -m examples.methods.pywhy_review.experiment
.venv-pywhy-014/bin/python -m pytest -q examples/methods/pywhy_review/test_review.py
```

The isolated 0.14 numerical experiment passed but recorded NumPy matrix-operation overflow/invalid/divide-by-zero warnings. Finite estimates near expected values do not justify ignoring warnings and declaring production support. Investigating their origin/platform reproducibility and choosing a warning policy remain upgrade gates. The 0.13 pandas positional-indexing warning and string-wrapper deprecation on both versions were also recorded.

Runtime never installs dependencies. Contributors install a reviewed extra/constraints set once; deployments use controlled environments. Core users need not install a causal stack. Upgrades include NumPy/compiled-dependency compatibility, forwarding contracts, numerical/refusal/inference regressions and lock maintenance.

## 11. Implementation, migration and documentation plan

This is a recommendation, not a completed production migration.

1. **Interpretation contract:** distinguish matched comparison, association and conditional causal interpretation; record estimand, contrast, intended/actual population and unverified assumptions. Correct labeling in a new Method ID/version contract, leaving existing CEM unchanged.
2. **Small shared checks:** extract only genuinely duplicated unit, encoding, contrast, support and selection-evidence logic. Keep estimator-specific conditions in its helper. No automatic algorithm selection or arbitrary kwargs.
3. **Promote reviewed estimators:** validate native binary matching/regression, then direct categorical/continuous DML against real sources and refusal contracts. ATT/CATE require evaluation-population and modifier-omission regression tests. CI remains unsupported pending separate review.
4. **Compatibility:** retain CEM 1.1.1 and historical Run artifacts without automatic recalculation/relabeling. The current registry stores one implementation per name; registering two versions under one ID does not provide coexistence. Use separate IDs or implement version resolution first. Do not alias pinned Recipes automatically: clone, explicitly opt in, shadow-compare, then pin the new version. Removal needs a separate decision based on usage, replacement coverage and retention/replay policy.
5. **Interface verification:** execute identical canonical specs through Python/REST/MCP/Web and compare versions, contrasts, queries and refusal status. Local adapter tests do not replace these checks. Regression-test execution limits and server compute termination too.
6. **Documentation:** organize VitePress around first connection → object selection → single query → multiple queries → entity roles → Python experiment → pytest failures → optional notebook → registration/sharing. English/Korean use the same code includes and scenario IDs. This page links the existing authoring/scenario flow; maintain support tables and refusal explanations alongside the API reference.

## 12. Product wording

Recommended: **“Run reviewed DoWhy- and EconML-backed analysis Methods on governed semantic data, with inspectable assumptions, validation and execution evidence.”**

“PyWhy-friendly” is reasonable when accompanied by ordinary Python integration and explicit tested scope. “All PyWhy estimators supported,” “automatic causal inference,” and “causality verified by refutation” exceed current evidence. Multicategorical/continuous treatment remains experimental here, not default product support. Do not imply official PyWhy certification or affiliation.
