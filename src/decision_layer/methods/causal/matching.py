"""Pure pieces of coarsened exact matching: groups, numeric ranges, strata, weights, uncertainty.

Weights follow the target group's composition (ATT): for the strata both groups share,

    KPI_g = Σ_k n_target,k · KPI_g,k / Σ_k n_target,k

When the KPI's denominator is the matching unit (events / units) this is
unit-level CEM weighting; otherwise it is direct standardisation to the target mix.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Hashable

from ...core.models import Filter
from ..stats import is_proportion, proportion_variance, summarize
from ...i18n import _

TARGET, COMPARISON = "target", "comparison"
DEFAULT_BINS = 5
DEFAULT_QUALITY = {"min_target_retention": 0.5, "min_units_per_group": 30, "min_strata": 2}


# ── groups ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Group:
    """values: equals any; exclude: none of; gte/lt: numeric range. One kind per group."""
    values: tuple = ()
    exclude: tuple = ()
    gte: float | None = None
    lt: float | None = None

    @classmethod
    def parse(cls, spec: Any) -> "Group":
        if isinstance(spec, list):
            return cls(values=tuple(spec))
        if not isinstance(spec, dict):
            return cls(values=(spec,))
        return cls(values=tuple(spec.get("values") or ()), exclude=tuple(spec.get("exclude") or ()),
                   gte=spec.get("gte"), lt=spec.get("lt"))

    def filters(self, member: str) -> list[Filter]:
        out = []
        if self.values:
            out.append(Filter(member=member, operator="equals", values=[_fv(v) for v in self.values]))
        if self.exclude:
            out.append(Filter(member=member, operator="notEquals", values=[_fv(v) for v in self.exclude]))
        if self.gte is not None:
            out.append(Filter(member=member, operator="gte", values=[_num(self.gte)]))
        if self.lt is not None:
            out.append(Filter(member=member, operator="lt", values=[_num(self.lt)]))
        return out

    def contains(self, value: Any) -> bool:
        if value is None:
            return False
        if self.values:
            return str(value).lower() in {str(v).lower() for v in self.values}
        if self.exclude:
            return str(value).lower() not in {str(v).lower() for v in self.exclude}
        x = float(value)
        return (self.gte is None or x >= self.gte) and (self.lt is None or x < self.lt)

    def label(self) -> str:
        if self.values:
            return ", ".join(map(str, self.values))
        if self.exclude:
            return _("except {values}", values=", ".join(map(str, self.exclude)))
        parts = ([f"≥ {_num(self.gte)}"] if self.gte is not None else []) + ([f"< {_num(self.lt)}"] if self.lt is not None else [])
        return _(" and ").join(parts) or _("all")

    def to_dict(self) -> dict[str, Any]:
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in
                {"values": self.values, "exclude": self.exclude, "gte": self.gte, "lt": self.lt}.items() if v not in ((), None)}

    def complement(self) -> "Group | None":
        """The natural comparison for a one-sided range ('≥ 3' → '< 3')."""
        if self.gte is not None and self.lt is None:
            return Group(lt=self.gte)
        if self.lt is not None and self.gte is None:
            return Group(gte=self.lt)
        return None


def _fv(v: Any) -> Any:
    return "true" if v is True else "false" if v is False else v


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else repr(float(x))


# ── numeric ranges ───────────────────────────────────────────────────────
def quantile_edges(weighted: list[tuple[float, float]], bins: int = DEFAULT_BINS) -> list[float]:
    """Interior edges from (value, weight) pairs, rounded to 2 significant digits."""
    points = sorted((float(v), float(w)) for v, w in weighted if v is not None and w and w > 0)
    if not points:
        return []
    total, lo, hi = sum(w for _, w in points), points[0][0], points[-1][0]
    targets, edges, cum, t = [total * i / bins for i in range(1, bins)], [], 0.0, 0
    for value, weight in points:
        cum += weight
        while t < len(targets) and cum >= targets[t]:
            edge = _round_sig(value)
            if lo < edge <= hi and (not edges or edge > edges[-1]):
                edges.append(edge)
            t += 1
    return edges


def _round_sig(x: float, digits: int = 2) -> float:
    if x == 0 or not math.isfinite(x):
        return x
    return round(x, digits - 1 - int(math.floor(math.log10(abs(x)))))


def bin_index(value: Any, edges: list[float]) -> int | None:
    if value is None:
        return None
    x = float(value)
    return next((i for i, e in enumerate(edges) if x < e), len(edges))


def bin_group(edges: list[float], index: int) -> Group:
    return Group(gte=edges[index - 1] if index > 0 else None, lt=edges[index] if index < len(edges) else None)


def bin_label(edges: list[float], index: int) -> str:
    return bin_group(edges, index).label() if edges else _("all")


# ── strata and matching ──────────────────────────────────────────────────
@dataclass
class Cell:
    units: float
    kpi: float | None


@dataclass
class Stratum:
    key: Hashable
    label: dict[str, Any]
    cells: dict[str, Cell] = field(default_factory=dict)

    def usable(self, group: str) -> bool:
        c = self.cells.get(group)
        return bool(c and c.units > 0 and c.kpi is not None)


def weighted(strata: list[Stratum], group: str) -> float | None:
    num = sum(s.cells[TARGET].units * s.cells[group].kpi for s in strata)
    den = sum(s.cells[TARGET].units for s in strata)
    return num / den if den else None


def match(strata: list[Stratum], missing: dict[str, float], quality: dict[str, Any]) -> dict[str, Any]:
    common = [s for s in strata if s.usable(TARGET) and s.usable(COMPARISON)]
    units = lambda g, items: sum(s.cells[g].units for s in items if g in s.cells)  # noqa: E731
    t_all, c_all = units(TARGET, strata), units(COMPARISON, strata)
    t_matched, c_matched = units(TARGET, common), units(COMPARISON, common)
    imbalance = None
    if t_all and c_all:
        imbalance = 0.5 * sum(abs((s.cells[TARGET].units if TARGET in s.cells else 0) / t_all
                                  - (s.cells[COMPARISON].units if COMPARISON in s.cells else 0) / c_all) for s in strata)
    t_total = t_all + missing.get(TARGET, 0.0)
    retention = t_matched / t_total if t_total else 0.0
    q = {**DEFAULT_QUALITY, **(quality or {})}
    reasons = []
    if retention < q["min_target_retention"]:
        reasons.append(_("Only {share:.1%} of the target could be compared, below the threshold ({minimum:.0%})",
                         share=retention, minimum=q["min_target_retention"]))
    if t_matched < q["min_units_per_group"]:
        reasons.append(_("Only {n:,.0f} target units were compared, below the threshold ({minimum})",
                         n=t_matched, minimum=q["min_units_per_group"]))
    if c_matched < q["min_units_per_group"]:
        reasons.append(_("Only {n:,.0f} comparison units were compared, below the threshold ({minimum})",
                         n=c_matched, minimum=q["min_units_per_group"]))
    if len(common) < q["min_strata"]:
        reasons.append(_("Only {n} strata contain both groups, below the threshold ({minimum})", n=len(common), minimum=q["min_strata"]))
    return {
        "common": common,
        "target_kpi": weighted(common, TARGET), "comparison_kpi": weighted(common, COMPARISON),
        "balance": {
            "target_units": t_total, "target_matched_units": t_matched, "target_retention": round(retention, 4),
            "comparison_units": c_all + missing.get(COMPARISON, 0.0), "comparison_matched_units": c_matched,
            "strata_total": len(strata), "strata_common": len(common),
            "excluded": {"target_without_comparison": t_all - t_matched, "comparison_without_target": c_all - c_matched,
                         "target_missing_condition": missing.get(TARGET, 0.0),
                         "comparison_missing_condition": missing.get(COMPARISON, 0.0)},
            "imbalance_before": round(imbalance, 4) if imbalance is not None else None,
            "imbalance_after": 0.0 if common else None,
            "balance_basis": "coarsened_strata",
            "thresholds": q,
        },
        "reasons": reasons,
    }


def matched_interval(common: list[Stratum], selected_among: int | None) -> dict | None:
    """CI of the target-weighted difference when every stratum KPI is a verifiable proportion."""
    rows = [(s.cells[TARGET].units, s.cells[TARGET].kpi, s.cells[COMPARISON].units, s.cells[COMPARISON].kpi) for s in common]
    if not rows or not all(is_proportion(kt, nt) and is_proportion(kc, nc) for nt, kt, nc, kc in rows):
        return None
    total = sum(nt for nt, *_ in rows)
    diff = sum(nt / total * (kt - kc) for nt, kt, _, kc in rows)
    var = sum((nt / total) ** 2 * (proportion_variance(kt, nt) + proportion_variance(kc, nc)) for nt, kt, nc, kc in rows)
    return summarize(diff, 100 * math.sqrt(var), selected_among)
