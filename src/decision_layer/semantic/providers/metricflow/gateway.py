"""Self-hosted dbt MetricFlow gateway. Install the metricflow extra in its own environment.

The deployment owns its dbt project and warehouse credentials. Requests contain
canonical dataset specs only; no caller-supplied SQL, Python, project path or Jinja.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, time as daytime
import hmac
import os
import threading
import time

from fastapi import Depends, FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ....core.errors import CapabilityMissing, DatasetTooLarge, DecisionLayerError, InvalidDatasetSpec
from ....core.models import Column, Dataset, DatasetSpec, QueryProvenance, SemanticCatalog, SemanticObject
from .provider import capabilities


def _literal(value):
    if isinstance(value, str) and any(marker in value for marker in ("{{", "{%", "{#")):
        raise InvalidDatasetSpec("Template delimiters are not supported in filter values.")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        import math
        if not math.isfinite(value):
            raise InvalidDatasetSpec("Filter numbers must be finite.")
        return str(value)
    # PostgreSQL standard strings: escape both quotes and backslashes explicitly.
    return "E'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


class MetricFlowRuntime:
    def __init__(self, instance: str):
        from dbt_metricflow.cli.cli_configuration import CLIConfiguration
        self.config = CLIConfiguration()
        self.config.setup(configure_file_logging=False)
        self.engine = self.config.mf
        self.instance = instance
        self.lock = threading.Lock()
        self.catalog = self._catalog()

    def _catalog(self):
        manifest = self.config.semantic_manifest
        ref = lambda name: f"metricflow://{self.instance}/metrics/{name}"
        dim_ref = lambda name: f"metricflow://{self.instance}/dimensions/{name}"
        objects = {}
        definitions = {m.name: m for m in manifest.metrics}
        measures = {m.name: m for model in manifest.semantic_models for m in model.measures}
        for item in self.engine.list_metrics():
            definition = definitions[item.name]
            raw = definition.dict()
            dimensions = []
            for dim in item.dimensions:
                name = dim.granularity_free_dunder_name
                dimensions.append(dim_ref(name))
                is_time = name == "metric_time" or any(
                    name.endswith("__" + d.name) and str(d.type.value) == "time"
                    for model in manifest.semantic_models for d in model.dimensions)
                objects[dim_ref(name)] = SemanticObject(ref=dim_ref(name), kind="time_dimension" if is_time else "dimension",
                    data_type="time" if is_time else "string", title=name.replace("__", " / ").replace("_", " "),
                    metadata={"native_name": name})
            kind = "other"
            input_measure = definition.type_params.measure
            if input_measure and input_measure.name in measures:
                agg = measures[input_measure.name].agg.value
                kind = {"sum": "additive", "count": "count", "count_distinct": "count", "average": "average"}.get(agg, "other")
            numerator, denominator = None, None
            if definition.type.value == "ratio":
                numerator = definition.type_params.numerator.name
                denominator = definition.type_params.denominator.name
                kind = "ratio"
            count = denominator
            if not count and input_measure and measures[input_measure.name].agg.value == "count":
                count = item.name
            objects[ref(item.name)] = SemanticObject(ref=ref(item.name), kind="measure", data_type="number",
                title=raw.get("label") or item.name.replace("_", " "), description=raw.get("description"),
                metric_kind=kind,
                ratio_parts=(ref(numerator), ref(denominator)) if numerator and denominator else None,
                count_measure=ref(count) if count else None, dimension_refs=sorted(set(dimensions)),
                time_dimension=dim_ref("metric_time") if dim_ref("metric_time") in dimensions else None,
                metadata={"native_name": item.name})
        return SemanticCatalog(provider="metricflow", instance=self.instance, objects=list(objects.values()))

    def compile(self, spec: DatasetSpec):
        from metricflow.engine.metricflow_engine import MetricFlowQueryRequest
        if spec.grain != "aggregate":
            raise CapabilityMissing("This MetricFlow gateway supports aggregate queries. Entity-grain analysis is unavailable.")
        if not spec.measures:
            raise CapabilityMissing("MetricFlow dimension queries require at least one metric.")
        selected = [*spec.measures, *spec.dimensions, *([spec.time.dimension] if spec.time else [])]
        refs = [*selected, *(f.member for f in spec.filters), *(r for r, _ in spec.order)]
        objs = {ref: self.catalog.get(ref) for ref in refs}
        if any(o is None for o in objs.values()):
            raise InvalidDatasetSpec("A requested object does not belong to this MetricFlow catalog.")
        if any(objs[r].kind != "measure" for r in spec.measures) or any(objs[r].kind != "dimension" for r in spec.dimensions):
            raise InvalidDatasetSpec("Bind metrics and categorical dimensions to their declared roles.")
        metrics = [objs[r].metadata["native_name"] for r in spec.measures]
        group = [objs[r].metadata["native_name"] for r in spec.dimensions]
        columns = [Column(ref=r, role="dimension", data_type=objs[r].data_type) for r in spec.dimensions]
        if spec.time:
            if objs[spec.time.dimension].kind != "time_dimension":
                raise InvalidDatasetSpec("The date basis must be a time dimension.")
            if spec.time.dimension != f"metricflow://{self.instance}/dimensions/metric_time":
                raise CapabilityMissing("Use the metric's declared metric_time date basis on this gateway.")
            if spec.time.granularity:
                group.append("metric_time__" + spec.time.granularity)
                columns.append(Column(ref=spec.time.dimension, role="time", data_type="time", granularity=spec.time.granularity))
        allowed = set.intersection(*(set(objs[r].dimension_refs) for r in spec.measures))
        if any(r not in allowed for r in spec.dimensions):
            raise CapabilityMissing("These dimensions cannot be queried with all selected metrics.")
        where = []
        for f in spec.filters:
            if objs[f.member].kind != "dimension" or f.member not in allowed:
                raise CapabilityMissing("Filters must use dimensions available to every selected metric.")
            name = objs[f.member].metadata["native_name"]
            field = "{{ Dimension('" + name + "') }}"
            if f.operator in ("set", "notSet"):
                where.append(field + (" is not null" if f.operator == "set" else " is null"))
            elif f.operator in ("equals", "notEquals"):
                where.append(field + (" in (" if f.operator == "equals" else " not in (") + ", ".join(_literal(v) for v in f.values) + ")")
            elif f.operator in ("gt", "gte", "lt", "lte") and len(f.values) == 1:
                where.append(field + {"gt": " > ", "gte": " >= ", "lt": " < ", "lte": " <= "}[f.operator] + _literal(f.values[0]))
            else:
                raise CapabilityMissing("This filter operator is not supported by the MetricFlow gateway.")
        keys = [*group, *metrics]
        columns.extend(Column(ref=r, role="measure", data_type="number") for r in spec.measures)
        order = []
        for r, direction in spec.order:
            name = objs[r].metadata["native_name"]
            if spec.time and r == spec.time.dimension and spec.time.granularity:
                name += "__" + spec.time.granularity
            if name not in keys:
                raise InvalidDatasetSpec("Order fields must be selected in the dataset.")
            order.append(("-" if direction == "desc" else "") + name)
        start = end = None
        if spec.time and spec.time.date_range:
            try:
                start, end = (datetime.fromisoformat(d) for d in spec.time.date_range)
            except ValueError as exc:
                raise InvalidDatasetSpec("Use ISO dates for the analysis period.") from exc
            end = datetime.combine(end.date(), daytime.max)
            if start > end:
                raise InvalidDatasetSpec("The start date must precede the end date.")
        if spec.limit_rows is not None and not 1 <= spec.limit_rows <= 50000:
            raise DatasetTooLarge("Choose a row limit between 1 and 50,000.")
        args = dict(metric_names=metrics, group_by_names=group, where_constraints=where or None,
                    order_by_names=order or None, limit=spec.limit_rows or 50001,
                    time_constraint_start=start, time_constraint_end=end)
        return MetricFlowQueryRequest.create(**args), columns, keys, args

    def execute(self, spec, with_sql):
        request, columns, keys, native = self.compile(spec)
        started = time.monotonic()
        with self.lock:
            result = self.engine.query(mf_request=request)
            sql = self.engine.explain(mf_request=request).sql_statement.without_descriptions.sql if with_sql else None
        frame = result.result_df
        if frame.row_count > 50000:
            raise DatasetTooLarge("The result exceeds 50,000 rows. Narrow the period or filters.")
        indices = [list(frame.column_names).index(k) for k in keys]
        rows = [[row[i].isoformat() if hasattr(row[i], "isoformat") else row[i] for i in indices] for row in frame.rows]
        native = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in native.items()}
        return Dataset(spec=spec, columns=columns, rows=rows, provenance=[QueryProvenance(
            provider="metricflow", instance=self.instance, native_query=native, compiled_sql=sql,
            rows=len(rows), elapsed_ms=round((time.monotonic()-started)*1000))])


class QueryInput(BaseModel):
    spec: DatasetSpec
    with_sql: bool = False


def create_gateway():
    token = os.environ.get("DL_METRICFLOW_TOKEN")
    anonymous = os.environ.get("DL_METRICFLOW_ALLOW_ANONYMOUS") == "true"
    if not token and not anonymous:
        raise RuntimeError("Set DL_METRICFLOW_TOKEN, or explicitly enable anonymous local development.")

    def authorize(authorization: str | None = Header(default=None)):
        if token and not hmac.compare_digest(authorization or "", "Bearer " + token):
            from fastapi import HTTPException
            raise HTTPException(401, "A valid gateway token is required.")

    @asynccontextmanager
    async def lifespan(app):
        app.state.runtime = MetricFlowRuntime(os.environ.get("DL_METRICFLOW_INSTANCE", "local"))
        yield
        app.state.runtime.config.sql_client.close()

    app = FastAPI(title="Decision Layer MetricFlow gateway", lifespan=lifespan, dependencies=[Depends(authorize)])

    @app.exception_handler(DecisionLayerError)
    async def known_error(_request, exc):
        return JSONResponse(status_code=exc.http_status, content={"error": exc.to_dict()})

    @app.get("/catalog")
    def catalog():
        return app.state.runtime.catalog

    @app.get("/capabilities")
    def provider_capabilities():
        return capabilities()

    @app.post("/datasets/validate")
    def validate(spec: DatasetSpec):
        app.state.runtime.compile(spec)
        return {"valid": True}

    @app.post("/datasets/query")
    def query(value: QueryInput):
        return app.state.runtime.execute(value.spec, value.with_sql)

    return app
