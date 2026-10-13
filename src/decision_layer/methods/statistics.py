"""Ordinary Python statistical helpers; no provider access or invented semantics."""
from __future__ import annotations
from ..i18n import _
from .context import Refused


def _units(frame, columns):
    import numpy as np
    if frame.empty or frame["unit"].isna().any() or frame["unit"].duplicated().any():
        raise Refused(_("The analysis requires unique non-null independent units"))
    if frame[columns].isna().any().any():
        raise Refused(_("Missing observations require an explicit analysis policy"))
    if not np.isfinite(frame["outcome"].to_numpy(dtype=float)).all():
        raise Refused(_("Outcomes must be finite"))


def _covariates(frame, columns):
    import numpy as np
    import pandas as pd
    if not columns:
        raise Refused(_("Select at least one pre-treatment covariate"))
    if frame[columns].isna().any().any():
        raise Refused(_("Missing observations require an explicit analysis policy"))
    encoded_width = sum(max(frame[name].nunique() - 1, 0) if not pd.api.types.is_numeric_dtype(frame[name]) else 1
                        for name in columns)
    if encoded_width > 100 or encoded_width * len(frame) > 2_000_000:
        raise Refused(_("Categorical encoding exceeds the statistical matrix bound"))
    encoded = pd.get_dummies(frame[columns], drop_first=True, dtype=float)
    mapping = {f"feature_{index}": str(name) for index, name in enumerate(encoded.columns)}
    encoded.columns = [f"feature_{index}" for index in range(len(encoded.columns))]
    encoded.attrs["encoding"] = mapping
    if not len(encoded.columns) or not np.isfinite(encoded.to_numpy(dtype=float)).all():
        raise Refused(_("Covariates must have observed variation and finite encoded values"))
    return encoded


def fit_ols(frame, columns):
    import numpy as np
    import statsmodels.api as sm
    _units(frame, ["outcome", *columns])
    encoded = _covariates(frame, columns)
    x = sm.add_constant(encoded, has_constant="add")
    if len(frame) <= x.shape[1] or np.linalg.matrix_rank(x.to_numpy(dtype=float)) < x.shape[1]:
        raise Refused(_("Regression requires full-rank predictors and residual degrees of freedom"))
    fit = sm.OLS(frame["outcome"].to_numpy(dtype=float), x, missing="raise").fit()
    return {"rows": [{"term": name, "input_column": encoded.attrs["encoding"].get(name, "intercept"),
                       "coefficient": float(value)} for name, value in fit.params.items()],
            "n_units": len(frame), "encoded_columns": list(x.columns),
            "statistical_judgement": "not_tested"}


def _binary_support(frame, encoded):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    if set(frame["treatment"].unique()) != {0, 1}:
        raise Refused(_("This estimator requires binary treatment and both groups"))
    if frame.groupby("treatment").size().min() < 30:
        raise Refused(_("This estimator requires at least 30 units in each treatment group"))
    model = LogisticRegression(max_iter=1000, random_state=7).fit(encoded, frame["treatment"])
    probability = model.predict_proba(encoded)[:, 1]
    if np.any(probability < .05) or np.any(probability > .95):
        raise Refused(_("Observed propensity support fails the estimator diagnostic"))
    return {"minimum": float(probability.min()), "maximum": float(probability.max()),
            "basis": "fitted_logistic_propensity", "thresholds": [.05, .95]}


def fit_dowhy(frame, columns, design, seed):
    import pandas as pd
    import networkx as nx
    from dowhy import CausalModel
    _units(frame, ["outcome", "treatment", *columns])
    encoded = _covariates(frame, columns)
    support = _binary_support(frame, encoded)
    observations = pd.concat([frame[["outcome", "treatment"]].reset_index(drop=True),
                              encoded.reset_index(drop=True)], axis=1)
    edges = [("treatment", "outcome")]
    edges += [(name, destination) for name in encoded.columns for destination in ("treatment", "outcome")]
    model = CausalModel(data=observations, treatment="treatment", outcome="outcome", graph=nx.DiGraph(edges))
    estimand = model.identify_effect(proceed_when_unidentifiable=False)
    if not (estimand.estimands.get("backdoor") or {}).get("estimand"):
        raise Refused(_("No backdoor estimand is identified under the supplied assumptions"))
    estimate = model.estimate_effect(estimand, method_name="backdoor.linear_regression",
                                     control_value=0, treatment_value=1, target_units="ate")
    placebo = model.refute_estimate(estimand, estimate, method_name="placebo_treatment_refuter",
                                    placebo_type="permute", num_simulations=20, random_state=seed)
    return {"value": float(estimate.value), "placebo_difference": float(placebo.new_effect),
            "estimand": str(estimand), "graph_edges": edges, "n_units": len(frame),
            "support": support, "encoding": encoded.attrs["encoding"], "design": design, "assumptions_status": "author_asserted",
            "seed": seed, "refutations": 20, "causal_claim": "not_established",
            "statistical_judgement": "not_tested"}


def fit_dml(frame, columns, design, seed):
    import numpy as np
    from econml.dml import LinearDML
    from sklearn.linear_model import LinearRegression, LogisticRegression
    _units(frame, ["outcome", "treatment", *columns])
    encoded = _covariates(frame, columns)
    support = _binary_support(frame, encoded)
    estimator = LinearDML(model_y=LinearRegression(), model_t=LogisticRegression(max_iter=1000),
                           discrete_treatment=True, cv=3, random_state=seed)
    estimator.fit(frame["outcome"].to_numpy(dtype=float), frame["treatment"].to_numpy(),
                  W=encoded.to_numpy(), X=None, inference=None)
    return {"value": float(np.asarray(estimator.ate(X=None)).item()), "n_units": len(frame),
            "support": support, "encoding": encoded.attrs["encoding"], "design": design, "assumptions_status": "author_asserted",
            "seed": seed, "estimator": "LinearDML", "cv": 3,
            "causal_claim": "not_established", "statistical_judgement": "not_tested"}


def fit_did(panel, design):
    import numpy as np
    import pandas as pd
    pre, post = design.get("pre_period"), design.get("post_period")
    if not pre or not post or pre >= post:
        raise Refused(_("Specify ordered pre and post period buckets"))
    if panel.empty or panel[["unit", "time", "treated", "outcome"]].isna().any().any():
        raise Refused(_("The panel requires complete non-null observations"))
    frame = panel.copy()
    try:
        timestamps = pd.to_datetime(frame["time"], errors="raise")
        frame["time"] = timestamps.dt.strftime("%Y-%m" if len(pre) == 7 and len(post) == 7 else "%Y-%m-%d")
    except (ValueError, TypeError) as exc:
        raise Refused(_("Panel observations require valid time buckets")) from exc
    if set(frame["time"].unique()) != {pre, post}:
        raise Refused(_("This estimator supports exactly two common period buckets"))
    if frame.duplicated(["unit", "time"]).any() or not frame.groupby("unit").size().eq(2).all():
        raise Refused(_("The panel requires one observation per unit in both periods"))
    if set(frame["treated"].unique()) != {0, 1} or not frame.groupby("unit")["treated"].nunique().eq(1).all():
        raise Refused(_("This estimator requires two fixed treatment groups"))
    frame["treated"] = frame["treated"].astype(int)
    if not np.isfinite(frame["outcome"].to_numpy(dtype=float)).all():
        raise Refused(_("Outcomes must be finite"))
    means = frame.groupby(["treated", "time"])["outcome"].mean()
    target = float(means.loc[1, post] - means.loc[1, pre])
    comparison = float(means.loc[0, post] - means.loc[0, pre])
    return {"value": target - comparison, "treated_change": target, "comparison_change": comparison,
            "n_units": int(frame["unit"].nunique()), "design": design,
            "assumptions_status": "author_asserted", "causal_claim": "not_established",
            "statistical_judgement": "not_tested"}


def estimate_binary_regression(frame, confounder_columns):
    """Estimate the 0-to-1 contrast under an explicitly assumed backdoor graph."""
    import networkx as nx
    import numpy as np
    import pandas as pd
    from dowhy import CausalModel
    from sklearn.linear_model import LogisticRegression

    # 1. Check the observation units, missing values and treatment groups.
    if (
        frame.empty
        or frame["unit"].isna().any()
        or frame["unit"].duplicated().any()
    ):
        raise Refused("Unique non-null analysis units are required")

    required_columns = ["outcome", "treatment", *confounder_columns]
    if not confounder_columns or frame[required_columns].isna().any().any():
        raise Refused(
            "Observed adjustment variables and a missing-data policy are required"
        )

    if (
        set(frame["treatment"].unique()) != {0, 1}
        or frame.groupby("treatment").size().min() < 30
    ):
        raise Refused(
            "This example requires binary treatment and at least 30 units per arm"
        )

    # 2. Bound encoding before allocating the matrix.
    encoded_width = sum(
        1 if pd.api.types.is_numeric_dtype(frame[column]) else max(frame[column].nunique() - 1, 0)
        for column in confounder_columns
    )
    if encoded_width == 0 or encoded_width > 100 or encoded_width * len(frame) > 2_000_000:
        raise Refused("Adjustment encoding is empty or exceeds the matrix bound")
    encoded = pd.get_dummies(
        frame[confounder_columns],
        drop_first=True,
        dtype=float,
    )
    if (
        not len(encoded.columns)
        or len(encoded.columns) > 100
        or encoded.size > 2_000_000
    ):
        raise Refused("Adjustment encoding is empty or exceeds the matrix bound")

    encoded.columns = [f"adjustment_{i}" for i in range(len(encoded.columns))]

    if (
        not np.isfinite(frame["outcome"].to_numpy(dtype=float)).all()
        or not np.isfinite(encoded.to_numpy()).all()
    ):
        raise Refused("Finite outcomes and adjustment variables are required")

    observations = pd.concat(
        [
            frame[["outcome", "treatment"]].reset_index(drop=True),
            encoded.reset_index(drop=True),
        ],
        axis=1,
    )

    predictor_columns = ["treatment", *encoded.columns]
    predictors = observations[predictor_columns].to_numpy(dtype=float)
    matrix = np.column_stack([np.ones(len(frame)), predictors])

    if (
        len(frame) <= matrix.shape[1]
        or np.linalg.matrix_rank(matrix) < matrix.shape[1]
    ):
        raise Refused(
            "The regression needs full-rank predictors and residual degrees of freedom"
        )

    # 3. Diagnose observed treatment support. This does not prove positivity.
    propensity = LogisticRegression(
        max_iter=1000,
        random_state=7,
    ).fit(encoded, frame["treatment"])
    probability = propensity.predict_proba(encoded)[:, 1]

    if np.any(probability < 0.05) or np.any(probability > 0.95):
        raise Refused(
            "Observed support fails this example's diagnostic; not a positivity proof"
        )

    # 4. Declare the assumed DAG and identify its backdoor estimand.
    edges = [("treatment", "outcome")]
    edges += [
        (column, target)
        for column in encoded.columns
        for target in ("treatment", "outcome")
    ]
    model = CausalModel(
        data=observations,
        treatment="treatment",
        outcome="outcome",
        graph=nx.DiGraph(edges),
    )
    estimand = model.identify_effect(proceed_when_unidentifiable=False)

    if not (estimand.estimands.get("backdoor") or {}).get("estimand"):
        raise Refused("No backdoor estimand is identified under the assumed graph")

    # 5. Fit the explicit binary regression contrast and a placebo diagnostic.
    estimate = model.estimate_effect(
        estimand,
        method_name="backdoor.linear_regression",
        control_value=0,
        treatment_value=1,
        target_units="ate",
        confidence_intervals=False,
    )
    placebo = model.refute_estimate(
        estimand,
        estimate,
        method_name="placebo_treatment_refuter",
        placebo_type="permute",
        num_simulations=20,
        random_state=7,
    )

    # 6. Return the estimate with its analysis settings and interpretation limits.
    return {
        "value": float(estimate.value),
        "estimator": "backdoor.linear_regression",
        "contrast": [0, 1],
        "target": "ate",
        "n_units": len(frame),
        "graph_edges": edges,
        "estimand": str(estimand),
        "placebo_difference": float(placebo.new_effect),
        "seed": 7,
        "support": {
            "min": float(probability.min()),
            "max": float(probability.max()),
        },
        "causal_claim": "not_established",
        "uncertainty": "not_reported",
        "assumptions_status": "not_verified",
    }



def estimate_linear_dml(frame, columns):
    import numpy as np
    from econml.dml import LinearDML
    from sklearn.linear_model import LinearRegression, LogisticRegression
    _units(frame, ["outcome", "treatment", *columns])
    encoded = _covariates(frame, columns)
    support = _binary_support(frame, encoded)
    model = LinearDML(
        model_y=LinearRegression(), model_t=LogisticRegression(max_iter=1000),
        discrete_treatment=True, cv=3, random_state=7,
    )
    model.fit(frame["outcome"].to_numpy(dtype=float), frame["treatment"].to_numpy(),
              W=encoded.to_numpy(), X=None, inference=None)
    return {"value": float(np.asarray(model.ate(X=None)).item()), "n_units": len(frame),
            "support": support, "encoding": encoded.attrs["encoding"], "estimator": "LinearDML",
            "seed": 7, "cv": 3, "contrast": [0, 1], "target": "ate",
            "assumptions_status": "not_verified", "causal_claim": "not_established",
            "uncertainty": "not_reported", "statistical_judgement": "not_tested"}


def estimate_two_period_contrast(panel, granularity):
    import pandas as pd
    if panel.empty or panel[["unit", "time", "treated", "outcome"]].isna().any().any():
        raise Refused(_("The panel requires complete non-null observations"))
    try:
        timestamps = pd.to_datetime(panel["time"], errors="raise")
        buckets = sorted(timestamps.dt.strftime("%Y-%m" if granularity == "month" else "%Y-%m-%d").unique())
    except (ValueError, TypeError) as exc:
        raise Refused(_("Panel observations require valid time buckets")) from exc
    if len(buckets) != 2:
        raise Refused(_("This estimator supports exactly two common period buckets"))
    # The complete scope must contain exactly two buckets. Never choose endpoints from a longer panel.
    result = fit_did(panel, {"pre_period": buckets[0], "post_period": buckets[1]})
    result.pop("design")
    result.update(assumptions_status="not_verified", pre_period=buckets[0], post_period=buckets[1])
    return result
