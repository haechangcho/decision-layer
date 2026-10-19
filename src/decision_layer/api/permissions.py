"""Operator permissions shared by Method and Recipe resource routes."""

from ..core.errors import DecisionLayerError
from ..core.models import CallerInfo
from ..settings import Settings


def _is_local_operator(settings: Settings, caller: CallerInfo) -> bool:
    return (
        settings.allow_service_credentials
        and caller.authentication == "local_service"
        and caller.subject in ("service:decision-layer", "service:local-development")
    )


class SourceAdminRequired(DecisionLayerError):
    code = "SOURCE_ADMIN_REQUIRED"
    http_status = 403


class RecipePermissionRequired(DecisionLayerError):
    code = "RECIPE_PERMISSION_REQUIRED"
    http_status = 403


def require_recipe_permission(
    settings: Settings, caller: CallerInfo, *, publish: bool = False
) -> None:
    # Explicit local service access belongs to the person operating this runtime.
    # It is never a multi-user identity; shared mode is rejected at startup.
    local_owner = _is_local_operator(settings, caller)
    subjects = (
        settings.recipe_publishers
        if publish
        else (*settings.recipe_editors, *settings.recipe_publishers)
    )
    if not local_owner and caller.subject not in subjects:
        raise RecipePermissionRequired(
            "Recipe publication requires publisher permission."
            if publish
            else "Recipe changes require editor permission."
        )


class MethodPermissionRequired(DecisionLayerError):
    code = "METHOD_PERMISSION_REQUIRED"
    http_status = 403


def require_method_permission(
    settings: Settings, caller: CallerInfo, *, publish: bool = False
):
    local_owner = _is_local_operator(settings, caller)
    subjects = (
        settings.method_publishers
        if publish
        else (*settings.method_editors, *settings.method_publishers)
    )
    if not local_owner and caller.subject not in subjects:
        raise MethodPermissionRequired(
            "Method publication and Python import checks require a Method publisher."
            if publish
            else "Method drafts require a Method editor."
        )
