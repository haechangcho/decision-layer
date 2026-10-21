"""Calculate numeric OLS with one row per observational unit."""

import statsmodels.api as sm
from decision_layer.methods import Column, DataInput, python_method
from .checks import check_data


def ols(data, outcome, treatment, confounders):
    """Compare an outcome with one variable, accounting for the other variables."""
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
    version="2.1.0",
    label="OLS regression",
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
                    source=["measure", "dimension"],
                    dtype="number",
                    description="Variable to examine",
                ),
                "confounders": Column(
                    source=["measure", "dimension"],
                    dtype="number",
                    multiple=True,
                    description="Other variables to account for",
                ),
            },
            minimum_rows=60,
        )
    },
    checks=[check_data],
    output="estimate",
    requires_packages={"statsmodels": ">=0.14,<0.16", "pandas": ">=2.2,<3"},
)
