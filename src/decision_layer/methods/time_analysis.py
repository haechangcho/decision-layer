"""Reusable time-series calculations and executed checks, separate from query Skills."""
from ..core.models import Artifact, DatasetSpec, Filter, MethodManifest, ParamSpec, RoleSpec, ValidationResult
from ..i18n import _
from ..validation import builtin as v
from .base import Method, MethodOutput
from .context import Refused
from .change import period_change
from .common import analysis_period, path_filters, rnd


def largest_moves(series, metrics):
    """Return each series' largest observed adjacent change; preserve all ties."""
    moves = []
    for metric in metrics:
        pairs = [(a, b) for a, b in zip(series, series[1:])
                 if a.get(metric) is not None and b.get(metric) is not None]
        if not pairs:
            continue
        maximum = max(abs(b[metric] - a[metric]) for a, b in pairs)
        for a, b in pairs:
            if abs(b[metric] - a[metric]) == maximum:
                moves.append({'metric': metric, 'from': a['period'], 'to': b['period'],
                    'before': a[metric], 'after': b[metric], 'change': rnd(b[metric] - a[metric])})
    return moves


ROLES = {
    'metric': RoleSpec(kind='measure', default_binding='primary_metric'),
    'related': RoleSpec(kind='measure', multiple=True, required=False),
}
PARAMS = {
    'filters': ParamSpec(type='filters', default=[]),
    'drill_path': ParamSpec(type='drill_path', default=[]),
}


def selected_filters(ctx, params):
    return [*path_filters(ctx, params.get('drill_path', [])),
            *(Filter.model_validate(f) for f in params.get('filters', []))]


class PeriodChange(Method):
    manifest = MethodManifest(name='stats.period_change', version='1.0.0', kind='stats',
        description='Calculate explicit period changes, per-day comparisons, supported tests and declared factor decompositions; no causal claim.',
        roles=ROLES, parameters={**PARAMS, 'comparison': ParamSpec(type='date_range', required=True)},
        requires_period=True, requires_capabilities=['aggregate_queries'], execution='semantic_pushdown',
        interpretation='association', outputs=['estimate'], provides=['period_change'])

    async def run(self, ctx, bindings, params):
        current = analysis_period(ctx, {})
        if not current:
            raise Refused(_('An analysis period is required.'))
        filters = selected_filters(ctx, params)
        summary, checks = await period_change(ctx, bindings['metric'], current, tuple(params['comparison']),
                                              filters, bindings.get('related') or [])
        if summary.get('current') is None or summary.get('comparison') is None:
            checks.append(ValidationResult(validator='period_values', code='MISSING_PERIOD_VALUE', status='fail',
                message=_('Both periods need an observed metric value.')))
        checks.append(await v.freshness(ctx, bindings['metric'], current, filters=filters))
        return MethodOutput(primary=Artifact(type='estimate', title=_('Change between periods'), data=summary), validation=checks,
            warnings=[_('Only supported aggregates and tests are computed. Checks do not establish ingestion completeness or causality.')])


class SeriesDiagnostics(Method):
    manifest = MethodManifest(name='stats.series_diagnostics', version='1.0.0', kind='stats',
        description='Calculate largest observed adjacent time-bucket changes and check calendar period and observed date coverage.',
        roles=ROLES, parameters={**PARAMS, 'granularity': ParamSpec(type='enum', enum=['day','week','month','quarter'], default='month')},
        requires_period=True, requires_capabilities=['aggregate_queries'], execution='semantic_pushdown',
        interpretation='association', outputs=['time_series', 'table'], provides=['time_series'])

    def __init__(self, fn=None, *, version='1.0.0'):
        # Existing source-bound extraction/checks remain canonical. Contributors
        # can replace only the ordinary calculation without copying this adapter.
        if fn is not None:
            import inspect
            if not inspect.isfunction(fn) or inspect.iscoroutinefunction(fn):
                raise ValueError('Register an ordinary synchronous calculation function')
            self.fn = fn
        self.manifest = self.manifest.model_copy(deep=True, update={'version':version})
        if fn is not None:
            self.manifest.requires_packages = {'pandas':'>=2.2,<3'}

    async def run(self, ctx, bindings, params):
        metric = bindings['metric']
        span = analysis_period(ctx, {})
        if not span:
            raise Refused(_('An analysis period is required.'))
        filters = selected_filters(ctx, params)
        metrics = list(dict.fromkeys([metric, *(bindings.get('related') or [])]))
        time = ctx.time_scope(metric, span, granularity=params['granularity'])
        ds = await ctx.dataset(DatasetSpec(grain='aggregate', measures=metrics, time=time,
            filters=[*ctx.scope.filters, *filters], order=[(time.dimension, 'asc')], limit_rows=400))
        refs = [c.ref for c in ds.columns]
        series = [{'period': str(row[time.dimension])[:10], **{m: row.get(m) for m in metrics}}
                  for row in (dict(zip(refs, r)) for r in ds.rows)]
        checks = [v.non_empty(len(series)), v.complete_period(span),
                  await v.freshness(ctx, metric, span, filters=filters)]
        moves = []
        if getattr(self, 'fn', None) and not any(check.status == 'fail' for check in checks):
            import pandas as pd
            data = pd.DataFrame([{'period':row['period'], 'metric':metric, 'value':row.get(metric)}
                                 for metric in metrics for row in series], columns=['period','metric','value'])
            calculated = await ctx.compute(self.fn, data)
            if not isinstance(calculated, pd.DataFrame) or list(calculated.columns) != ['metric','from','to','before','after','change']:
                raise ValueError('Series calculation must return metric/from/to/before/after/change columns')
            moves = calculated.to_dict(orient='records')
        elif not getattr(self, 'fn', None):
            moves = largest_moves(series, metrics)
        return MethodOutput(primary=Artifact(type='time_series', title=_('Values over time'),
            data={'metric':metric, 'related':metrics[1:], 'granularity':params['granularity'], 'rows':series}),
            artifacts=[Artifact(type='table',title=_('Largest observed adjacent changes (including ties)'),data=moves)],
            validation=checks, warnings=[_('Changes concern returned adjacent observations. Missing time buckets are not filled with zero; largest changes are not statistical anomalies or causal effects.')])
