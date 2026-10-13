"""Compatibility implementations for the original assumption-object contracts."""
from typing import Annotated, Literal
from pydantic import Field
from ..i18n import _
from ..core.models import ValidationResult
from .authoring import method
from .inputs import AnalysisDesign, DateRange, Dimension, Entity, Measure, TimeDimension
from .output import Estimate
from .context import Refused
from . import statistics as calculation

PANDAS = {"pandas": ">=2.2,<3"}
STATS = {**PANDAS, "statsmodels": ">=0.14,<0.16"}
DESIGN_FIELDS = ("pretreatment_covariates", "treatment_precedes_outcome", "no_unmeasured_confounding", "no_interference", "independent_units")


def require_design(design, fields):
    if not design.note.strip() or any(getattr(design, name) is not True for name in fields):
        raise Refused(_("Document the required analysis assumptions before estimation"))


def _checks(payload):
    return [ValidationResult(validator="unit_data", status="pass", code="UNIT_DATA_CHECKED",
                             message=_("Observation keys, values and estimator data requirements were checked"),
                             details={"n_units": payload["n_units"]}),
            ValidationResult(validator="identification", status="warning", code="ASSUMPTIONS_ASSERTED",
                             message=_("Identification assumptions are authored assertions, not verified facts"))]


#region adjusted_difference
@method("stats.adjusted_difference", version="1.0.0", kind="stats", execution="dataframe", interpretation="associational",
        requires_packages={**STATS, "dowhy": "==0.13", "scikit-learn": ">=1.2,<1.7", "numpy": ">=1.26,<2"})
async def adjusted_difference(ctx, *, outcome: Measure, treatment: Dimension,
                              confounders: list[Dimension | Measure], unit: Entity, design: AnalysisDesign,
                              seed: Annotated[int, Field(ge=0, le=2147483647)] = 7) -> Estimate:
    """Use DoWhy for a binary-treatment adjusted difference with explicit design assumptions and placebo diagnostics."""
    require_design(design, DESIGN_FIELDS)
    data = await ctx.entities(entity=unit, measures={"outcome": outcome},
                              dimensions={"treatment": treatment, "confounders": confounders})
    payload = await ctx.compute(calculation.fit_dowhy, data.frame, data.columns("confounders"), design.model_dump(), seed)
    return Estimate(payload["value"], details=payload, validation=_checks(payload),
        warnings=[_("Observed adjustment and placebo checks do not establish causality; no uncertainty interval is reported."),
                  *payload.get("backend_warnings", [])])

#endregion adjusted_difference

@method("stats.dml", version="1.0.0", kind="stats", execution="dataframe", interpretation="associational",
        requires_packages={**PANDAS, "econml": "==0.16.0", "scikit-learn": ">=1.2,<1.7", "numpy": ">=1.26,<2"})
async def dml(ctx, *, outcome: Measure, treatment: Dimension, confounders: list[Dimension | Measure],
              unit: Entity, design: AnalysisDesign,
              seed: Annotated[int, Field(ge=0, le=2147483647)] = 7) -> Estimate:
    """Estimate a constant binary-treatment contrast using EconML with explicit observation and design checks."""
    require_design(design, DESIGN_FIELDS)
    data = await ctx.entities(entity=unit, measures={"outcome": outcome},
                              dimensions={"treatment": treatment, "confounders": confounders})
    payload = await ctx.compute(calculation.fit_dml, data.frame, data.columns("confounders"), design.model_dump(), seed)
    return Estimate(payload["value"], details=payload, validation=_checks(payload),
        warnings=[_("EconML estimation does not verify identification assumptions; no uncertainty interval is reported."),
                  *payload.get("backend_warnings", [])])


@method("stats.did", version="1.0.0", kind="stats", execution="dataframe", interpretation="associational",
        requires_packages=PANDAS)
async def did(ctx, *, outcome: Measure, treated: Dimension, time: TimeDimension, unit: Entity,
              design: AnalysisDesign, windows: list[DateRange] = [],
              granularity: Literal["month", "day"] = "month") -> Estimate:
    """Calculate a two-group two-period panel contrast, optionally extracting disjoint windows."""
    require_design(design, ("parallel_trends", "no_anticipation", "no_interference", "independent_units"))
    import pandas as pd
    ranges = sorted(windows)
    if any(a2 <= b1 for (a1, b1), (a2, b2) in zip(ranges, ranges[1:])):
        raise Refused(_("Panel extraction windows must not overlap"))
    frames = []
    rows = 0
    bound = ctx.execution_policy.max_result_rows if ctx.execution_policy else 50_000
    for index, window in enumerate(windows or [None]):
        data = await ctx.entities(entity=unit, measures={"outcome": outcome}, dimensions={"treated": treated},
            by_time=time, time_granularity=granularity, period=window, label=f"panel_{index + 1}")
        rows += len(data.dataset.rows)
        if rows > bound:
            raise Refused(_("The combined panel exceeds the execution row bound"))
        frames.append(data.frame)
    panel = pd.concat(frames, ignore_index=True)
    if len(panel) > bound:
        raise Refused(_("The combined panel exceeds the execution row bound"))
    payload = await ctx.compute(calculation.fit_did, panel, design.model_dump())
    return Estimate(payload["value"], details=payload, validation=_checks(payload),
        warnings=[_("This simple panel contrast does not establish parallel trends or causal effects; no uncertainty is reported.")])




for implementation, replacement in (
    (adjusted_difference, "stats.binary_regression"),
    (dml, "stats.linear_dml"),
    (did, "stats.two_period_contrast"),
):
    implementation.manifest.label = f"Compatibility: {implementation.manifest.name}"
    implementation.manifest.description += f" Compatibility contract; new callers should use {replacement}."
