"""Semantic HTTP routes; analytical work stays in the canonical engine."""
from __future__ import annotations
from typing import Annotated
from fastapi import Query
from fastapi.responses import JSONResponse
from ..core.models import Column, Dataset, DatasetSpec, PlanStep, SemanticCatalog, SemanticObject
from fastapi import APIRouter
from .dependencies import Caller, Creds, PREVIEW_ROWS

def create_router(provider, engine):
    router = APIRouter()
    @router.get("/semantic/catalog", response_model=SemanticCatalog)
    async def catalog(creds: Creds, include_private: bool = False) -> SemanticCatalog:
        cat = await provider.discover(creds)
        if include_private:
            return cat
        return cat.model_copy(update={"objects": [o for o in cat.objects if o.public]})

    @router.get("/semantic/objects", response_model=list[SemanticObject])
    async def objects(creds: Creds, ref: Annotated[list[str], Query()]) -> list[SemanticObject]:
        return await provider.resolve(ref, creds)

    @router.post("/datasets/preview", response_model=Dataset)
    async def preview(spec: DatasetSpec, creds: Creds, caller: Caller, with_sql: bool = False) -> Dataset:
        """Compatibility endpoint: validated, bounded and recorded aggregate preview."""
        from ..methods import InvalidBinding
        await provider.validate_dataset(spec, creds)
        if spec.grain != "aggregate" or not spec.measures:
            raise InvalidBinding("Aggregate previews require a metric. Use a registered Method for entity data.")
        if len(spec.order) > 1 or any(ref not in spec.measures for ref, direction in spec.order):
            raise InvalidBinding("Preview supports ordering by one selected metric.")
        params = {"limit": min(spec.limit_rows or PREVIEW_ROWS, PREVIEW_ROWS), "with_sql": with_sql}
        if spec.order:
            params.update(order_by=spec.order[0][0], direction=spec.order[0][1])
        if spec.time and spec.time.granularity:
            params["granularity"] = spec.time.granularity
        run, result = await engine.adhoc(creds, caller, PlanStep(method="query.aggregate",
            bindings={"metric": spec.measures[0], "related_metrics": spec.measures[1:], "dimensions": spec.dimensions}, params=params),
            scope={"date_range": spec.time.date_range if spec.time else None,
                   "time_dimension": spec.time.dimension if spec.time else None,
                   "filters": [item.model_dump(mode="json") for item in spec.filters]}, preview=True)
        if run.needs_input:
            return JSONResponse(status_code=422, content={"error": {"code": "PERIOD_REQUIRED", "message": run.needs_input["question"], "details": {"run_id": run.id}}})
        if not result or result.status != "success":
            raise InvalidBinding("Preview could not execute.", run_id=run.id)
        columns = [Column.model_validate(item) for item in result.artifacts[0].data["columns"]]
        return Dataset(spec=run.query_attempts[-1].spec, columns=columns,
            rows=[[row[column.ref] for column in columns] for row in result.primary.data],
            provenance=result.provenance.queries)

    return router
