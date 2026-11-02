"""Summarize campaign cohort balance and missing classification codes."""
from decision_layer.methods import Column, DataInput, python_method
from decision_layer.methods.context import Refused


def summarize_cohort(data, outcome, treatment, confounders, age, income, composition, overlaps):
    """Show target and control household counts, prior and post activity and missing codes."""
    if data["campaign"].isna().any() or data["campaign"].nunique() != 1:
        raise Refused("Select exactly one campaign with non-null campaign IDs.")
    if len(confounders) != 2 or set(data[treatment].unique()) != {0, 1}:
        raise Refused("Both groups and two prior-activity variables are required.")
    rows = []
    for group, part in data.groupby(treatment):
        rows.append({"targeted": int(group), "households": len(part),
                     "post_sales_mean": float(part[outcome].mean()),
                     "prior_sales_mean": float(part[confounders[0]].mean()),
                     "prior_frequency_mean": float(part[confounders[1]].mean()),
                     "age_missing": int(part[age].isna().sum()),
                     "income_missing": int(part[income].isna().sum()),
                     "composition_missing": int(part[composition].isna().sum()),
                     "other_campaigns_targeted": int((part[overlaps] > 0).sum())})
    return rows


METHOD = python_method(
    summarize_cohort, name="benchmark.campaign_cohort", version="1.0.0", output="table",
    inputs={"data": DataInput(columns={
        "entity_id": Column(source="dimension", role="entity_key"),
        "campaign": Column(source="dimension"),
        "outcome": Column(source="measure", dtype="number"),
        "treatment": Column(source="dimension", dtype="number"),
        "confounders": Column(source="measure", dtype="number", multiple=True),
        "age": Column(source="dimension"),
        "income": Column(source="dimension"),
        "composition": Column(source="dimension"),
        "overlaps": Column(source="dimension", dtype="number"),
    }, filters_parameter="campaign_filter", minimum_rows=60, require_complete=True)},
    requires_packages={"pandas": ">=2.2,<3"},
)
