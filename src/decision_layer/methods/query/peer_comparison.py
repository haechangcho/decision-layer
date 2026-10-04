"""Compare a selected subject with explicit peers and the accessible population."""
from __future__ import annotations

from ...core.models import Artifact, Filter, MethodManifest, ParamSpec, RoleSpec
from ...i18n import _
from ...validation import builtin as v
from ..base import Method, MethodOutput, registry
from ..context import Refused
from .common import path_filters, rnd, totals


class PeerComparison(Method):
    manifest = MethodManifest(
        name="query.peer_comparison", version="1.0.0", kind="query",
        description="Compare a selected subject against explicitly defined peers and the accessible overall population. "
                    "Preserves scope and source aggregation. Descriptive, not risk-adjusted or causal; a high value is not wrongdoing.",
        roles={"metric": RoleSpec(kind="measure", description="Metric to compare")},
        parameters={
            "subject": ParamSpec(type="drill_path", required=True, ui_group="basic",
                                 description="One selected dimension and value, e.g. an adviser ID"),
            "peers": ParamSpec(type="drill_path", default=[], ui_group="basic",
                               description="Explicit peer conditions, e.g. department; empty means the accessible population"),
            "min_count": ParamSpec(type="integer", default=30, minimum=1,
                                   description="Minimum source row count for a comparison; not a significance threshold"),
        },
        execution="semantic_pushdown", interpretation="descriptive", outputs=["breakdown_table"],
    )

    async def run(self, ctx, bindings, params):
        metric = bindings["metric"]
        subject, peers = params["subject"], params["peers"]
        if len(subject) != 1:
            raise Refused(_("Select one subject dimension and value for peer comparison"))
        for item in [*subject, *peers]:
            if ctx.obj(item["member"]).kind != "dimension" or item["value"] is None:
                raise Refused(_("Peer comparison conditions need a dimension and a non-null value"))
        member = subject[0]["member"]
        if any(item["member"] == member for item in peers) or any(f.member == member for f in ctx.scope.filters):
            raise Refused(_("Keep the subject filter in subject, not in peers or the shared scope"))
        if len({item["member"] for item in peers}) != len(peers):
            raise Refused(_("Peer conditions must use distinct dimensions"))
        count = ctx.count_measure(metric)
        measures = [metric, *([count] if count else [])]
        peer_filters = path_filters(ctx, peers)
        target_filters = path_filters(ctx, subject)
        # Explicit exclusion avoids comparing a subject to a benchmark containing itself.
        excluded = Filter(member=member, operator="notEquals", values=[subject[0]["value"]])
        target = (await totals(ctx, measures, metric, None, [*peer_filters, *target_filters]) or [{}])[0]
        peer = (await totals(ctx, measures, metric, None, [*peer_filters, excluded]) or [{}])[0]
        overall = (await totals(ctx, measures, metric, None, [excluded]) or [{}])[0]
        value = target.get(metric)
        rows = []
        for label, record in ((_("Selected subject"), target), (_("Peers excluding subject"), peer),
                              (_("Overall excluding subject"), overall)):
            n, benchmark = record.get(count) if count else None, record.get(metric)
            rows.append({"value": label, "metric": rnd(benchmark), "count": n,
                         "difference_from_subject": rnd(value - benchmark) if value is not None and benchmark is not None else None})
        checks = [v.non_empty(int(row["metric"] is not None), row["value"]) for row in rows]
        if count:
            checks += [v.min_sample(row["count"] or 0, params["min_count"], row["value"]) for row in rows]
            checks = [check.model_copy(update={"status": "fail"}) if check.code == "SMALL_SAMPLE" else check for check in checks]
        warnings = [_("Descriptive comparison only: case mix and prior selection are not adjusted; no significance or misconduct claim is made.")]
        if ctx.obj(metric).metric_kind in ("additive", "count"):
            warnings.append(_("Totals depend on population size; use a governed rate or average for performance comparison."))
        return MethodOutput(primary=Artifact(type="breakdown_table", title=_("Peer group comparison"), data={
            "metric": metric, "subject": subject, "peers": peers, "exclude_subject": True,
            "scope_filters": [f.model_dump() for f in ctx.scope.filters], "rows": rows,
            "date_range": ctx.scope.date_range,
            "benchmark_aggregation": "semantic_provider", "statistical_judgement": "not_tested",
        }), validation=checks, warnings=warnings)


registry.register(PeerComparison())
