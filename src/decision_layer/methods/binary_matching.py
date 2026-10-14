"""Binary DoWhy distance matching with bounded observed-data diagnostics."""
from ..i18n import _
from ..core.models import ValidationResult
from .authoring import method
from .inputs import Dimension, Entity, Measure
from .output import Estimate
from .context import Refused
from .statistics import _units, _covariates, _binary_support


REQUIREMENTS = {"dowhy": "==0.13", "numpy": ">=1.26,<2", "pandas": ">=2.2,<3",
                "scikit-learn": ">=1.2,<1.7", "statsmodels": ">=0.14,<0.16"}


def estimate_binary_matching(frame, confounder_columns):
    import networkx as nx
    import numpy as np
    import pandas as pd
    from dowhy import CausalModel

    _units(frame, ["outcome", "treatment", *confounder_columns])
    encoded = _covariates(frame, confounder_columns)
    support = _binary_support(frame, encoded)
    # Standardization stops units of measurement from dominating the distance.
    scale = encoded.std(ddof=0)
    if (scale <= 0).any():
        raise Refused(_("Matching covariates must vary; remove constant columns"))
    standardized = (encoded - encoded.mean()) / scale
    observations = pd.concat([frame[["outcome", "treatment"]].reset_index(drop=True),
                              standardized.reset_index(drop=True)], axis=1)
    # This DAG is an explicit assumption, not learned or verified from data.
    edges = [("treatment", "outcome")]
    edges += [(name, destination) for name in standardized.columns
              for destination in ("treatment", "outcome")]
    model = CausalModel(data=observations, treatment="treatment", outcome="outcome", graph=nx.DiGraph(edges))
    estimand = model.identify_effect(proceed_when_unidentifiable=False)
    if not (estimand.estimands.get("backdoor") or {}).get("estimand"):
        raise Refused(_("No backdoor estimand is identified under the supplied assumptions"))
    estimate = model.estimate_effect(estimand, method_name="backdoor.distance_matching",
        control_value=0, treatment_value=1, target_units="att", confidence_intervals=False,
        method_params={"num_matches_per_unit": 1, "distance_metric": "euclidean"})

    pairs = estimate.estimator.matched_indices_att
    treated_indices = list(pairs)
    control_indices = [pairs[index][0] for index in treated_indices]
    if len(treated_indices) != int(observations["treatment"].sum()):
        raise Refused(_("Matching must cover every treated unit without changing the target population"))
    unique_controls = len(set(control_indices))
    if unique_controls < 30:
        raise Refused(_("Matching requires at least 30 distinct matched control units"))
    distances = np.linalg.norm(
        standardized.reset_index(drop=True).iloc[treated_indices].to_numpy()
        - standardized.reset_index(drop=True).iloc[control_indices].to_numpy(), axis=1)
    if distances.max() > 1.0:
        raise Refused(_("Matched distances exceed this Method's support threshold"))
    treated = encoded.loc[frame["treatment"].to_numpy() == 1]
    controls = encoded.loc[frame["treatment"].to_numpy() == 0]
    denominator = np.sqrt((treated.var(ddof=1) + controls.var(ddof=1)) / 2)
    before = treated.mean() - controls.mean()
    after = encoded.reset_index(drop=True).iloc[treated_indices].mean() - encoded.reset_index(drop=True).iloc[control_indices].mean()
    # Zero pooled variance with distinct group constants is unsupported.
    if (denominator <= 0).any():
        raise Refused(_("Matching balance requires within-group covariate variation"))
    smd_before, smd_after = before / denominator, after / denominator
    if smd_after.abs().max() > 0.1:
        raise Refused(_("Matched covariate balance fails this Method's diagnostic threshold"))
    value = float(estimate.value)
    if not np.isfinite(value):
        raise Refused(_("Outcomes must be finite"))
    return {"value": value, "estimator": "backdoor.distance_matching", "contrast": [0, 1],
        "target": "att", "n_units": len(frame), "n_treated": len(treated_indices),
        "n_unique_matched_controls": unique_controls, "matching_with_replacement": True,
        "max_distance": float(distances.max()), "support": support,
        "balance": [{"covariate": encoded.attrs["encoding"][name],
                     "smd_before": float(smd_before[name]), "smd_after": float(smd_after[name])}
                    for name in encoded.columns],
        "diagnostic_policy": {"min_unique_controls": 30, "max_distance": 1.0, "max_abs_smd": 0.1},
        "graph_edges": edges, "estimand": str(estimand), "encoding": encoded.attrs["encoding"],
        "assumptions_status": "not_verified", "causal_claim": "not_established",
        "uncertainty": "not_reported"}


@method("stats.binary_matching", version="1.0.0", kind="stats", execution="dataframe",
        requires_packages=REQUIREMENTS, provides=["matched_comparison"])
async def binary_matching(ctx, *, outcome: Measure, treatment: Dimension,
                          confounders: list[Dimension | Measure], unit: Entity) -> Estimate:
    """Compare treated units (1) with nearest controls (0) using pre-treatment covariates; ATT under an assumed backdoor graph, with identification assumptions unverified."""
    observations = await ctx.entities(entity=unit, measures={"outcome": outcome},
        dimensions={"treatment": treatment, "confounders": confounders})
    payload = await ctx.compute(estimate_binary_matching, observations.frame, observations.columns("confounders"))
    return Estimate(payload["value"], details=payload, validation=[
        ValidationResult(validator="matching_data", status="pass", code="MATCHING_DIAGNOSTICS_CHECKED",
            message=_("Unit uniqueness, observed support, matched distances and covariate balance were checked")),
        ValidationResult(validator="identification", status="warning", code="ASSUMPTIONS_UNVERIFIED",
            message=_("Identification assumptions have not been verified"))],
        warnings=[_("Matching diagnostics do not verify pre-treatment timing, no unmeasured confounding, independence or no interference. No established causal effect or uncertainty interval is reported.")])


binary_matching.manifest.label = "DoWhy matching comparison"
