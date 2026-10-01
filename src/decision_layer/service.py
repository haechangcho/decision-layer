"""Request models shared by the REST API and the MCP server."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .core.models import Filter, Recipe


class ScopeIn(BaseModel):
    date_range: tuple[str, str] | None = None
    time_dimension: str | None = None
    filters: list[Filter] = Field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class MethodRunRequest(BaseModel):
    bindings: dict[str, str | list[str]] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    scope: ScopeIn = Field(default_factory=ScopeIn)


class RunStartRequest(BaseModel):
    recipe: str | None = None                      # name, name@version or recipe://name@version
    question: str | None = None
    scope: ScopeIn = Field(default_factory=ScopeIn)


class RecipeSaveRequest(BaseModel):
    recipe: Recipe
    base_version: str | None = None


class RunStepRequest(BaseModel):
    id: str | None = None
    method: str
    bindings: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class RunCompleteRequest(BaseModel):
    summary: str | None = None


class RunShareRequest(BaseModel):
    subjects: list[str] = Field(default_factory=list)   # [] = private again
