"""Recipes HTTP routes; analytical work stays in the canonical engine."""
from __future__ import annotations
import yaml
from fastapi import Query, Request
from fastapi.responses import JSONResponse, Response
from ..i18n import _
from ..core.models import Recipe, Run
from ..methods import registry
from ..recipes.loader import parse_recipe
from ..service import RecipeSearchRequest, RecipeConfigureRequest, RecipePreviewRequest, RecipePublishRequest, RecipeSaveRequest, RecipeYamlRequest
from ..i18n import _
from fastapi import APIRouter
from .dependencies import Caller, Creds, run_origin, waited

from ..recipes.authoring import check_recipe_semantics

def create_router(settings, provider, recipes, engine):
    router = APIRouter()
    @router.get("/recipes", response_model=list[Recipe])
    async def recipes_list(_caller: Caller) -> list[Recipe]:
        return recipes.list()

    @router.post("/recipes:search")
    async def recipe_search(req: RecipeSearchRequest, creds: Creds, caller: Caller):
        from ..recipes.routing import search_recipes
        return await search_recipes(recipes, provider, creds, req.question, req.goals, req.inputs, req.limit)

    @router.get("/recipes:drafts", response_model=list[Recipe])
    async def recipe_drafts(_caller: Caller) -> list[Recipe]:
        return recipes.list_drafts()

    @router.post("/recipes:configure-step", response_model=Recipe)
    async def configure_recipe_step(req: RecipeConfigureRequest, caller: Caller, creds: Creds):
        from ..recipes.configuration import configure_step
        from ..recipes.authoring import RecipeEditError
        try:
            catalog = None
            if 0 <= req.step_index < len(req.recipe.steps):
                manifest = registry.get(req.recipe.steps[req.step_index].method).manifest
                if any(role.default_binding == "unit_count" for role in manifest.roles.values()):
                    catalog = await provider.discover(creds)
            recipe = configure_step(req.recipe, req.step_index, req.reset_parameters, catalog=catalog)
            for spec in recipe.inputs.values():
                spec.label = _(spec.label)
            return recipe
        except (ValueError, KeyError) as exc:
            raise RecipeEditError(str(exc), field="steps") from exc

    @router.post("/recipes:format")
    async def recipe_format(recipe: Recipe, _caller: Caller) -> dict[str, str]:
        recipes.validate(recipe)
        return {"yaml": yaml.safe_dump(recipe.model_dump(mode="json"), allow_unicode=True, sort_keys=False)}

    @router.post("/recipes:parse", response_model=Recipe)
    async def recipe_parse(req: RecipeYamlRequest, _caller: Caller) -> Recipe:
        from ..recipes.authoring import RecipeEditError

        try:
            document = yaml.safe_load(req.yaml)
            if not isinstance(document, dict):
                raise RecipeEditError(_("Recipe YAML must be a mapping."))
            parsed = parse_recipe(document, provider.name, provider.instance)
        except yaml.YAMLError as error:
            raise RecipeEditError(_("Recipe YAML syntax is invalid: {error}", error=error)) from error
        except ValueError as error:
            raise RecipeEditError(_("Recipe YAML structure is invalid: {error}", error=error)) from error
        recipes.validate(parsed)
        return parsed

    @router.post("/recipes:validate")
    async def recipe_validate(recipe: Recipe, _caller: Caller, creds: Creds, live: bool = False) -> dict[str, bool]:
        """Validate the shared static contract and, optionally, caller-visible semantic references."""
        recipes.validate(recipe)
        if live:
            await check_recipe_semantics(recipe, provider, creds)
        return {"valid": True, "semantic_checked": live}

    @router.post("/recipes:preview", response_model=Run, responses={202: {"description": "preview still running"}})
    async def recipe_preview(req: RecipePreviewRequest, creds: Creds, caller: Caller, request: Request, wait: float | None = None):
        """Execute an unsaved pipeline prefix with normal validation, access and query limits."""
        recipes.validate(req.recipe)
        run = await engine.preview(creds, caller, req.recipe, req.step_index, req.scope.as_dict(), wait=waited(settings, wait), origin=run_origin(request))
        return JSONResponse(status_code=202, content=run.model_dump(mode="json")) if run.running else run

    @router.get("/recipes/{name}/edit", response_model=Recipe)
    async def recipe_edit(name: str, _caller: Caller) -> Recipe:
        return recipes.get(name, include_drafts=True)

    @router.post("/recipes/{name}/publish", response_model=Recipe)
    async def recipe_publish(name: str, req: RecipePublishRequest, _caller: Caller, creds: Creds) -> Recipe:
        draft = recipes.get(name, req.base_version, include_drafts=True)
        recipes.validate(draft)
        await check_recipe_semantics(draft, provider, creds)
        return recipes.publish(name, req.base_version)

    @router.get("/recipes/{name}", response_model=Recipe)
    async def recipe_get(name: str, _caller: Caller) -> Recipe:
        return recipes.get(name)

    @router.put("/recipes/{name}", response_model=Recipe)
    async def recipe_save(name: str, req: RecipeSaveRequest, _caller: Caller) -> Recipe:
        from ..recipes.authoring import RecipeEditError

        if req.recipe.name != name:
            raise RecipeEditError("Recipe name must match the URL.")
        return recipes.save(req.recipe, req.base_version)

    @router.delete("/recipes/{name}", status_code=204)
    async def recipe_delete(name: str, _caller: Caller, base_version: str = Query(...)) -> Response:
        recipes.delete(name, base_version)
        return Response(status_code=204)

    return router
