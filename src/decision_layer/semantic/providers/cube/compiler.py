"""DatasetSpec → Cube REST query, and Cube rows → typed columns."""
from __future__ import annotations

from typing import Any

from ....core.ids import SemanticRef
from ....core.models import Column, DatasetSpec, SemanticCatalog
from .catalog_mapper import ViewIndex


def spec_members(spec: DatasetSpec) -> list[str]:
    refs = [*spec.measures, *spec.dimensions, *[f.member for f in spec.filters], *[r for r, _ in spec.order]]
    if spec.entity:
        refs.append(spec.entity)
    if spec.time:
        refs.append(spec.time.dimension)
    return list(dict.fromkeys(refs))


def _value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


class CompiledQuery:
    """The Cube query plus the mapping back from Cube column keys to semantic refs."""

    def __init__(self, query: dict[str, Any], columns: list[Column], keys: list[str], view: str | None) -> None:
        self.query = query
        self.columns = columns
        self.keys = keys            # Cube response key per column, same order as columns
        self.view = view


def compile_spec(spec: DatasetSpec, catalog: SemanticCatalog, views: ViewIndex) -> CompiledQuery:
    base = {r: SemanticRef.parse(r).member_name for r in spec_members(spec)}
    view = views.target(set(base.values()))
    name = (lambda r: views.views[view][base[r]]) if view else (lambda r: base[r])  # noqa: E731

    columns: list[Column] = []
    keys: list[str] = []
    dims = ([spec.entity] if spec.grain == "entity" and spec.entity else []) + [d for d in spec.dimensions if d != spec.entity]
    for r in dims:
        obj = catalog.get(r)
        columns.append(Column(ref=r, role="entity" if r == spec.entity else "dimension", data_type=obj.data_type))
        keys.append(name(r))
    query: dict[str, Any] = {"dimensions": [name(r) for r in dims]} if dims else {}
    if spec.measures:
        query["measures"] = [name(r) for r in spec.measures]
    if spec.time:
        td: dict[str, Any] = {"dimension": name(spec.time.dimension)}
        if spec.time.date_range:
            td["dateRange"] = list(spec.time.date_range)
        if spec.time.granularity:
            td["granularity"] = spec.time.granularity
            columns.append(Column(ref=spec.time.dimension, role="time", data_type="time", granularity=spec.time.granularity))
            keys.append(f"{name(spec.time.dimension)}.{spec.time.granularity}")
        query["timeDimensions"] = [td]
    for r in spec.measures:
        columns.append(Column(ref=r, role="measure", data_type="number"))
        keys.append(name(r))
    if spec.filters:
        query["filters"] = [{"member": name(f.member), "operator": f.operator,
                             **({"values": [_value(v) for v in f.values]} if f.values else {})} for f in spec.filters]
    order = spec.order or ([(spec.entity, "asc")] if spec.grain == "entity" and spec.entity else [])
    if order:
        query["order"] = [[name(r), d] for r, d in order]
    return CompiledQuery(query, columns, keys, view)


def convert(value: Any, data_type: str) -> Any:
    """Cube returns measures as strings and booleans in various spellings."""
    if value is None:
        return None
    if data_type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if data_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "t", "yes")
    return value
