"""Built-in validators (ARCHITECTURE §13). Each returns a structured ValidationResult;
Methods and Recipes decide which ones apply. A `fail` makes the Result `refused`."""
from __future__ import annotations

from datetime import date, timedelta

from ..core.models import DatasetSpec, ValidationResult
from ..methods.context import ExecutionContext
from ..i18n import _


def non_empty(rows: int, what: str | None = None) -> ValidationResult:
    what = what or _("result")
    if rows > 0:
        return ValidationResult(validator="non_empty", status="pass", code="OK", message=_("{what}: {rows} rows", what=what, rows=rows))
    return ValidationResult(validator="non_empty", status="fail", code="EMPTY_RESULT",
                            message=_("{what} is empty (check the period, filters and your access)", what=what))


def min_sample(count: float | None, minimum: int, what: str) -> ValidationResult:
    if count is None:
        return ValidationResult(validator="min_sample", status="warning", code="SAMPLE_UNKNOWN",
                                message=_("The count of {what} is unknown, so the sample size could not be checked", what=what))
    if count >= minimum:
        return ValidationResult(validator="min_sample", status="pass", code="OK",
                                message=_("{what}: {count:,.0f} ≥ {minimum}", what=what, count=count, minimum=minimum), details={"count": count})
    return ValidationResult(validator="min_sample", status="warning", code="SMALL_SAMPLE",
                            message=_("{what} is {count:,.0f}, below {minimum}; the value can vary a lot", what=what, count=count, minimum=minimum),
                            details={"count": count, "minimum": minimum})


def complete_period(date_range: tuple[str, str] | None, today: date | None = None) -> ValidationResult:
    if not date_range:
        return ValidationResult(validator="complete_period", status="warning", code="NO_PERIOD",
                                message=_("No period was given, so all data was used"))
    today = today or date.today()
    end = date.fromisoformat(date_range[1])
    if end < today:
        return ValidationResult(validator="complete_period", status="pass", code="OK", message=_("The period is complete"))
    return ValidationResult(validator="complete_period", status="warning", code="INCOMPLETE_PERIOD",
                            message=_("The period ends ({end}) today ({today}) or later, so it is not complete. "
                                      "Data for the last day may not all be in yet", end=end, today=today),
                            details={"end": end.isoformat(), "today": today.isoformat()})


async def freshness(ctx: ExecutionContext, metric: str, date_range: tuple[str, str] | None,
                    tolerance_days: int = 1) -> ValidationResult:
    """Latest date with data ≥ period end − tolerance. One extra query."""
    if not date_range:
        return ValidationResult(validator="freshness", status="pass", code="SKIPPED", message=_("No period"))
    count = ctx.count_measure(metric)
    time = ctx.time_scope(metric, date_range, granularity="day")
    if not count or not time:
        return ValidationResult(validator="freshness", status="warning", code="FRESHNESS_UNKNOWN",
                                message=_("The latest data date could not be determined"))
    ds = await ctx.dataset(DatasetSpec(grain="aggregate", measures=[count], time=time,
                                       filters=list(ctx.scope.filters), order=[(time.dimension, "desc")],
                                       limit_rows=1))
    if not ds.rows:
        return ValidationResult(validator="freshness", status="fail", code="NO_DATA",
                                message=_("There is no data in the period"))
    latest = date.fromisoformat(str(ds.rows[0][0])[:10])
    end = date.fromisoformat(date_range[1])
    if latest >= end - timedelta(days=tolerance_days):
        return ValidationResult(validator="freshness", status="pass", code="OK",
                                message=_("Latest data {date}", date=latest), details={"latest": latest.isoformat()})
    return ValidationResult(validator="freshness", status="warning", code="DATA_STALE",
                            message=_("Data only reaches {latest}, {days} days before the period end ({end})", latest=latest, days=(end - latest).days, end=end),
                            details={"latest": latest.isoformat(), "end": end.isoformat()})


def period_days(date_range: tuple[str, str]) -> int:
    start, end = (date.fromisoformat(d) for d in date_range)
    return (end - start).days + 1


def comparable_periods(current: tuple[str, str], comparison: tuple[str, str]) -> ValidationResult:
    """Totals of periods with different lengths differ just by the day count; say so and by how much."""
    a, b = period_days(current), period_days(comparison)
    if a == b:
        return ValidationResult(validator="comparable_periods", status="pass", code="OK",
                                message=_("Both periods have {days} days", days=a), details={"current_days": a, "comparison_days": b})
    return ValidationResult(validator="comparable_periods", status="warning", code="UNEQUAL_PERIODS",
                            message=_("The current period has {a} days and the comparison {b}, so totals differ by the day count alone "
                                      "({diff:+.1f}%). Compare totals and counts by their per_day values", a=a, b=b, diff=(a / b - 1) * 100),
                            details={"current_days": a, "comparison_days": b})
