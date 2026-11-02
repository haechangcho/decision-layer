"""Register the unchanged starter OLS with complete input retrieval required."""
from decision_layer.methods import Column, DataInput, python_method
from decision_layer.starters.methods.ols.checks import check_data
from decision_layer.starters.methods.ols.method import ols

METHOD = python_method(
    ols, name="benchmark.campaign_ols", version="1.0.0", output="estimate",
    inputs={"data": DataInput(columns={
        "entity_id": Column(source="dimension", role="entity_key"),
        "outcome": Column(source="measure", dtype="number"),
        "treatment": Column(source="dimension", dtype="number"),
        "confounders": Column(source="measure", dtype="number", multiple=True),
    }, minimum_rows=60, require_complete=True)}, checks=[check_data],
    requires_packages={"statsmodels": ">=0.14,<0.16", "pandas": ">=2.2,<3"},
)
