"""Small, dependency-free statistics shared by Methods.

Intervals are only produced for proportion metrics — a share of units such as
events / units × 100 — and only when that is verifiable from the data:
value × units / 100 must be a whole number of events. Amount-weighted rates and
averages fail the check and get no interval rather than a wrong one.
"""
from __future__ import annotations

import math
from statistics import NormalDist

Z95 = 1.959964
_EVENT_TOLERANCE = 0.02


def is_proportion(value: float | None, units: float | None) -> bool:
    if value is None or not units or units <= 0 or not 0 <= value <= 100:
        return False
    events = value * units / 100
    return abs(events - round(events)) <= _EVENT_TOLERANCE


def proportion_variance(value: float, units: float) -> float:
    p = value / 100
    return p * (1 - p) / units


def difference_test(a: float | None, n_a: float | None, b: float | None, n_b: float | None,
                    selected_among: int | None = None) -> dict | None:
    """95% CI and z for a − b (percentage points) when both sides are proportions; None otherwise."""
    if not (is_proportion(a, n_a) and is_proportion(b, n_b)):
        return None
    se = 100 * math.sqrt(proportion_variance(a, n_a) + proportion_variance(b, n_b))
    return summarize(a - b, se, selected_among)


def summarize(diff: float, se: float, selected_among: int | None = None) -> dict:
    z = diff / se if se > 0 else None
    out = {
        "difference": round(diff, 4),
        "standard_error": round(se, 4),
        "ci95": [round(diff - Z95 * se, 4), round(diff + Z95 * se, 4)],
        "z": round(z, 2) if z is not None else None,
        "significant": bool(z is not None and abs(z) > Z95),
    }
    if selected_among and selected_among > 1:
        # the subject was the top of a ranking of N groups: Bonferroni-adjusted threshold
        critical = NormalDist().inv_cdf(1 - 0.025 / selected_among)
        out["selection"] = {
            "selected_among": selected_among,
            "adjusted_critical_z": round(critical, 2),
            "significant_after_selection": bool(z is not None and abs(z) > critical),
        }
    return out


def safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return a / b


def pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / abs(previous) * 100, 2)
