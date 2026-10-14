"""Native DoWhy additive OLS: numeric treatment slope or an explicit contrast."""
from ..i18n import _
from ..core.models import ValidationResult
from .authoring import method
from .inputs import Dimension, Entity, Measure
from .output import Estimate
from .context import Refused
from .statistics import _units, _covariates, _binary_support
from .binary_matching import REQUIREMENTS


def estimate_regression_adjustment(frame, confounder_columns, control_value=None, treatment_value=None):
    import networkx as nx
    import numpy as np
    import pandas as pd
    from dowhy import CausalModel

    if (control_value is None) != (treatment_value is None):
        raise Refused(_("Specify both comparison values or omit both for the per-unit slope"))
    _units(frame, ["outcome", "treatment", *confounder_columns])
    if not pd.api.types.is_numeric_dtype(frame["treatment"]):
        raise Refused(_("Regression adjustment requires numeric treatment; categorical coding must be explicit"))
    t = frame["treatment"].to_numpy(dtype=float)
    if not np.isfinite(t).all():
        raise Refused(_("Treatment values must be finite"))
    unique = np.unique(t)
    binary = set(unique) == {0, 1}
    if not binary and (len(frame) < 60 or len(unique) < 10):
        raise Refused(_("Continuous regression requires at least 60 units and 10 distinct treatment values"))
    encoded = _covariates(frame, confounder_columns)
    support = {"min": float(t.min()), "max": float(t.max()), "joint_support": "not_verified"}
    if binary:
        support["binary_propensity"] = _binary_support(frame, encoded)
    matrix = np.column_stack([np.ones(len(frame)), t, encoded.to_numpy()])
    if len(frame) <= matrix.shape[1] or np.linalg.matrix_rank(matrix) < matrix.shape[1]:
        raise Refused(_("Regression requires full-rank predictors and residual degrees of freedom"))
    explicit = control_value is not None
    lo, hi = (float(control_value), float(treatment_value)) if explicit else (float(t.min()), float(t.max()))
    if not np.isfinite([lo, hi]).all() or lo == hi:
        raise Refused(_("Regression comparison values must be finite and different"))
    if binary and {lo, hi} != {0, 1}:
        raise Refused(_("Binary treatment contrasts must compare 0 and 1"))
    if min(lo, hi) < t.min() or max(lo, hi) > t.max():
        raise Refused(_("Explicit comparison values must lie within the observed treatment range"))
    observations = pd.concat([pd.DataFrame({"outcome": frame["outcome"].to_numpy(), "treatment": t}),
                              encoded.reset_index(drop=True)], axis=1)
    edges = [("treatment", "outcome")]
    edges += [(name, destination) for name in encoded.columns for destination in ("treatment", "outcome")]
    model = CausalModel(data=observations, treatment="treatment", outcome="outcome", graph=nx.DiGraph(edges))
    estimand = model.identify_effect(proceed_when_unidentifiable=False)
    if not (estimand.estimands.get("backdoor") or {}).get("estimand"):
        raise Refused(_("No backdoor estimand is identified under the supplied assumptions"))
    estimate = model.estimate_effect(estimand, method_name="backdoor.linear_regression",
        control_value=lo, treatment_value=hi, target_units="ate", confidence_intervals=False)
    # Normalize a fitted in-range contrast; do not manufacture an out-of-range intervention.
    slope = float(estimate.value) / (hi - lo)
    value = float(estimate.value) if explicit else slope
    if not np.isfinite(value):
        raise Refused(_("Outcomes must be finite"))
    return {"value": value, "slope": slope, "result_scale": "contrast" if explicit else "per_treatment_unit",
        "contrast": [lo, hi] if explicit else None, "estimation_contrast": [lo, hi],
        "treatment_type": "binary" if binary else "continuous", "target": "ate",
        "n_units": len(frame), "support": support, "encoding": encoded.attrs["encoding"],
        "estimator": "backdoor.linear_regression", "model": "additive_linear_constant_slope",
        "graph_edges": edges, "estimand": str(estimand),
        "assumptions_status": "not_verified", "causal_claim": "not_established", "uncertainty": "not_reported"}


@method("stats.regression_adjustment", version="1.0.0", kind="stats", execution="dataframe",
        requires_packages=REQUIREMENTS)
async def regression_adjustment(ctx, *, outcome: Measure, treatment: Dimension | Measure,
                                confounders: list[Dimension | Measure], unit: Entity,
                                control_value: float | None = None,
                                treatment_value: float | None = None) -> Estimate:
    """Estimate a constant adjusted change per stored numeric treatment unit using DoWhy OLS. Binary and continuous treatments are supported; optional comparison values specify a contrast within the observed range. Identification assumptions remain unverified."""
    if (control_value is None) != (treatment_value is None):
        raise Refused(_("Specify both comparison values or omit both for the per-unit slope"))
    observations = await ctx.entities(entity=unit, measures={"outcome": outcome},
        dimensions={"treatment": treatment, "confounders": confounders})
    payload = await ctx.compute(estimate_regression_adjustment, observations.frame,
        observations.columns("confounders"), control_value, treatment_value)
    payload["treatment_ref"] = treatment
    payload["treatment_scale"] = "as_stored_in_semantic_source"
    return Estimate(payload["value"], details=payload, validation=[
        ValidationResult(validator="regression_data", status="pass", code="REGRESSION_DATA_CHECKED",
            message=_("Unique units, finite data and full-rank predictors were checked")),
        ValidationResult(validator="identification", status="warning", code="ASSUMPTIONS_UNVERIFIED",
            message=_("Identification assumptions have not been verified"))], warnings=[
        _("A unit is the treatment's stored semantic scale; percentages are not converted automatically."),
        _("This additive linear model assumes a constant slope. Treatment timing, no unmeasured confounding, independence, no interference and joint treatment support remain unverified. No established causal effect or uncertainty interval is reported.")])


regression_adjustment.manifest.label = "DoWhy regression adjustment (OLS)"
