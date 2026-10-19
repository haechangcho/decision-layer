"""Bring a normal Python function; register only its governed input contract."""

from decision_layer.core.models import RoleSpec
from decision_layer.methods import DataInput, python_method


def rank_values(data, value, group, descending=True):
    """Rank the selected metric within the observed groups, retaining ties."""
    return data[[group, value]].assign(
        rank=data[value].rank(method="min", ascending=not descending).astype(int)
    )


def ols(data, outcome, treatment, confounders):
    """Fit numeric additive OLS; coefficients describe association, not causation.

    One row is one independent observational unit. Choose covariates explicitly;
    this function cannot establish their timing or absence of omitted confounding.
    Categorical encoding, interactions and uncertainty inference are not provided.
    """
    import numpy as np
    import pandas as pd
    import statsmodels.api as sm

    selected = [outcome, treatment, *confounders]
    if len(set(selected)) != len(selected):
        raise ValueError("Outcome, treatment and confounders must be distinct columns")
    values = data[selected]
    if not all(pd.api.types.is_numeric_dtype(values[name]) for name in selected):
        raise ValueError("OLS requires numeric columns; encode categories explicitly")
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("OLS requires finite, non-null observations")
    if values[outcome].nunique() < 2:
        raise ValueError("OLS requires a varying outcome for a finite fit summary")
    design = sm.add_constant(values[[treatment, *confounders]], has_constant="add")
    if len(data) <= design.shape[1] or np.linalg.matrix_rank(design) < design.shape[1]:
        raise ValueError("OLS requires full rank and residual degrees of freedom")
    fit = sm.OLS(values[outcome], design).fit()
    return {
        "value": float(fit.params[treatment]),
        "n_observations": int(fit.nobs),
        "r_squared": float(fit.rsquared),
        "coefficients": {key: float(value) for key, value in fit.params.items()},
        "causal_claim": "not_established",
        "uncertainty": "not_reported",
    }


METHODS = [
    python_method(
        rank_values,
        name="workshop.rank_columns",
        version="1.0.1",
        output="table",
        inputs={
            "data": DataInput(
                measures=["value"],
                dimensions=["group"],
                column_args=["value", "group"],
            )
        },
    ),
    python_method(
        ols,
        name="workshop.ols_columns",
        version="1.0.0",
        inputs={
            "data": DataInput(
                entity="unit",
                measures=["outcome"],
                columns={
                    "treatment": RoleSpec(
                        kind="dimension",
                        accepted_kinds=["dimension", "measure"],
                        data_type="number",
                        description="Explanatory variable on its stored numeric scale",
                    ),
                    "confounders": RoleSpec(
                        kind="dimension",
                        accepted_kinds=["dimension", "measure"],
                        data_type="number",
                        multiple=True,
                        description="Explicitly selected adjustment variables",
                    ),
                },
                column_args=["outcome", "treatment", "confounders"],
                minimum_rows=10,
            )
        },
        output="estimate",
        requires_packages={"statsmodels": ">=0.14,<0.16"},
    ),
]
