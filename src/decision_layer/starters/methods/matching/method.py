"""Match similar observations and report an observed group difference."""

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors
from decision_layer.methods import Column, DataInput, python_method
from decision_layer.methods.context import Refused
from .checks import check_data, check_matches, check_overlap, standardize


def matching(data, outcome, treatment, confounders):
    """Compare outcomes after matching observations on measured covariates."""
    check_data(data, outcome, treatment, confounders)
    treated = data[treatment].to_numpy() == 1
    covariates = data[confounders]
    standardized = standardize(covariates)
    # Check that similar observations exist in both groups.
    propensity = LogisticRegression(max_iter=1000, random_state=7).fit(
        standardized, data[treatment]
    )
    probabilities = propensity.predict_proba(standardized)[:, 1]
    check_overlap(probabilities)

    # Find the closest control for each treated observation. Controls may be reused.
    neighbors = NearestNeighbors(n_neighbors=1, algorithm="brute", n_jobs=1).fit(
        standardized.loc[~treated]
    )
    distances, indices = neighbors.kneighbors(standardized.loc[treated])
    matched_positions = np.flatnonzero(~treated)[indices[:, 0]]
    balance = check_matches(covariates, treated, matched_positions, distances)

    # Average the observed differences. This alone does not establish causality.
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
    version="2.1.0",
    label="Matching",
    inputs={
        "data": DataInput(
            columns={
                "entity_id": Column(
                    source="dimension",
                    role="entity_key",
                    description="ID for each observation",
                ),
                "outcome": Column(
                    source="measure", dtype="number", description="Value to compare"
                ),
                "treatment": Column(
                    source="dimension",
                    dtype="number",
                    description="Group indicator (0 or 1)",
                ),
                "confounders": Column(
                    source=["measure", "dimension"],
                    dtype="number",
                    multiple=True,
                    description="Variables used to match similar observations",
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
