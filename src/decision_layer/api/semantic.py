"""Semantic HTTP routes; analytical work stays in the canonical engine."""
from __future__ import annotations
from typing import Annotated
from fastapi import Query
from ..core.models import SemanticCatalog, SemanticObject
from fastapi import APIRouter
from .dependencies import Creds

def create_router(provider):
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

    return router
