"""Binary regression adjustment with the native DoWhy API."""

from decision_layer.methods import (
    Dimension,
    Entity,
    Estimate,
    Measure,
    Refused,
    method,
)


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
    }


@method(
    "workshop.binary_regression",
    version="1.0.0",
    execution="dataframe",
    requires_packages={
        "dowhy": "==0.13",
        "numpy": ">=1.26,<2",
        "pandas": ">=2.2,<3",
        "scikit-learn": ">=1.2,<1.7",
    },
)
async def my_binary_regression(
    ctx,
    *,
    outcome: Measure,
    treatment: Dimension,
    confounders: list[Dimension | Measure],
    unit: Entity,
) -> Estimate:
    # Extract governed entity data, then run ordinary Python calculation code.
    observations = await ctx.entities(
        entity=unit,
        measures={"outcome": outcome},
        dimensions={
            "treatment": treatment,
            "confounders": confounders,
        },
    )
    payload = await ctx.compute(
        estimate_binary_regression,
        observations.frame,
        observations.columns("confounders"),
    )

    return Estimate(
        payload["value"],
        details={
            **payload,
            "assumptions_status": "not_verified",
        },
        warnings=[
            "Unverified assumptions and placebo diagnostics do not establish "
            "causality; no interval is reported."
        ],
    )
