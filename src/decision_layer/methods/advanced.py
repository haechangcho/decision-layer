"""Registered advanced capabilities using the same authoring and execution contracts."""
from ..i18n import _
from typing import Literal
from ..core.models import ValidationResult
from .authoring import method
from .inputs import DateRange, Dimension, Entity, Measure, TimeDimension
from .output import Estimate, Table
from .context import Refused
from . import statistics as calculation

PANDAS = {"pandas": ">=2.2,<3"}
STATS = {**PANDAS, "statsmodels": ">=0.14,<0.16"}


def _checks(payload):
    return [ValidationResult(validator="unit_data", status="pass", code="UNIT_DATA_CHECKED",
                             message=_("Observation keys, values and estimator data requirements were checked"),
                             details={"n_units": payload["n_units"]}),
            ValidationResult(validator="identification", status="warning", code="ASSUMPTIONS_UNVERIFIED",
                             message=_("Identification assumptions have not been verified"))]


@method("stats.ols", version="1.0.0", kind="stats", execution="dataframe", interpretation="associational",
        requires_packages=STATS, provides=["regression_coefficients"])
async def ols(ctx, *, outcome: Measure, features: list[Dimension | Measure], unit: Entity) -> Table:
    """Estimate associational regression coefficients from complete per-unit observations."""
    data = await ctx.entities(entity=unit, measures={"outcome": outcome}, dimensions={"features": features})
    payload = await ctx.compute(calculation.fit_ols, data.frame, data.columns("features"))
    return Table(payload["rows"], warnings=[_("Regression coefficients are associational; uncertainty is not reported."),
                                            *payload.get("backend_warnings", [])],
                 validation=[ValidationResult(validator="regression_data", status="pass", code="REGRESSION_DATA_CHECKED",
                                              message=_("Unique units, finite data and full-rank predictors were checked"),
                                              details={"n_units": payload["n_units"]})])


#region binary_regression
@method("stats.binary_regression", version="1.0.0", kind="stats", execution="dataframe",
        interpretation="associational",
        requires_packages={**STATS, "dowhy": "==0.13", "scikit-learn": ">=1.2,<1.7", "numpy": ">=1.26,<2"})
async def binary_regression(ctx, *, outcome: Measure, treatment: Dimension,
                            confounders: list[Dimension | Measure], unit: Entity) -> Estimate:
    """Estimate a binary adjusted regression contrast; identification assumptions are unverified."""
    data = await ctx.entities(
        entity=unit, measures={"outcome": outcome},
        dimensions={"treatment": treatment, "confounders": confounders},
    )
    payload = await ctx.compute(
        calculation.estimate_binary_regression, data.frame, data.columns("confounders"),
    )
    return Estimate(payload["value"], details=payload, validation=_checks(payload),
        warnings=[_("Observed adjustment and placebo checks do not establish causality; no uncertainty interval is reported.")])
#endregion binary_regression


@method("stats.linear_dml", version="1.0.0", kind="stats", execution="dataframe",
        interpretation="associational",
        requires_packages={**PANDAS, "econml": "==0.16.0", "scikit-learn": ">=1.2,<1.7", "numpy": ">=1.26,<2"})
async def linear_dml(ctx, *, outcome: Measure, treatment: Dimension,
                     confounders: list[Dimension | Measure], unit: Entity) -> Estimate:
    """Estimate a constant binary LinearDML contrast; identification assumptions are unverified."""
    data = await ctx.entities(
        entity=unit, measures={"outcome": outcome},
        dimensions={"treatment": treatment, "confounders": confounders},
    )
    payload = await ctx.compute(
        calculation.estimate_linear_dml, data.frame, data.columns("confounders"),
    )
    return Estimate(payload["value"], details=payload, validation=_checks(payload),
        warnings=[_("EconML estimation does not verify identification assumptions; no uncertainty interval is reported.")])


@method("stats.two_period_contrast", version="1.0.0", kind="stats", execution="dataframe",
        interpretation="associational", requires_packages=PANDAS)
async def two_period_contrast(ctx, *, outcome: Measure, treated: Dimension,
                              time: TimeDimension, unit: Entity,
                              windows: list[DateRange] = [],
                              granularity: Literal["month", "day"] = "month") -> Estimate:
    """Compare group changes across exactly two ordered observed periods; no parallel-trends claim."""
    import pandas as pd
    ranges = sorted(windows)
    if any(a2 <= b1 for (a1, b1), (a2, b2) in zip(ranges, ranges[1:])):
        raise Refused(_("Panel extraction windows must not overlap"))
    frames = []
    rows = 0
    bound = ctx.execution_policy.max_result_rows if ctx.execution_policy else 50_000
    for index, window in enumerate(windows or [None]):
        data = await ctx.entities(
            entity=unit, measures={"outcome": outcome}, dimensions={"treated": treated},
            by_time=time, time_granularity=granularity, period=window, label=f"panel_{index + 1}",
        )
        rows += len(data.dataset.rows)
        if rows > bound:
            raise Refused(_("The combined panel exceeds the execution row bound"))
        frames.append(data.frame)
    panel = pd.concat(frames, ignore_index=True)
    payload = await ctx.compute(calculation.estimate_two_period_contrast, panel, granularity)
    return Estimate(payload["value"], details=payload, validation=_checks(payload),
        warnings=[_("This simple panel contrast does not establish parallel trends or causal effects; no uncertainty is reported.")])


@method("query.unit_change", version="1.0.0", interpretation="descriptive", requires_packages=PANDAS)
async def unit_change(ctx, *, outcome: Measure, unit: Entity,
                      baseline: DateRange | None = None, baseline_outcome: Measure = None) -> Table:
    """Align complete observations of the same primary units across two periods and report their changes."""
    if (baseline is None) == (baseline_outcome is None):
        raise Refused(_("Choose a baseline period or a provider-defined baseline outcome, but not both"))
    now = await ctx.entities(entity=unit, measures={"outcome": outcome}, label="current")
    before = await ctx.entities(entity=unit, measures={"outcome": baseline_outcome or outcome}, period=baseline,
                                period_role="comparison", label="baseline")
    paired = now.frame.merge(before.frame, on="unit", how="outer", suffixes=("_current", "_baseline"),
                             validate="one_to_one", indicator=True)
    if not paired["_merge"].eq("both").all():
        raise Refused(_("Both periods must contain the same units for a complete-cohort comparison"))
    import numpy as np
    if paired.empty or not np.isfinite(paired[["outcome_current", "outcome_baseline"]].to_numpy(dtype=float)).all():
        raise Refused(_("The unit comparison requires finite observations"))
    paired["change"] = paired["outcome_current"] - paired["outcome_baseline"]
    return Table(paired[["unit", "outcome_current", "outcome_baseline", "change"]].to_dict("records"),
                  warnings=[_("Changes are descriptive; units with incomplete periods are not silently excluded.")])


@method("query.unit_distribution", version="1.0.0", interpretation="descriptive", requires_packages=PANDAS)
async def unit_distribution(ctx, *, outcome: Measure, unit: Entity) -> Table:
    """Inspect a provider-aggregated value alongside the complete per-unit distribution."""
    aggregate = await ctx.aggregate(measures={"provider_value": outcome}, label="aggregate")
    data = await ctx.entities(entity=unit, measures={"outcome": outcome}, label="units")
    frame = data.frame
    calculation._units(frame, ["outcome"])
    return Table([{"provider_value": aggregate.scalar("provider_value"), "unit_min": float(frame["outcome"].min()),
                   "unit_max": float(frame["outcome"].max()), "n_units": len(frame)}],
                 warnings=[_("The aggregate and unit distribution have different bases; cross-query snapshot consistency may be unknown.")])
