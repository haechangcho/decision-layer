"""Error types. Decision Layer fails closed (ADR-020): these carry a stable code so
API, MCP and Web can show the same reason."""
from __future__ import annotations

from typing import Any


class DecisionLayerError(Exception):
    code = "DECISION_LAYER_ERROR"
    http_status = 500

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class InvalidReference(DecisionLayerError):
    code = "INVALID_REFERENCE"
    http_status = 400


class UnknownSemanticObject(DecisionLayerError):
    """The ref is well formed but the provider doesn't expose it (or the caller can't see it)."""
    code = "UNKNOWN_SEMANTIC_OBJECT"
    http_status = 404


class InvalidDatasetSpec(DecisionLayerError):
    code = "INVALID_DATASET_SPEC"
    http_status = 400


class CapabilityMissing(DecisionLayerError):
    code = "CAPABILITY_MISSING"
    http_status = 422


class ProviderAccessDenied(DecisionLayerError):
    code = "PROVIDER_ACCESS_DENIED"
    http_status = 403


class ProviderError(DecisionLayerError):
    code = "PROVIDER_ERROR"
    http_status = 502


class DatasetTooLarge(DecisionLayerError):
    code = "DATASET_TOO_LARGE"
    http_status = 422
