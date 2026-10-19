"""Stable domain errors shared by Run lifecycle, policy and access checks."""

from ..core.errors import DecisionLayerError


class RunClosed(DecisionLayerError):
    code = "RUN_CLOSED"
    http_status = 409


class RunLimitExceeded(DecisionLayerError):
    code = "RUN_LIMIT_EXCEEDED"
    http_status = 422


class RunBusy(DecisionLayerError):
    code = "RUN_BUSY"
    http_status = 409


class MethodNotAllowed(DecisionLayerError):
    code = "METHOD_NOT_ALLOWED"
    http_status = 403


class PreviewStepInvalid(DecisionLayerError):
    code = "PREVIEW_STEP_INVALID"
    http_status = 422


class AnalysisContractError(DecisionLayerError):
    code = "ANALYSIS_CONTRACT_REQUIRED"
    http_status = 422


class ExecutionDeadlineExceeded(DecisionLayerError):
    code = "EXECUTION_TIMEOUT"
    http_status = 422
