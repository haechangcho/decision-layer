"""Reviewed demo module: an ordinary statsmodels function after agent-driven Skills."""


def sufficient_observations(observations):
    import numpy as np

    if len(observations) < 60:
        raise ValueError("At least 60 observations are required for this example")
    predictors = np.column_stack(
        [np.ones(len(observations)), observations[["baseline", "frequency"]].to_numpy()]
    )
    if np.linalg.matrix_rank(predictors) != predictors.shape[1]:
        raise ValueError("Predictors must have full rank")


def household_regression(observations):
    """Describe associations between prior activity and subsequent household sales."""
    import pandas as pd
    import statsmodels.api as sm

    fitted = sm.OLS(
        observations["outcome"],
        sm.add_constant(observations[["baseline", "frequency"]], has_constant="add"),
    ).fit()
    return pd.DataFrame(
        {
            "term": fitted.params.index,
            "coefficient": fitted.params.values,
            "standard_error": fitted.bse.values,
            "n_observations": int(fitted.nobs),
        }
    )


from decision_layer.methods import DataInput, python_method

METHODS = []
# Explicit legacy imports and pinned Runs remain reproducible; not a catalog choice.
COMPATIBILITY_METHODS = [
    python_method(
        household_regression,
        name="example.household_regression",
        version="1.0.0",
        inputs={
            "observations": DataInput(
                measures=["outcome", "baseline", "frequency"],
                entity="unit_id",
                filters_parameter="population_filters",
                minimum_rows=60,
            )
        },
        checks=[sufficient_observations],
        requires_packages={"statsmodels": ">=0.14,<0.16"},
    )
]


def legacy_campaign_recipe(instance="journey"):
    """Only for the repository's existing campaign_household_outcomes Cube model."""
    from decision_layer.core.models import Recipe, SemanticScope, PlanStep

    ref = lambda member: f"cube://{instance}/campaign_household_outcomes/{member}"
    metric, campaign = ref("post_sales_mean"), ref("campaign_id")
    return Recipe(
        name="campaign-skill-investigation",
        version="1.0.1",
        description="Inspect campaign means, compare an observed campaign with other accessible campaigns, then fit household associations within a selected peer campaign. Not causal or risk-adjusted.",
        mode="pipeline",
        semantic_scope=SemanticScope(
            primary_metric=metric,
            related_metrics=[ref("pre_sales_mean"), ref("pre_frequency_mean")],
            preferred_dimensions=[campaign],
        ),
        steps=[
            PlanStep(
                id="campaigns",
                method="analysis.drilldown",
                method_version="1.0.1",
                purpose="Inspect campaign-level mean sales and select a campaign from recorded rows.",
                bindings={"metric": metric, "dimensions": [campaign]},
            ),
            PlanStep(
                id="peers",
                method="analysis.peer_comparison",
                method_version="1.0.1",
                purpose="Compare the selected campaign with other accessible campaigns, then select one peer campaign for an associational calculation.",
                bindings={"metric": metric, "dimensions": [campaign]},
                params={
                    "subject": {
                        "source": "step",
                        "step_id": "campaigns",
                        "output": "selected_group",
                        "select": "first",
                        "project": "condition",
                    }
                },
            ),
            PlanStep(
                id="regression",
                method="example.household_regression",
                method_version="1.0.0",
                purpose="Fit household-level associations inside the selected peer campaign; do not claim a causal effect.",
                bindings={
                    "outcome": metric,
                    "baseline": ref("pre_sales_mean"),
                    "frequency": ref("pre_frequency_mean"),
                    "unit_id": ref("observation_id"),
                },
                params={
                    "population_filters": "$steps.peers.selections.selected_group.evidence.filters"
                },
            ),
        ],
    )


def campaign_recipe(instance="journey"):
    """Current query-only example; no retired calculation is appended."""
    recipe = legacy_campaign_recipe(instance)
    recipe.version = "1.1.0"
    recipe.description = "Inspect campaign means and compare a selected campaign with accessible peers. Query evidence only; not causal or risk-adjusted."
    recipe.steps = recipe.steps[:2]
    recipe.steps[0].method_version = "1.1.0"
    recipe.steps[
        1
    ].purpose = "Compare the selected campaign with other accessible campaigns and retain the observed peer evidence."
    return recipe
