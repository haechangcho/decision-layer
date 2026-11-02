"""Reviewed reusable campaign comparison, scoped to exactly one campaign."""
import numpy as np
from decision_layer.methods import Column, DataInput, python_method
from decision_layer.starters.methods.ols.checks import check_data
from decision_layer.starters.methods.ols.method import ols


def check_campaign(data):
    if data["campaign"].isna().any() or data["campaign"].nunique() != 1:
        raise ValueError("Select exactly one campaign with non-null campaign IDs.")


def check_groups(data, treatment):
    if set(data[treatment].unique()) != {0, 1}:
        raise ValueError("Both target-list and non-target groups are required.")
    if data.groupby(treatment).size().min() < 30:
        raise ValueError("Each group requires at least 30 observations.")


def compare_campaign(data, outcome, treatment, confounders):
    """Compare target and non-target household outcomes with prior-activity OLS adjustment."""
    result = ols(data, outcome, treatment, confounders)
    groups = []
    for group, rows in data.groupby(treatment):
        groups.append({"targeted": int(group), "households": len(rows),
                       "post_sales_mean": float(rows[outcome].mean()),
                       "prior_sales_mean": float(rows[confounders[0]].mean()),
                       "prior_frequency_mean": float(rows[confounders[1]].mean())})
    if not np.isfinite(result["value"]):
        raise ValueError("OLS estimate must be finite.")
    return {**result, "campaign": str(data["campaign"].iloc[0]), "groups": groups,
            "limitations": ["Target-list membership is not confirmed exposure or random assignment.",
                            "Association does not establish campaign causality; no uncertainty interval is reported.",
                            "Only eligible previously active households are represented."]}


METHOD = python_method(
    compare_campaign, name="benchmark.campaign_business", version="1.0.0", output="estimate",
    inputs={"data": DataInput(columns={
        "entity_id": Column(source="dimension", role="entity_key"),
        "campaign": Column(source="dimension"),
        "outcome": Column(source="measure", dtype="number"),
        "treatment": Column(source="dimension", dtype="number"),
        "confounders": Column(source="measure", dtype="number", multiple=True),
    }, filters_parameter="campaign_filter", minimum_rows=60, require_complete=True)},
    checks=[check_campaign, check_data, check_groups],
    requires_packages={"statsmodels": ">=0.14,<0.16", "pandas": ">=2.2,<3"},
)
