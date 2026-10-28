"""A campaign procedure using the two currently installed query Skills."""

from decision_layer.core.models import Recipe, SemanticScope, PlanStep

METHODS = []


def campaign_recipe(instance="journey"):
    ref = lambda member: f"cube://{instance}/campaign_household_outcomes/{member}"
    metric, campaign = ref("post_sales_mean"), ref("campaign_id")
    return Recipe(
        name="campaign-skill-investigation",
        version="1.2.0",
        description="Inspect campaign means, then query a selected campaign and accessible peers. Descriptive evidence only.",
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
                method_version="2.2.0",
                purpose="Inspect campaign means and select a campaign from recorded rows.",
                bindings={"metric": metric, "dimensions": [campaign]},
            ),
            PlanStep(
                id="peers",
                method="analysis.metric_lookup",
                method_version="2.2.0",
                purpose="Query the chosen campaign and other accessible campaigns separately and explain the comparison limits.",
                bindings={"metric": metric, "dimensions": [campaign]},
            ),
        ],
    )
