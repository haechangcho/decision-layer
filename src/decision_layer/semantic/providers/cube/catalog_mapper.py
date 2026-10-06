"""Cube /meta → canonical SemanticCatalog.

Rules (ADR-023, ADR-026):
- Refs always name the **base** cube member; views re-expose members through
  `aliasMember`, and are only used at query time (compiler.py).
- /meta may list a view before the cube it re-exposes, and member meta often
  lives on the view (e.g. preAggregation hints) — merge after the loop.
- Cube camelCases meta keys; keep them untouched in `metadata`.
- Native hierarchies are optional; custom meta does not define ratio semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ....core.ids import SemanticRef
from ....core.models import MetricKind, SemanticCatalog, SemanticObject

_METRIC_KIND: dict[str, MetricKind] = {
    "count": "count", "countDistinct": "count", "countDistinctApprox": "count",
    "sum": "additive", "runningTotal": "additive",
    "avg": "average",
    "number": "other", "min": "other", "max": "other", "string": "other", "time": "other", "boolean": "other",
}
_DATA_TYPE = {"number": "number", "string": "string", "boolean": "boolean", "time": "time"}


@dataclass
class ViewIndex:
    """base member name → view member name, per view."""
    views: dict[str, dict[str, str]] = field(default_factory=dict)

    def target(self, members: set[str]) -> str | None:
        """Smallest view exposing every member (most specific), else None (query base cubes)."""
        covering = [(len(m), v) for v, m in self.views.items() if members <= m.keys()]
        return min(covering)[1] if covering else None


def map_meta(meta: dict[str, Any], instance: str) -> tuple[SemanticCatalog, ViewIndex]:
    ref = lambda member: str(SemanticRef.from_member(member, instance))  # noqa: E731
    objects: dict[str, SemanticObject] = {}
    view_meta: dict[str, dict[str, Any]] = {}
    view_members: dict[str, dict[str, Any]] = {}
    views = ViewIndex()
    hierarchies: dict[str, list[str]] = {}
    primary_keys: dict[str, str] = {}

    for cube in meta.get("cubes", []):
        is_view = cube.get("type") == "view"
        if is_view:
            views.views[cube["name"]] = {}
        for kind, key in (("measure", "measures"), ("dimension", "dimensions")):
            for m in cube.get(key, []):
                name = m["name"]
                base = m.get("aliasMember") or name
                if is_view:
                    views.views[cube["name"]][base] = name
                    view_members.setdefault(base, {**m, "_kind": kind})
                    if m.get("meta"):
                        view_meta.setdefault(base, {}).update(m["meta"])
                    continue
                objects[base] = _object(ref(base), m, kind)
                if kind == "dimension" and m.get("primaryKey"):
                    primary_keys[base.split(".")[0]] = base
        if not is_view:
            for h in cube.get("hierarchies", []) or []:
                hierarchies[ref(h["name"])] = [ref(level) for level in h.get("levels", [])]

    # Members visible only through a view (base cube private) still get a canonical object.
    for base, m in view_members.items():
        if base not in objects:
            objects[base] = _object(ref(base), m, m["_kind"])
    for base, extra in view_meta.items():
        obj = objects[base]
        objects[base] = obj.model_copy(update={"metadata": {**extra, **obj.metadata}})

    finished = []
    for base, obj in objects.items():
        cube_name = base.split(".")[0]
        updates: dict[str, Any] = {}
        if cube_name in primary_keys:
            updates["entity"] = ref(primary_keys[cube_name])
        finished.append(obj.model_copy(update=updates) if updates else obj)

    catalog = SemanticCatalog(provider="cube", instance=instance, objects=sorted(finished, key=lambda o: o.ref),
                              hierarchies=hierarchies)
    for obj in catalog.objects:
        if obj.kind != "measure":
            continue
        group = SemanticRef.parse(obj.ref).cube
        local = [o for o in catalog.objects if SemanticRef.parse(o.ref).cube == group]
        obj.dimension_refs = [o.ref for o in local if o.kind != "measure"]
        times = [o.ref for o in local if o.kind == "time_dimension"]
        pre = obj.metadata.get("preAggregation") or obj.metadata.get("pre_aggregation") or {}
        name = pre.get("timeDimension") or pre.get("time_dimension")
        hint = ref(name if "." in name else f"{group}.{name}") if name else None
        obj.time_dimension = hint if hint in times else (times[0] if len(times) == 1 else None)
    return catalog, views


def _object(ref: str, m: dict[str, Any], kind: str) -> SemanticObject:
    cube_type = m.get("type", "string")
    if kind == "measure":
        return SemanticObject(
            ref=ref, kind="measure", data_type="number",
            title=m.get("shortTitle") or m.get("title") or ref,
            description=(m.get("description") or None),
            metric_kind=_METRIC_KIND.get(m.get("aggType") or cube_type, "other"),
            public=m.get("public", m.get("isVisible", True)),
            # A sibling count does not establish a calculated metric's sample grain.
            count_measure=ref if (m.get("aggType") or cube_type) == "count" else None,
            metadata=dict(m.get("meta") or {}),
        )
    return SemanticObject(
        ref=ref, kind="time_dimension" if cube_type == "time" else "dimension",
        data_type=_DATA_TYPE.get(cube_type, "string"),
        title=m.get("shortTitle") or m.get("title") or ref,
        description=(m.get("description") or None),
        public=m.get("public", m.get("isVisible", True)),
        metadata=dict(m.get("meta") or {}),
    )
