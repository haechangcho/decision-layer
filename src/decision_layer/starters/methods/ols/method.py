"""Calculate numeric OLS with one row per observational unit."""

import numpy as np
import statsmodels.api as sm
from decision_layer.methods import Column, DataInput, python_method


def check_data(data, outcome="outcome", treatment="treatment", confounders=None):
    """Check unique units, finite values and an identifiable regression design."""
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
    if not np.isfinite(data[columns].to_numpy(dtype=float)).all():
        raise ValueError("Analysis variables must be finite and non-null.")
    if data[outcome].nunique() < 2:
        raise ValueError("The outcome must vary.")
    predictors = [name for name in columns if name != outcome]
    design = sm.add_constant(data[predictors], has_constant="add")
    if len(data) <= design.shape[1]:
        raise ValueError(
            "The number of rows must exceed the number of regression coefficients."
        )
    if np.linalg.matrix_rank(design) < design.shape[1]:
        raise ValueError(
            "Predictors are linearly dependent. Review the selected variables."
        )


def ols(data, outcome, treatment, confounders):
    """Estimate the outcome association with treatment, adjusting for covariates."""
    check_data(data, outcome, treatment, confounders)
    design = sm.add_constant(data[[treatment, *confounders]], has_constant="add")
    fit = sm.OLS(data[outcome], design, missing="raise").fit()
    return {
        "value": float(fit.params[treatment]),
        "n_observations": int(fit.nobs),
        "r_squared": float(fit.rsquared),
        "coefficients": {name: float(value) for name, value in fit.params.items()},
        "causal_claim": "not_established",
        "uncertainty": "not_reported",
    }


METHOD = python_method(
    ols,
    name="stats.regression_adjustment",
    version="2.0.0",
    label="OLS regression",
    inputs={
        "data": DataInput(
            columns={
                "entity_id": Column(source="dimension", role="entity_key"),
                "outcome": Column(source="measure", dtype="number"),
                "treatment": Column(source=["measure", "dimension"], dtype="number"),
                "confounders": Column(
                    source=["measure", "dimension"], dtype="number", multiple=True
                ),
            },
            minimum_rows=60,
        )
    },
    checks=[check_data],
    output="estimate",
    requires_packages={"statsmodels": ">=0.14,<0.16", "pandas": ">=2.2,<3"},
)
