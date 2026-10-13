"""Same-data PyWhy route comparison. Explicit numerical experiments, not causal proof."""
from __future__ import annotations
import json
import warnings
from importlib.metadata import version
import numpy as np
import pandas as pd
from decision_layer.methods import Refused

SEED = 17


def data(kind="binary", n=4000):
    rng = np.random.default_rng(SEED)
    w = rng.uniform(0, 1, n) if kind == "binary" else rng.binomial(1, .5, n)
    x = rng.binomial(1, .5, n)
    if kind == "categorical":
        labels = np.array(["control", "basic", "plus"])
        t = np.array([rng.choice(labels, p=[.5-.2*z, .3, .2+.2*z]) for z in w])
        signal = np.select([t == "basic", t == "plus"], [2., 5.], default=0.)
    elif kind == "continuous":
        t = w + rng.normal(0, 1, n)
        signal = 2*t
    elif kind == "heterogeneous":
        t = rng.binomial(1, .2+.6*x)
        signal = (1+2*x)*t
    else:
        t = rng.binomial(1, .1+.8*w)
        signal = 2*t
    return pd.DataFrame({"unit": np.arange(n).astype(str), "outcome": signal+3*w+rng.normal(0, .25, n),
                         "treatment": t, "w": w, "x": x})


def validate(frame, kind, control, treated):
    """Small experimental policy; thresholds diagnose this experiment, not identification."""
    from sklearn.linear_model import LogisticRegression
    if kind not in ("binary", "categorical", "continuous", "heterogeneous"):
        raise Refused("Unsupported treatment type")
    if frame.empty or frame.unit.isna().any() or frame.unit.duplicated().any():
        raise Refused("Unique non-null analysis units are required")
    if frame[["outcome", "treatment", "w", "x"]].isna().any().any():
        raise Refused("Missing values require a declared policy")
    if not np.isfinite(frame[["outcome", "w", "x"]].to_numpy(dtype=float)).all():
        raise Refused("Finite outcomes and covariates are required")
    if control == treated:
        raise Refused("The treatment contrast needs distinct values")
    if kind == "continuous":
        t = frame.treatment.to_numpy(dtype=float)
        if not np.isfinite(t).all() or np.std(t) < 1e-8:
            raise Refused("Continuous treatment needs finite residual variation")
        # Synthetic W has two exact levels. This is a stratum-range diagnostic only.
        if any(not (g.treatment.min() <= min(control, treated) < max(control, treated) <= g.treatment.max())
               for _, g in frame.groupby("w")):
            raise Refused("Contrast lies outside observed within-stratum treatment ranges")
    else:
        categories = [0, 1] if kind != "categorical" else ["control", "basic", "plus"]
        if set(frame.treatment.unique()) != set(categories) or control not in categories or treated not in categories:
            raise Refused("Expected treatment categories and explicit contrast are required")
        if frame.groupby("treatment").size().min() < 30:
            raise Refused("At least 30 observations per arm are required by this experiment")
        covariates = ["w", "x"] if kind == "heterogeneous" else ["w"]
        prop = LogisticRegression(max_iter=2000).fit(frame[covariates], frame.treatment).predict_proba(frame[covariates])
        if prop.min() < .02 or prop.max() > .98:
            raise Refused("Observed fitted propensity support fails the experimental diagnostic")


def causal_model(frame, *, heterogeneous=False):
    import networkx as nx
    from dowhy import CausalModel
    causes = ["w", "x"] if heterogeneous else ["w"]
    graph = nx.DiGraph([("treatment", "outcome"), *[(c, dst) for c in causes for dst in ("treatment", "outcome")]])
    model = CausalModel(data=frame, treatment="treatment", outcome="outcome", graph=graph,
                        effect_modifiers=["x"] if heterogeneous else [])
    identified = model.identify_effect(proceed_when_unidentifiable=False)
    if not (identified.estimands.get("backdoor") or {}).get("estimand"):
        raise Refused("No backdoor estimand identified under this graph")
    return model, identified


def dml_init(kind):
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.model_selection import KFold, StratifiedKFold
    discrete = kind != "continuous"
    return {"model_y": LinearRegression(),
            "model_t": LogisticRegression(max_iter=2000) if discrete else LinearRegression(),
            "discrete_treatment": discrete,
            "categories": ["control", "basic", "plus"] if kind == "categorical" else [0, 1] if discrete else "auto",
            "cv": StratifiedKFold(3, shuffle=True, random_state=SEED) if discrete else KFold(3, shuffle=True, random_state=SEED),
            "random_state": SEED}


#region dowhy_native
def native(frame, backend="linear", target="ate"):
    validate(frame, "binary", 0, 1)
    model, identified = causal_model(frame)
    options = {"init_params": {"num_matches_per_unit": 1, "distance_metric": "euclidean"}} if backend == "matching" else {}
    estimate = model.estimate_effect(identified,
        method_name="backdoor.distance_matching" if backend == "matching" else "backdoor.linear_regression",
        control_value=0, treatment_value=1, target_units=target, confidence_intervals=False, method_params=options)
    return float(estimate.value)
#endregion dowhy_native


#region dml_routes
def dml(frame, kind, *, route="direct", control=0, treated=1, target="ate"):
    validate(frame, kind, control, treated)
    if target not in ("ate", "att", "att_explicit"):
        raise Refused("Unsupported target population")
    heterogeneous = kind == "heterogeneous"
    if target != "ate" and not heterogeneous:
        raise Refused("This experiment only evaluates ATT with explicit heterogeneous features")
    if route == "wrapper":
        model, identified = causal_model(frame, heterogeneous=heterogeneous)
        # The "att" string is deliberately exercised as a failing population
        # contract in run(); never promote that route as a production ATT API.
        target_units = (lambda rows: rows.treatment == treated) if target == "att_explicit" else target
        estimate = model.estimate_effect(identified, method_name="backdoor.econml.dml.LinearDML",
            control_value=control, treatment_value=treated, target_units=target_units,
            effect_modifiers=["x"] if heterogeneous else [],
            confidence_intervals=False, method_params={"init_params": dml_init(kind), "fit_params": {"inference": None}})
        return float(np.asarray(estimate.value).item())
    if route != "direct":
        raise Refused("Only reviewed direct or wrapper routes are allowed")
    from econml.dml import LinearDML
    x = frame[["x"]].to_numpy() if heterogeneous else None
    # DoWhy's graph-derived adjustment includes x as well as w in the heterogeneous case.
    w = frame[["w", "x"] if heterogeneous else ["w"]].to_numpy()
    fit = LinearDML(**dml_init(kind))
    fit.fit(frame.outcome.to_numpy(), frame.treatment.to_numpy(), X=x, W=w, inference=None)
    evaluation = x[frame.treatment.to_numpy() == treated] if target != "ate" else x
    return float(np.asarray(fit.ate(X=evaluation, T0=control, T1=treated)).item())
#endregion dml_routes


def cem_kernel(frame):
    """Evaluate existing target-weighted CEM arithmetic; no provider path is simulated here."""
    from decision_layer.methods.matching import Cell, Stratum, match, TARGET, COMPARISON
    strata, balance = [], []
    bins = np.digitize(frame.w, [.5])
    for bucket in (0, 1):
        t = frame[(bins == bucket) & (frame.treatment == 1)]
        c = frame[(bins == bucket) & (frame.treatment == 0)]
        strata.append(Stratum(bucket, {"w_bin": bucket}, {TARGET: Cell(len(t), t.outcome.mean()), COMPARISON: Cell(len(c), c.outcome.mean())}))
        balance.append((len(t), t.w.mean()-c.w.mean()))
    result = match(strata, {}, {})
    return {"estimate": result["target_kpi"]-result["comparison_kpi"],
            "coarsened_imbalance_after": result["balance"]["imbalance_after"],
            "remaining_w_difference": sum(n*d for n, d in balance)/sum(n for n, d in balance),
            "retention": result["balance"]["target_retention"]}


def run():
    import statsmodels.api as sm
    report = {"versions": {p: version(p) for p in ("dowhy", "econml", "numpy", "pandas", "scipy", "scikit-learn", "statsmodels")},
              "seed": SEED, "n": 4000, "uncertainty": "not_reported", "causal_claim": "not_established"}
    b = data()
    report["binary"] = {"truth": 2., "matching_att": native(b, "matching", "att"), "regression_ate": native(b),
        "direct_dml": dml(b, "binary"), "wrapped_dml": dml(b, "binary", route="wrapper"), "cem": cem_kernel(b)}
    report["binary"]["ols_treatment_coefficient"] = float(sm.OLS(b.outcome, sm.add_constant(b[["treatment", "w"]])).fit().params["treatment"])
    for kind, t0, t1, truth in [("categorical", "basic", "plus", 3.), ("continuous", .5, 1.5, 2.)]:
        f = data(kind)
        report[kind] = {"control": t0, "treated": t1, "truth": truth,
            "direct": dml(f, kind, control=t0, treated=t1),
            "wrapped": dml(f, kind, route="wrapper", control=t0, treated=t1)}
    h = data("heterogeneous")
    report["heterogeneous"] = {"ate_truth": float((1+2*h.x).mean()),
        "att_truth": float((1+2*h.loc[h.treatment == 1, "x"]).mean()),
        "direct_ate": dml(h, "heterogeneous"), "direct_att": dml(h, "heterogeneous", target="att"),
        "wrapped_ate": dml(h, "heterogeneous", route="wrapper"),
        "wrapped_att_string": dml(h, "heterogeneous", route="wrapper", target="att"),
        "wrapped_att_explicit": dml(h, "heterogeneous", route="wrapper", target="att_explicit")}
    model, identified = causal_model(b)
    estimate = model.estimate_effect(identified, method_name="backdoor.linear_regression")
    placebo = model.refute_estimate(identified, estimate, method_name="placebo_treatment_refuter",
                                   placebo_type="permute", num_simulations=20, random_state=SEED)
    report["placebo_difference"] = float(placebo.new_effect)
    verify(report)
    return report


def verify(report):
    b = report["binary"]
    for key in ("matching_att", "regression_ate", "direct_dml", "wrapped_dml", "ols_treatment_coefficient"):
        assert abs(b[key]-2) < .15, (key, b[key])
    assert abs(b["ols_treatment_coefficient"]-b["regression_ate"]) < 1e-8
    for kind in ("categorical", "continuous"):
        item = report[kind]
        assert abs(item["direct"]-item["truth"]) < .15
        assert abs(item["wrapped"]-item["direct"]) < .02
    h = report["heterogeneous"]
    for key, truth in [("direct_ate", "ate_truth"), ("direct_att", "att_truth"), ("wrapped_att_explicit", "att_truth")]:
        assert abs(h[key]-h[truth]) < .15, (key, h)
    assert abs(h["wrapped_att_string"]-h["wrapped_ate"]) < 1e-8
    assert b["cem"]["coarsened_imbalance_after"] == 0 and b["cem"]["remaining_w_difference"] > .03


if __name__ == "__main__":
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        result = run()
    result["backend_warnings"] = sorted(set(str(w.message) for w in observed))
    print(json.dumps(result, ensure_ascii=False, indent=2))
