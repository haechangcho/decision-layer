"""Ordinary calculation, result presentation and separate governed input registration."""

from decision_layer.methods import DataInput, python_method
from decision_layer.core.models import RoleSpec, ValidationResult
from decision_layer.methods.output import Estimate
from decision_layer.methods.context import Refused
from decision_layer.methods.statistics import _units, _covariates, _binary_support
from decision_layer.methods.binary_matching import REQUIREMENTS
from decision_layer.i18n import _


def analyze(
    data, control_value: float | None = None, treatment_value: float | None = None
):
    """Estimate adjusted change per stored treatment unit, or an explicit in-range contrast; causal identification is unverified."""
    import networkx as nx
    import numpy as np
    from dowhy import CausalModel

    # data: unit, outcome, treatment, confounders_0, confounders_1, ...
    # The registered DataInput handles Cube queries and column bindings.
    try:
        check_contrast(control_value, treatment_value)
    except ValueError as exc:
        raise Refused(_(str(exc))) from exc
    observations, encoding, support = prepare_observations(data)
    binary = set(observations["treatment"].unique()) == {0, 1}
    comparison_start, comparison_end = resolve_comparison(
        support, binary, control_value, treatment_value
    )

    # This graph states analytical assumptions, not causal relationships established by data.
    edges = [("treatment", "outcome")]
    edges += [
        (name, destination)
        for name in encoding
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
        method_name="backdoor.linear_regression",
        control_value=comparison_start,
        treatment_value=comparison_end,
        target_units="ate",
        confidence_intervals=False,
    )
    # Normalize a fitted in-range contrast; do not manufacture an out-of-range intervention.
    slope = float(estimate.value) / (comparison_end - comparison_start)
    explicit = control_value is not None
    value = float(estimate.value) if explicit else slope
    if not np.isfinite(value):
        raise Refused(_("Outcomes must be finite"))
    return {
        "value": value,
        "slope": slope,
        "result_scale": "contrast" if explicit else "per_treatment_unit",
        "contrast": [comparison_start, comparison_end] if explicit else None,
        "estimation_contrast": [comparison_start, comparison_end],
        "treatment_ref": data.attrs.get("semantic_refs", {}).get("treatment"),
        "treatment_scale": "as_stored_in_semantic_source",
        "treatment_type": "binary" if binary else "continuous",
        "target": "ate",
        "n_units": len(data),
        "support": support,
        "encoding": encoding,
        "estimator": "backdoor.linear_regression",
        "model": "additive_linear_constant_slope",
        "graph_edges": edges,
        "estimand": str(estimand),
        "assumptions_status": "not_verified",
        "causal_claim": "not_established",
        "uncertainty": "not_reported",
    }


def prepare_observations(data):
    """Validate observations and encode covariates without mutating the input DataFrame."""
    import numpy as np
    import pandas as pd

    confounders = [name for name in data.columns if name.startswith("confounders_")]
    _units(data, ["outcome", "treatment", *confounders])
    if not pd.api.types.is_numeric_dtype(data["treatment"]):
        raise Refused(
            _(
                "Regression adjustment requires numeric treatment; categorical coding must be explicit"
            )
        )
    treatment = data["treatment"].to_numpy(dtype=float)
    if not np.isfinite(treatment).all():
        raise Refused(_("Treatment values must be finite"))
    unique = np.unique(treatment)
    binary = set(unique) == {0, 1}
    if not binary and (len(data) < 60 or len(unique) < 10):
        raise Refused(
            _(
                "Continuous regression requires at least 60 units and 10 distinct treatment values"
            )
        )

    encoded = _covariates(data, confounders)
    support = {
        "min": float(treatment.min()),
        "max": float(treatment.max()),
        "joint_support": "not_verified",
    }
    if binary:
        support["binary_propensity"] = _binary_support(data, encoded)
    matrix = np.column_stack([np.ones(len(data)), treatment, encoded.to_numpy()])
    if len(data) <= matrix.shape[1] or np.linalg.matrix_rank(matrix) < matrix.shape[1]:
        raise Refused(
            _(
                "Regression requires full-rank predictors and residual degrees of freedom"
            )
        )

    observations = pd.concat(
        [
            pd.DataFrame(
                {"outcome": data["outcome"].to_numpy(), "treatment": treatment}
            ),
            encoded.reset_index(drop=True),
        ],
        axis=1,
    )
    return observations, encoded.attrs["encoding"], support


def resolve_comparison(support, binary, control_value, treatment_value):
    """Default to the observed range; validate explicit comparison values against that range."""
    import numpy as np

    start, end = (
        (float(control_value), float(treatment_value))
        if control_value is not None
        else (support["min"], support["max"])
    )
    if not np.isfinite([start, end]).all() or start == end:
        raise Refused(_("Regression comparison values must be finite and different"))
    if binary and {start, end} != {0, 1}:
        raise Refused(_("Binary treatment contrasts must compare 0 and 1"))
    if min(start, end) < support["min"] or max(start, end) > support["max"]:
        raise Refused(
            _("Explicit comparison values must lie within the observed treatment range")
        )
    return start, end


def check_contrast(control_value=None, treatment_value=None):
    if (control_value is None) != (treatment_value is None):
        raise ValueError(
            "Specify both comparison values or omit both for the per-unit slope"
        )


def present_result(payload):
    """Record executed diagnostics separately from unverified assumptions."""
    return Estimate(
        payload["value"],
        details=payload,
        validation=[
            ValidationResult(
                validator="regression_data",
                status="pass",
                code="REGRESSION_DATA_CHECKED",
                message=_(
                    "Unique units, finite data and full-rank predictors were checked"
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
                "A unit is the treatment's stored semantic scale; percentages are not converted automatically."
            ),
            _(
                "This additive linear model assumes a constant slope. Treatment timing, no unmeasured confounding, independence, no interference and joint treatment support remain unverified. No established causal effect or uncertainty interval is reported."
            ),
        ],
    )


METHODS = [
    python_method(
        analyze,
        name="stats.regression_adjustment",
        version="1.1.0",
        label="DoWhy regression adjustment (OLS)",
        inputs={
            "data": DataInput(
                measures=["outcome"],
                entity="unit",
                minimum_rows=60,
                columns={
                    "treatment": RoleSpec(
                        kind="dimension", accepted_kinds=["dimension", "measure"]
                    ),
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
        option_checks=[check_contrast],
        requires_packages=REQUIREMENTS,
    ),
]
