"""Query the declared input tables and record their resolved column mappings."""

from __future__ import annotations

from ...core.models import Filter


async def query_inputs(ctx, inputs, roles, bindings, params):
    rows, resolved = {}, {}

    def bound(name):
        value = bindings[name]
        if roles[name].multiple:
            return value if isinstance(value, list) else [value]
        return value[0] if isinstance(value, list) else value

    for name, spec in inputs.items():
        entity_alias = spec.entity if spec.entity in spec.columns else "unit"
        data = await ctx.aggregate(
            measures={n: bound(n) for n in spec.measures},
            dimensions={n: bound(n) for n in spec.dimensions},
            columns={
                n: bound(n)
                for n in spec.columns
                if n != spec.entity and bindings.get(n)
            },
            entity=bound(spec.entity) if spec.entity else None,
            entity_alias=entity_alias,
            period=params.get(spec.period_parameter) if spec.period_parameter else None,
            period_role=spec.period_role,
            filters=[
                Filter.model_validate(item)
                for item in params.get(spec.filters_parameter, [])
            ]
            if spec.filters_parameter
            else None,
            time_granularity=spec.time_granularity,
            label=f"python:{name}",
        )
        rows[name] = data.records()
        aliases = {alias: ref for pairs in data.roles.values() for alias, ref in pairs}
        resolved[name] = {
            "columns": list(aliases),
            "semantic_refs": aliases,
            "measures": [
                alias
                for alias, ref in aliases.items()
                if ref in data.dataset.spec.measures
            ],
            "numeric_columns": [
                alias
                for role, pairs in data.roles.items()
                if role in spec.columns and spec.columns[role].data_type == "number"
                for alias, ref in pairs
                if ref not in data.dataset.spec.measures
            ],
            "grain": "entity" if spec.entity else "aggregate",
            "grain_keys": (
                [entity_alias]
                if spec.entity
                else [
                    alias
                    for alias, ref in aliases.items()
                    if ref in data.dataset.spec.dimensions
                ]
            )
            + (["time"] if spec.time_granularity else []),
        }
        resolved[name]["column_args"] = {
            argument: (
                [alias for alias, _ in data.roles.get(argument, [])]
                if roles[argument].multiple
                else next((alias for alias, _ in data.roles.get(argument, [])), None)
            )
            for argument in spec.column_args
        }
    return rows, resolved
