"""Locally registered evaluation Methods; not supported production builtins."""
from decision_layer.methods import Dimension, Entity, Estimate, Measure, Refused, method
from .experiment import dml

PACKAGES = {"econml": "==0.16.0", "numpy": ">=1.26,<3", "pandas": ">=2.2,<3", "scikit-learn": "==1.6.1"}


def calculate(frame, kind, control, treated):
    # This evaluated template has one numeric adjustment variable, no heterogeneity.
    frame = frame.copy()
    frame["x"] = 0
    return dml(frame, kind, control=control, treated=treated)


async def contrast(ctx, outcome, treatment, confounder, unit, kind, control, treated):
    if control == treated:
        raise Refused("The treatment contrast needs distinct values")
    observations = await ctx.entities(entity=unit, measures={"outcome": outcome},
                                      dimensions={"treatment": treatment, "w": confounder})
    value = await ctx.compute(calculate, observations.frame, kind, control, treated)
    return Estimate(value, details={"control": control, "treated": treated, "target": "observed_population_ate",
        "estimator": "LinearDML", "categories": ["control", "basic", "plus"] if kind == "categorical" else None,
        "seed": 17, "cv": 3, "assumptions_status": "not_verified",
        "causal_claim": "not_established", "uncertainty": "not_reported"},
        warnings=["Evaluation template: independent synthetic units, numeric adjustment, no uncertainty."])


#region typed_methods
@method("review.categorical_dml", version="0.2.0", execution="dataframe", interpretation="associational",
        requires_packages=PACKAGES)
async def categorical_dml(ctx, *, outcome: Measure, treatment: Dimension,
                          confounder: Dimension | Measure, unit: Entity,
                          control: str, treated: str) -> Estimate:
    """Evaluate a constant contrast among the fixed control/basic/plus categories."""
    return await contrast(ctx, outcome, treatment, confounder, unit, "categorical", control, treated)


@method("review.continuous_dml", version="0.2.0", execution="dataframe", interpretation="associational",
        requires_packages=PACKAGES)
async def continuous_dml(ctx, *, outcome: Measure, treatment: Dimension | Measure,
                         confounder: Dimension | Measure, unit: Entity,
                         control: float, treated: float) -> Estimate:
    """Evaluate an explicit dose contrast in the synthetic two-stratum adjustment design."""
    return await contrast(ctx, outcome, treatment, confounder, unit, "continuous", control, treated)
#endregion typed_methods
