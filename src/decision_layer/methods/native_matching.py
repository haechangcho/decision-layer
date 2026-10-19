"""Ordinary calculation, result presentation and separate governed input registration."""

from decision_layer.methods import DataInput, python_method
from decision_layer.core.models import RoleSpec, ValidationResult
from decision_layer.methods.output import Estimate
from decision_layer.methods.context import Refused
from decision_layer.methods.statistics import _units, _covariates, _binary_support
from decision_layer.methods.binary_matching import REQUIREMENTS
from decision_layer.i18n import _


def analyze(data):
    """Compare treated units with nearest controls; identification assumptions remain unverified."""
    frame = data
    confounder_columns = [
        name for name in data.columns if name.startswith("confounders_")
    ]
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
    observations = pd.concat(
        [
            frame[["outcome", "treatment"]].reset_index(drop=True),
            standardized.reset_index(drop=True),
        ],
        axis=1,
    )
    # This DAG is an explicit assumption, not learned or verified from data.
    edges = [("treatment", "outcome")]
    edges += [
        (name, destination)
        for name in standardized.columns
        for destination in ("treatment", "outcome")
    ]
    model = CausalModel(
        data=observations,
        treatment="treatment",
        outcome="outcome",
        graph=nx.DiGraph(edges),
    )
    estimand = model.identify_effect(proceed_when_unidentifiable=False)
    if not (estimand.estimands.get("backdoor") or {}).get("estimand"):
        raise Refused(
            _("No backdoor estimand is identified under the supplied assumptions")
        )
    estimate = model.estimate_effect(
        estimand,
        method_name="backdoor.distance_matching",
        control_value=0,
        treatment_value=1,
        target_units="att",
        confidence_intervals=False,
        method_params={"num_matches_per_unit": 1, "distance_metric": "euclidean"},
    )

    pairs = estimate.estimator.matched_indices_att
    treated_indices = list(pairs)
    control_indices = [pairs[index][0] for index in treated_indices]
    if len(treated_indices) != int(observations["treatment"].sum()):
        raise Refused(
            _(
                "Matching must cover every treated unit without changing the target population"
            )
        )
    unique_controls = len(set(control_indices))
    if unique_controls < 30:
        raise Refused(_("Matching requires at least 30 distinct matched control units"))
    distances = np.linalg.norm(
        standardized.reset_index(drop=True).iloc[treated_indices].to_numpy()
        - standardized.reset_index(drop=True).iloc[control_indices].to_numpy(),
        axis=1,
    )
    if distances.max() > 1.0:
        raise Refused(_("Matched distances exceed this Method's support threshold"))
    treated = encoded.loc[frame["treatment"].to_numpy() == 1]
    controls = encoded.loc[frame["treatment"].to_numpy() == 0]
    denominator = np.sqrt((treated.var(ddof=1) + controls.var(ddof=1)) / 2)
    before = treated.mean() - controls.mean()
    after = (
        encoded.reset_index(drop=True).iloc[treated_indices].mean()
        - encoded.reset_index(drop=True).iloc[control_indices].mean()
    )
    # Zero pooled variance with distinct group constants is unsupported.
    if (denominator <= 0).any():
        raise Refused(_("Matching balance requires within-group covariate variation"))
    smd_before, smd_after = before / denominator, after / denominator
    if smd_after.abs().max() > 0.1:
        raise Refused(
            _("Matched covariate balance fails this Method's diagnostic threshold")
        )
    value = float(estimate.value)
    if not np.isfinite(value):
        raise Refused(_("Outcomes must be finite"))
    return {
        "value": value,
        "estimator": "backdoor.distance_matching",
        "contrast": [0, 1],
        "target": "att",
        "n_units": len(frame),
        "n_treated": len(treated_indices),
        "n_unique_matched_controls": unique_controls,
        "matching_with_replacement": True,
        "max_distance": float(distances.max()),
        "support": support,
        "balance": [
            {
                "covariate": encoded.attrs["encoding"][name],
                "smd_before": float(smd_before[name]),
                "smd_after": float(smd_after[name]),
            }
            for name in encoded.columns
        ],
        "diagnostic_policy": {
            "min_unique_controls": 30,
            "max_distance": 1.0,
            "max_abs_smd": 0.1,
        },
        "graph_edges": edges,
        "estimand": str(estimand),
        "encoding": encoded.attrs["encoding"],
        "assumptions_status": "not_verified",
        "causal_claim": "not_established",
        "uncertainty": "not_reported",
    }


def present_result(payload):
    """Record executed diagnostics separately from unverified assumptions."""
    return Estimate(
        payload["value"],
        details=payload,
        validation=[
            ValidationResult(
                validator="matching_data",
                status="pass",
                code="MATCHING_DIAGNOSTICS_CHECKED",
                message=_(
                    "Unit uniqueness, observed support, matched distances and covariate balance were checked"
                ),
            ),
            ValidationResult(
                validator="identification",
                status="warning",
                code="ASSUMPTIONS_UNVERIFIED",
                message=_("Identification assumptions have not been verified"),
            ),
        ],
        warnings=[
            _(
                "Matching diagnostics do not verify pre-treatment timing, no unmeasured confounding, independence or no interference. No established causal effect or uncertainty interval is reported."
            )
        ],
    )


METHODS = [
    python_method(
        analyze,
        name="stats.binary_matching",
        version="1.1.0",
        label="DoWhy matching comparison",
        inputs={
            "data": DataInput(
                measures=["outcome"],
                entity="unit",
                minimum_rows=60,
                columns={
                    "treatment": RoleSpec(kind="dimension"),
                    "confounders": RoleSpec(
                        kind="dimension",
                        accepted_kinds=["dimension", "measure"],
                        multiple=True,
                    ),
                },
            )
        },
        output="estimate",
        adapt=present_result,
        provides=["matched_comparison"],
        requires_packages=REQUIREMENTS,
    ),
]
