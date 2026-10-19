"""Aliased datasets and bounded query conveniences over ExecutionContext.dataset."""
from __future__ import annotations
from ..i18n import _
import math
from ..core.models import DatasetSpec, Filter, TimeScope
from ..core.periods import checked_range
from .context import Refused


class MethodData:
    def __init__(self, dataset, roles):
        self.dataset = dataset
        self.roles = roles

    def columns(self, role):
        if role not in self.roles:
            raise Refused(_("The requested dataset role is unavailable"))
        return [name for name, ref in self.roles[role]]

    def column(self, role):
        columns = self.columns(role)
        if len(columns) != 1:
            raise Refused(_("A scalar column role must select exactly one field"))
        return columns[0]

    def records(self):
        available = {column.ref for column in self.dataset.columns}
        if any(ref not in available for pairs in self.roles.values() for name, ref in pairs):
            raise Refused(_("The provider did not return every requested column"))
        result = []
        for row in self.dataset.rows:
            if len(row) != len(self.dataset.columns):
                raise Refused(_("The provider returned an invalid row shape"))
            values = dict(zip([column.ref for column in self.dataset.columns], row))
            result.append({name: values[ref] for pairs in self.roles.values() for name, ref in pairs})
        return result

    @property
    def frame(self):
        import pandas as pd
        return pd.DataFrame(self.records(), columns=[name for pairs in self.roles.values() for name, ref in pairs])

    def scalar(self, role, *, require_finite=True, require_one_row=True):
        rows = self.records()
        if not rows or (require_one_row and len(rows) != 1):
            raise Refused(_("A scalar query requires exactly one observation"))
        value = rows[0][self.column(role)]
        if require_finite and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise Refused(_("The scalar metric must be finite and non-null"))
        return value


def _fields(values, roles):
    if values is None:
        return []
    if not isinstance(values, dict):
        # Legacy convenient ref lists keep their original column names.
        values = {ref: ref for ref in values}
    selected = []
    names = {name for pairs in roles.values() for name, ref in pairs}
    for role, value in values.items():
        if role in roles:
            raise ValueError("Dataset role names must be unique")
        if not isinstance(role, str) or not role:
            raise ValueError("Dataset roles require non-empty names")
        refs = value if isinstance(value, list) else [value]
        if not refs or any(not isinstance(ref, str) for ref in refs):
            raise ValueError("Dataset fields require semantic references")
        pairs = [(f"{role}_{index}" if isinstance(value, list) else role, ref)
                 for index, ref in enumerate(refs)]
        if names.intersection(name for name, ref in pairs):
            raise ValueError("Dataset column aliases collide")
        roles[role] = pairs
        names.update(name for name, ref in pairs)
        selected.extend(refs)
    return list(dict.fromkeys(selected))


async def request_data(ctx, *, entity=None, entity_alias="unit", measures=None, dimensions=None, columns=None, filters=None,
                       period=None, period_role="current", by_time=None, time_granularity=None,
                       order=None, limit=None, label=None):
    if not entity and not ctx.provider.capabilities().aggregate_queries:
        raise Refused(_("The provider lacks a required Method capability"))
    if period_role not in ("current", "comparison"):
        raise ValueError("period_role must be current or comparison")
    dates = checked_range(period) if period is not None else ctx.scope.date_range
    if dates and period_role == "current" and ctx.scope.date_range:
        if dates[0] < ctx.scope.date_range[0] or dates[1] > ctx.scope.date_range[1]:
            raise Refused(_("Current query periods must stay inside the Run scope"))
    if by_time and ctx.scope.time_dimension and by_time != ctx.scope.time_dimension:
        raise Refused(_("Panel time must match the selected scope time dimension"))
    if by_time and not time_granularity:
        raise Refused(_("Panel extraction needs an explicit time granularity"))
    roles = {}
    if entity:
        if not ctx.provider.capabilities().entity_grain_queries:
            raise Refused(_("The provider cannot produce entity-grain observations"))
        obj = ctx.obj(entity)
        if obj.kind != "dimension" or not any(o.public and o.entity == entity for o in ctx.catalog.objects):
            raise Refused(_("The analysis unit must be a provider-declared primary dimension"))
        roles[entity_alias] = [(entity_alias, entity)]
    selected_dimensions = _fields(dimensions, roles)
    selected_columns = _fields(columns, roles)
    selected_measures = _fields(measures, roles)
    selected_measures = list(dict.fromkeys([
        *selected_measures,
        *(ref for ref in selected_columns if ctx.obj(ref).kind == "measure"),
    ]))
    selected_dimensions = list(dict.fromkeys([
        *selected_dimensions,
        *(ref for ref in selected_columns if ctx.obj(ref).kind != "measure"),
    ]))
    if entity:
        # Statistical variables can be native per-unit measures or dimensions.
        variable_measures = [ref for ref in selected_dimensions if ctx.obj(ref).kind == "measure"]
        selected_measures = list(dict.fromkeys([*selected_measures, *variable_measures]))
        selected_dimensions = [ref for ref in selected_dimensions if ref not in variable_measures]
    for ref in selected_measures:
        if ctx.obj(ref).kind != "measure":
            raise Refused(_("Measure roles must select governed measures"))
    for ref in selected_dimensions:
        if ctx.obj(ref).kind not in ("dimension", "time_dimension"):
            raise Refused(_("Dimension roles must select governed dimensions"))
    metric = selected_measures[0] if selected_measures else None
    time_ref = by_time or (ctx.time_dimension_for(metric) if metric and (dates or time_granularity) else ctx.scope.time_dimension)
    time = TimeScope(dimension=time_ref, date_range=dates, granularity=time_granularity) if time_ref and (dates or time_granularity) else None
    if dates and time is None:
        raise Refused(_("The selected period needs a governed time dimension"))
    if time_granularity:
        if "time" in roles:
            raise ValueError("time is reserved for the selected time bucket")
        roles = {"time": [("time", time_ref)], **roles}
    extras = [f if isinstance(f, Filter) else Filter.model_validate(f) for f in filters or []]
    width = sum(len(pairs) for pairs in roles.values())
    if width > 100:
        raise Refused(_("The requested dataset exceeds the materialization column bound"), maximum=100)
    bound = min(ctx.execution_policy.max_result_rows if ctx.execution_policy else 50_000,
                2_000_000 // max(width, 1))
    if entity and limit is not None:
        raise Refused(_("Complete entity extraction cannot use an analytical top-N limit"))
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > bound):
        raise Refused(_("The requested row limit is outside the execution policy"))
    spec = DatasetSpec(grain="entity" if entity else "aggregate", entity=entity,
        measures=selected_measures, dimensions=selected_dimensions,
        time=time, filters=[*ctx.scope.filters, *extras], order=order or [],
        limit_rows=limit if limit is not None else bound + 1)
    dataset = await ctx.dataset(spec, with_sql=ctx.provider.capabilities().compiled_sql, label=label)
    if len(dataset.rows) > bound:
        raise Refused(_("The result exceeds the complete-extraction bound"))
    data = MethodData(dataset, roles)
    if entity:
        keys = [entity_alias, *(["time"] if time_granularity else [])]
        seen = set()
        for row in data.records():
            key = tuple(row[name] for name in keys)
            if any(value is None for value in key) or key in seen:
                raise Refused(_("Entity observations need unique non-null analysis keys"))
            seen.add(key)
    return data
