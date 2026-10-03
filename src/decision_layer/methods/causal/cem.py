"""causal.cem — compare a target and a comparison group after aligning their conditions.

Question shape: "does the metric differ between the target and comparison group once
the listed conditions are the same?" The treatment splits units into two
groups; conditions define strata; only strata both groups share are compared,
weighted by the target's composition (see matching.py).

- dimension treatment → stratum path: the semantic layer computes the KPI and unit
  count per (group × numeric range × categorical conditions); nothing is recomputed
  here, so the KPI definition stays in the semantic layer.
- measure treatment (a per-unit numeric measure) → unit path: units are fetched at entity
  grain with the treatment, KPI and conditions, and strata are built in memory.
  Stratum KPIs are then unit averages — exact when the KPI's denominator is the unit.

The result is conditional on the listed conditions only (interpretation
causal_conditional): anything not in `conditions` can still differ.
"""
from __future__ import annotations

import asyncio
import itertools
from typing import Any

from ...core.models import Artifact, DatasetSpec, MethodManifest, ParamSpec, RoleSpec, ValidationResult
from ...validation import builtin as v
from ..base import Method, MethodOutput, registry
from ..context import ExecutionContext, NeedsInput, Refused
from ..query.common import path_filters, rnd
from ..stats import difference_test
from . import matching as m
from .matching import COMPARISON, TARGET, Group
from ...i18n import _

MAX_RANGE_COMBINATIONS = 25
MAX_GROUP_ROWS = 50_000
STRATA_PREVIEW = 20
CONCURRENCY = 4
KPI_CONSISTENCY = 0.005


class CEM(Method):
    manifest = MethodManifest(
        name="causal.cem", version="1.0.0", kind="causal",
        description=("Compares the metric of a target and a comparison group after matching them on conditions "
                     "(dimension values; numeric dimensions by range) — coarsened exact matching. Shows how a treatment "
                     "relates to the metric with the conditions held equal. A dimension treatment is aggregated in the "
                     "semantic layer; a measure treatment is evaluated per unit (the metric cube's primary key)."),
        roles={
            "metric": RoleSpec(kind="measure", description="Metric to compare"),
            "treatment": RoleSpec(kind="dimension", required=False,
                                  description="Dimension splitting the groups (yes/no or categorical). Either this or treatment_measure"),
            "treatment_measure": RoleSpec(kind="measure", required=False,
                                          description="Numeric measure splitting the groups by its per-unit value"),
            "conditions": RoleSpec(kind="dimension", multiple=True, description="Conditions to match on; numeric dimensions match by range"),
        },
        parameters={
            "target": ParamSpec(type="group", description=(
                "Target group: a value list [\"x\"] | {\"values\": [...]} | a range {\"gte\": 3}. "
                "Defaults to true for a yes/no dimension")),
            "comparison": ParamSpec(type="group", description=(
                "Comparison group: the same forms, or {\"exclude\": [target values]} for everyone else. "
                "If omitted the server asks, or uses the natural opposite")),
            "ranges": ParamSpec(type="ranges", description="Range edges for numeric conditions {member ref: [10, 100, 1000]}"),
            "drill_path": ParamSpec(type="drill_path", default=[], description="[{member, value}] narrows the population (optional)"),
            "selected_among": ParamSpec(type="integer", minimum=1, description="N when the target was picked among N candidates (selection correction)"),
            "min_target_retention": ParamSpec(type="number", default=0.5, minimum=0, maximum=1, description="Minimum share of the target that must remain in the comparison"),
            "min_units_per_group": ParamSpec(type="integer", default=30, minimum=1, description="Minimum units per group"),
        },
        execution="semantic_pushdown", interpretation="causal_conditional",
        outputs=["estimate", "balance", "interval", "table"],
    )

    async def run(self, ctx: ExecutionContext, bindings: dict[str, Any], params: dict[str, Any]) -> MethodOutput:
        metric = bindings["metric"]
        if bool(bindings.get("treatment")) == bool(bindings.get("treatment_measure")):
            raise Refused(_("Give either treatment (dimension) or treatment_measure (measure), not both"))
        treatment = bindings.get("treatment") or bindings["treatment_measure"]
        conditions = bindings["conditions"] if isinstance(bindings["conditions"], list) else [bindings["conditions"]]
        if treatment in conditions:
            raise Refused(_("The treatment can't also be a condition"))
        units = ctx.units_measure(metric) or ctx.count_measure(metric)
        if not units:
            raise Refused(_("The cube of '{title}' has no count measure, so matching isn't possible", title=ctx.obj(metric).title))
        numeric = [c for c in conditions if ctx.obj(c).data_type == "number"]
        categorical = [c for c in conditions if c not in numeric]
        base = path_filters(ctx, params.get("drill_path"))
        quality = {"min_target_retention": params["min_target_retention"],
                   "min_units_per_group": params["min_units_per_group"], "min_strata": 2}
        ranges = {c: [float(x) for x in e] for c, e in (params.get("ranges") or {}).items()}

        if ctx.obj(treatment).kind == "measure":
            target, comparison, strata, raw, missing, edges = await self._units(
                ctx, metric, units, treatment, categorical, numeric, ranges, base, params)
            path, unit_average = "unit", True
        else:
            target, comparison = await self._groups(ctx, metric, treatment, units, base, params)
            strata, raw, missing, edges = await self._strata(ctx, metric, units, treatment, target, comparison,
                                                             categorical, numeric, ranges, base)
            path, unit_average = "strata", False
        return self._finish(ctx, metric, treatment, target, comparison, categorical, numeric, ranges, edges,
                            strata, raw, missing, quality, params.get("selected_among"), path, unit_average)

    # ── groups ────────────────────────────────────────────────────────────
    async def _groups(self, ctx, metric, member, units, base, params) -> tuple[Group, Group]:
        obj = ctx.obj(member)
        target = Group.parse(params["target"]) if params.get("target") is not None else None
        comparison = Group.parse(params["comparison"]) if params.get("comparison") is not None else None
        if target is None and obj.data_type == "boolean":
            return Group(values=(True,)), comparison or Group(values=(False,))
        top = None
        if target is None:
            top = await _top_values(ctx, metric, member, units, base)
            raise NeedsInput(_("Which {title} value is the target group?", title=obj.title), "target",
                             [{"value": [t["value"]], "label": str(t["value"]), "count": t["count"]} for t in top])
        if comparison is None:
            comparison = target.complement()
        if comparison is None:
            top = top or await _top_values(ctx, metric, member, units, base)
            others = [t for t in top if not target.contains(t["value"])]
            if len(others) == 1:
                return target, Group(values=(others[0]["value"],))
            rest = {"value": {"exclude": list(target.values)}, "label": _("everyone except {target}", target=target.label())}
            cands = [{"value": [t["value"]], "label": str(t["value"]), "count": t["count"]} for t in others]
            raise NeedsInput(_("Which group should the target ({target}) be compared with?", target=target.label()), "comparison",
                             [rest, *cands] if len(others) > 5 else [*cands, rest])
        return target, comparison

    # ── stratum path ──────────────────────────────────────────────────────
    async def _strata(self, ctx, metric, units, treatment, target, comparison, categorical, numeric, ranges, base):
        groups = {TARGET: [*base, *target.filters(treatment)], COMPARISON: [*base, *comparison.filters(treatment)]}
        edges = {}
        for c in numeric:
            edges[c] = ranges.get(c) if c in ranges else await self._auto_edges(ctx, metric, units, c, groups)
        combos = list(itertools.product(*[range(len(edges[c]) + 1) for c in numeric]))
        if len(combos) > MAX_RANGE_COMBINATIONS:
            raise Refused(_("{n} numeric range combinations exceed the limit ({limit}). Use fewer ranges", n=len(combos), limit=MAX_RANGE_COMBINATIONS))
        sem = asyncio.Semaphore(CONCURRENCY)

        async def query(filters, dims):
            spec = DatasetSpec(grain="aggregate", measures=list(dict.fromkeys([metric, units])), dimensions=dims,
                               time=ctx.time_scope(metric), filters=[*ctx.scope.filters, *filters],
                               limit_rows=MAX_GROUP_ROWS)
            async with sem:
                ds = await ctx.dataset(spec)
            if len(ds.rows) >= MAX_GROUP_ROWS:
                raise Refused(_("Too many strata. Use fewer conditions"))
            return [dict(zip([col.ref for col in ds.columns], r)) for r in ds.rows]

        async def fetch(group, combo):
            filters = [*groups[group]]
            for c, i in zip(numeric, combo):
                filters += m.bin_group(edges[c], i).filters(c)
            return group, combo, await query(filters, categorical)

        fetched = await asyncio.gather(*[fetch(g, c) for g in groups for c in combos])
        raw_rows = await asyncio.gather(*[query(groups[g], []) for g in groups])
        raw = {g: ((rows[0] if rows else {}).get(metric), (rows[0] if rows else {}).get(units) or 0.0)
               for g, rows in zip(groups, raw_rows)}

        strata: dict[Any, m.Stratum] = {}
        stratified = {g: 0.0 for g in groups}
        for group, combo, rows in fetched:
            for row in rows:
                values = tuple(row.get(c) for c in categorical)
                n = row.get(units) or 0.0
                if any(x is None for x in values):
                    continue
                key = (combo, values)
                label = {**{ctx.obj(c).title: x for c, x in zip(categorical, values)},
                         **{ctx.obj(c).title: m.bin_label(edges[c], i) for c, i in zip(numeric, combo)}}
                strata.setdefault(key, m.Stratum(key, label)).cells[group] = m.Cell(n, row.get(metric))
                stratified[group] += n
        missing = {g: max(raw[g][1] - stratified[g], 0.0) for g in groups}
        return list(strata.values()), {g: raw[g][0] for g in groups}, missing, edges

    # ── unit path ─────────────────────────────────────────────────────────
    async def _units(self, ctx, metric, units, measure, categorical, numeric, ranges, base, params):
        entity = ctx.obj(metric).entity
        if not entity:
            raise Refused(_("The cube of '{title}' has no primary key, so it can't be evaluated per unit", title=ctx.obj(metric).title))
        spec = DatasetSpec(grain="entity", entity=entity, measures=list(dict.fromkeys([measure, metric, units])),
                           dimensions=[*categorical, *numeric], time=ctx.time_scope(metric),
                           filters=[*ctx.scope.filters, *base])
        ds = await ctx.dataset(spec)
        refs = [c.ref for c in ds.columns]
        rows = [dict(zip(refs, r)) for r in ds.rows]
        if not rows:
            raise Refused(_("No data in the current period, filters and access scope"))
        values = [(r.get(measure), r.get(units) or 0.0) for r in rows]
        title = ctx.obj(measure).title
        if params.get("target") is None:
            edges = m.quantile_edges([(x, w) for x, w in values if x is not None], bins=4)
            raise NeedsInput(_("How should {title} split off the target group?", title=title), "target",
                             [{"value": {"gte": e}, "label": f"{title} ≥ {e:g}",
                               "count": sum(w for x, w in values if x is not None and x >= e)} for e in edges])
        target = Group.parse(params["target"])
        comparison = Group.parse(params["comparison"]) if params.get("comparison") is not None else target.complement()
        edges = {c: ranges[c] if c in ranges else m.quantile_edges(
            [(r.get(c), r.get(units) or 0.0) for r in rows if r.get(c) is not None]) for c in numeric}

        sums: dict[Any, dict[str, list[float]]] = {}
        labels: dict[Any, dict[str, Any]] = {}
        raw_sums = {TARGET: [0.0, 0.0], COMPARISON: [0.0, 0.0]}
        missing = {TARGET: 0.0, COMPARISON: 0.0}
        for row, (value, n) in zip(rows, values):
            if value is None:
                continue
            group = TARGET if target.contains(value) else COMPARISON if comparison is None or comparison.contains(value) else None
            if group is None:
                continue
            kpi = row.get(metric)
            if kpi is None:
                missing[group] += n
                continue
            raw_sums[group][0] += n * kpi
            raw_sums[group][1] += n
            cats = tuple(row.get(c) for c in categorical)
            combo = tuple(m.bin_index(row.get(c), edges[c]) for c in numeric)
            if any(x is None for x in cats) or any(i is None for i in combo):
                missing[group] += n
                continue
            key = (combo, cats)
            labels.setdefault(key, {**{ctx.obj(c).title: x for c, x in zip(categorical, cats)},
                                    **{ctx.obj(c).title: m.bin_label(edges[c], i) for c, i in zip(numeric, combo)}})
            cell = sums.setdefault(key, {}).setdefault(group, [0.0, 0.0])
            cell[0] += n * kpi
            cell[1] += n
        strata = []
        for key, cells in sums.items():
            st = m.Stratum(key, labels[key])
            for group, (num, den) in cells.items():
                st.cells[group] = m.Cell(den, num / den if den else None)
            strata.append(st)
        raw = {g: (s[0] / s[1] if s[1] else None) for g, s in raw_sums.items()}
        return target, comparison or Group(), strata, raw, missing, edges

    async def _auto_edges(self, ctx, metric, units, member, groups) -> list[float]:
        pairs = []
        for filters in groups.values():
            spec = DatasetSpec(grain="aggregate", measures=[units], dimensions=[member], time=ctx.time_scope(metric),
                               filters=[*ctx.scope.filters, *filters], limit_rows=MAX_GROUP_ROWS)
            ds = await ctx.dataset(spec)
            if len(ds.rows) >= MAX_GROUP_ROWS:
                raise NeedsInput(_("{title} has too many distinct values for automatic ranges. Give range edges",
                                   title=ctx.obj(member).title),
                                 "ranges", [{"value": {member: []}, "label": "{\"" + member + "\": [100, 500]}"}])
            pairs += [(r[0], r[1] or 0) for r in ds.rows if r[0] is not None]
        return m.quantile_edges(pairs)

    # ── shared tail ───────────────────────────────────────────────────────
    def _finish(self, ctx, metric, treatment, target, comparison, categorical, numeric, ranges, edges, strata,
                raw, missing, quality, selected_among, path, unit_average) -> MethodOutput:
        res = m.match(strata, missing, quality)
        title = ctx.obj(treatment).title
        groups = {"treatment": treatment,
                  "target": {"label": f"{title} {target.label()}", "definition": target.to_dict()},
                  "comparison": {"label": f"{title} {comparison.label()}", "definition": comparison.to_dict()}}
        conds = [{"member": c, "title": ctx.obj(c).title, "match": "same_value"} for c in categorical] + \
                [{"member": c, "title": ctx.obj(c).title, "match": "same_range", "edges": edges.get(c),
                  "edges_source": "params" if c in ranges else "auto_quantiles"} for c in numeric]
        tk, ck = res["target_kpi"], res["comparison_kpi"]
        estimate = {
            **groups, "metric": metric, "conditions": conds, "path": path,
            "raw": {"target": rnd(raw.get(TARGET)), "comparison": rnd(raw.get(COMPARISON)),
                    "difference": rnd(raw[TARGET] - raw[COMPARISON]) if None not in (raw.get(TARGET), raw.get(COMPARISON)) else None},
            "matched": {"target": rnd(tk), "comparison": rnd(ck),
                        "difference": rnd(tk - ck) if None not in (tk, ck) else None},
        }
        limitations = [_("Observational comparison: differences in anything not listed in conditions can remain.")]
        if numeric:
            limitations.append(_("Numeric conditions were matched by range, so differences within a range remain."))
        if unit_average:
            limitations.append(_("Evaluated per unit, so stratum metrics are unit averages; they can differ from the metric's definition when its denominator is not the unit count."))
        elif not missing[TARGET] and _inconsistent(_standardized_all(strata), raw.get(TARGET)):
            limitations.append(_("The metric's denominator is not the matching unit, so this is the comparison group standardised to the target's condition mix."))
        if res["balance"]["excluded"]["target_without_comparison"]:
            limitations.append(_("{n:,.0f} target units with no comparison unit in the same conditions were left out.",
                                 n=res["balance"]["excluded"]["target_without_comparison"]))

        interval = m.matched_interval(res["common"], selected_among)
        raw_interval = difference_test(raw.get(TARGET), res["balance"]["target_units"], raw.get(COMPARISON),
                                       res["balance"]["comparison_units"])
        artifacts = [Artifact(type="balance", title=_("matching quality"), data=res["balance"])]
        if interval:
            artifacts.append(Artifact(type="interval", title=_("95% interval of the matched difference (pp)"), data=interval))
        if raw_interval:
            artifacts.append(Artifact(type="interval", title=_("95% interval of the unmatched difference (pp)"), data=raw_interval))
        preview = sorted(res["common"], key=lambda s: -s.cells[TARGET].units)[:STRATA_PREVIEW]
        artifacts.append(Artifact(type="table", title=_("Top {n} shared strata", n=len(preview)), data=[
            {"condition": s.label, "target": {"units": s.cells[TARGET].units, "metric": rnd(s.cells[TARGET].kpi)},
             "comparison": {"units": s.cells[COMPARISON].units, "metric": rnd(s.cells[COMPARISON].kpi)}} for s in preview]))
        if not interval:
            limitations.append(_("The metric could not be verified as a count proportion, so no interval was computed."))

        comparable = (ValidationResult(validator="comparability", status="fail", code="NOT_COMPARABLE",
                                       message="; ".join(res["reasons"]), details=res["balance"])
                      if res["reasons"] else
                      ValidationResult(validator="comparability", status="pass", code="OK",
                                       message=_("{share:.1%} of the target compared across {strata} shared strata",
                                                 share=res["balance"]["target_retention"], strata=res["balance"]["strata_common"])))
        return MethodOutput(
            primary=Artifact(type="estimate", title=f"{groups['target']['label']} vs {groups['comparison']['label']}",
                             data=estimate),
            artifacts=artifacts, warnings=limitations,
            validation=[comparable, v.complete_period(ctx.scope.date_range)],
        )


async def _top_values(ctx: ExecutionContext, metric: str, member: str, units: str, base) -> list[dict[str, Any]]:
    spec = DatasetSpec(grain="aggregate", measures=[units], dimensions=[member], time=ctx.time_scope(metric),
                       filters=[*ctx.scope.filters, *base], order=[(units, "desc")], limit_rows=50)
    ds = await ctx.dataset(spec)
    return [{"value": r[0], "count": r[1]} for r in ds.rows if r[0] is not None]


def _standardized_all(strata: list[m.Stratum]) -> float | None:
    usable = [s for s in strata if s.usable(TARGET)]
    den = sum(s.cells[TARGET].units for s in usable)
    return sum(s.cells[TARGET].units * s.cells[TARGET].kpi for s in usable) / den if den else None


def _inconsistent(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and abs(a - b) > KPI_CONSISTENCY * max(abs(b), 1e-9)


registry.register(CEM())
