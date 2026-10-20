"""Match similar observations and report an observed group difference."""

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors
from decision_layer.methods import Column, DataInput, python_method
from decision_layer.methods.context import Refused


def check_data(data, outcome="outcome", treatment="treatment", confounders=None):
    """Check the two groups and required observations."""
    if data["entity_id"].isna().any() or data["entity_id"].duplicated().any():
        raise ValueError("Entity IDs must be present and unique.")
    confounders = (
        confounders
        if confounders is not None
        else [name for name in data if name.startswith("confounders_")]
    )
    columns = [outcome, treatment, *confounders]
    if len(set(columns)) != len(columns):
        raise ValueError("Analysis variables must use distinct columns.")
    if not confounders:
        raise ValueError("Select at least one covariate.")
    values = data[columns]
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("Analysis variables must be finite and non-null.")
    if set(data[treatment].unique()) != {0, 1}:
        raise ValueError("Treatment must contain both 0 and 1, with no other values.")
    if data.groupby(treatment).size().min() < 30:
        raise ValueError("Each group needs at least 30 observations.")


def matching(data, outcome, treatment, confounders):
    """Compare outcomes after matching observations on measured covariates."""
    check_data(data, outcome, treatment, confounders)
    treated = data[treatment].to_numpy() == 1
    covariates = data[confounders]
    scale = covariates.std(ddof=0)
    if not np.isfinite(scale).all() or (scale <= 0).any():
        raise Refused("Covariates must have finite, positive variation.")
    standardized = (covariates - covariates.mean()) / scale
    propensity = LogisticRegression(max_iter=1000, random_state=7).fit(
        standardized, data[treatment]
    )
    probabilities = propensity.predict_proba(standardized)[:, 1]
    if (probabilities < 0.05).any() or (probabilities > 0.95).any():
        raise Refused("The groups have insufficient propensity overlap.")
    neighbors = NearestNeighbors(n_neighbors=1, algorithm="brute", n_jobs=1).fit(
        standardized.loc[~treated]
    )
    distances, indices = neighbors.kneighbors(standardized.loc[treated])
    matched_positions = np.flatnonzero(~treated)[indices[:, 0]]
    if len(set(matched_positions)) < 30:
        raise Refused("At least 30 distinct matched controls are required.")
    if float(distances.max()) > 1.0:
        raise Refused("Matched observations exceed the permitted distance.")
    target_covariates = covariates.loc[treated]
    control_covariates = covariates.loc[~treated]
    pooled = np.sqrt(
        (target_covariates.var(ddof=1) + control_covariates.var(ddof=1)) / 2
    )
    if not np.isfinite(pooled).all() or (pooled <= 0).any():
        raise Refused("Covariates must vary within groups.")
    balance = (
        target_covariates.mean() - covariates.iloc[matched_positions].mean()
    ) / pooled
    if balance.abs().max() > 0.1:
        raise Refused("Matched covariate imbalance exceeds the permitted threshold.")
    differences = (
        data.loc[treated, outcome].to_numpy()
        - data.iloc[matched_positions][outcome].to_numpy()
    )
    if not np.isfinite(differences).all():
        raise Refused("Outcome differences exceed the finite numeric range.")
    return {
        "value": float(differences.mean()),
        "n_treated": int(treated.sum()),
        "n_unique_matched_controls": len(set(matched_positions)),
        "matching_with_replacement": True,
        "max_distance": float(distances.max()),
        "balance": {name: float(value) for name, value in balance.items()},
        "target": "treated_group",
        "causal_claim": "not_established",
        "uncertainty": "not_reported",
    }


METHOD = python_method(
    matching,
    name="stats.binary_matching",
    version="2.0.0",
    label="Matching",
    inputs={
        "data": DataInput(
            columns={
                "entity_id": Column(source="dimension", role="entity_key"),
                "outcome": Column(source="measure", dtype="number"),
                "treatment": Column(source="dimension", dtype="number"),
                "confounders": Column(
                    source=["measure", "dimension"], dtype="number", multiple=True
                ),
            },
            minimum_rows=60,
        )
    },
    checks=[check_data],
    output="estimate",
    provides=["matched_comparison"],
    requires_packages={"scikit-learn": ">=1.6,<2", "pandas": ">=2.2,<3"},
)
