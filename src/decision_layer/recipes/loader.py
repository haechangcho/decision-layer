"""Recipes are versioned YAML files (ADR-025), refreshed from their file source.

Recipe authors write semantic refs short — `orders.total_amount` — and the
loader expands them to canonical refs for the configured provider instance.
Step values that start with `$` are expressions resolved at run time (see
runs/expressions.py) and are left untouched here.
"""
from __future__ import annotations

import re
import os
import fcntl
import tempfile
from threading import Lock
from pathlib import Path
from typing import Any

import yaml

from ..core.errors import DecisionLayerError
from ..core.ids import SemanticRef
from ..core.models import Recipe
from ..i18n import _

_SHORT_REF = re.compile(r"^[A-Za-z_][\w]*\.[A-Za-z_][\w]*$")


class UnknownRecipe(DecisionLayerError):
    code = "UNKNOWN_RECIPE"
    http_status = 404


class InvalidRecipe(DecisionLayerError):
    code = "INVALID_RECIPE"
    http_status = 500


def expand_ref(value: str, provider: str, instance: str) -> str:
    if _SHORT_REF.match(value):
        cube, member = value.split(".")
        return str(SemanticRef(provider=provider, instance=instance, cube=cube, member=member))
    return value


def _expand(value: Any, provider: str, instance: str, keys: set[str] | None = None) -> Any:
    """Expand short refs in strings (all strings when keys is None, else only under those keys)."""
    if isinstance(value, str):
        return expand_ref(value, provider, instance) if keys is None else value
    if isinstance(value, list):
        return [_expand(v, provider, instance, keys) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v, provider, instance, None if keys is None or k in keys else keys)
                for k, v in value.items()}
    return value


def parse_recipe(doc: dict[str, Any], provider: str, instance: str) -> Recipe:
    doc = dict(doc)
    doc["semantic_scope"] = _expand(doc.get("semantic_scope") or {}, provider, instance)
    if doc.get("default_scope"):
        doc["default_scope"] = _expand(doc["default_scope"], provider, instance, keys={"time_dimension"})
    steps = []
    for step in doc.get("steps") or []:
        step = dict(step)
        step["bindings"] = _expand(step.get("bindings") or {}, provider, instance)
        # in params only refs under these keys are semantic (drill_path members, factor lists, …)
        step["params"] = _expand(step.get("params") or {}, provider, instance,
                                 keys={"member", "factors", "next_dimension", "conditions", "treatment"})
        steps.append(step)
    doc["steps"] = steps
    return Recipe.model_validate(doc)


class RecipeStore:
    def __init__(self, directory: str | Path | None, provider: str, instance: str) -> None:
        self._writable = bool(directory)
        self._lock = Lock()
        self.directory = Path(directory) if directory else Path("/nonexistent")
        self.provider = provider
        self.instance = instance
        self._recipes: dict[str, dict[str, Recipe]] = {}
        self.reload()

    def _read_all(self) -> dict[str, dict[str, Recipe]]:
        found: dict[str, dict[str, Recipe]] = {}
        for path in sorted(self.directory.rglob("*.y*ml")) if self.directory.exists() else []:
            try:
                recipe = parse_recipe(yaml.safe_load(path.read_text()), self.provider, self.instance)
                from .authoring import validate_recipe

                validate_recipe(recipe)
            except DecisionLayerError as e:
                raise InvalidRecipe(
                    _("Can't read recipe file {file}: {error}", file=path.name, error=e.message),
                    path=str(path), field=e.details.get("field"),
                ) from e
            except Exception as e:  # a broken recipe must not be silently skipped
                raise InvalidRecipe(_("Can't read recipe file {file}: {error}", file=path.name, error=e), path=str(path)) from e
            found.setdefault(recipe.name, {})[recipe.version] = recipe
        return found

    def reload(self) -> None:
        """Refresh the in-memory index so file edits are visible without an API restart."""
        found = self._read_all()
        with self._lock:
            self._recipes = found

    def list(self) -> list[Recipe]:
        self.reload()
        return [recipe for name in sorted(self._recipes)
                if (recipe := self._latest_published(name)) is not None]

    def list_drafts(self) -> list[Recipe]:
        self.reload()
        return [recipe for name in sorted(self._recipes)
                if (recipe := self._latest(name)).status == "draft"]

    @staticmethod
    def validate(recipe: Recipe) -> None:
        """Apply the same static contract to file, API, and Web-authored Recipes."""
        from .authoring import validate_recipe

        validate_recipe(recipe)

    def save(self, recipe: Recipe, base_version: str | None) -> Recipe:
        from .authoring import RecipeConflict, RecipeEditError

        self.validate(recipe)
        if not self._writable:
            raise RecipeEditError("Configure DL_RECIPES_DIR to save Recipes.")
        self.directory.mkdir(parents=True, exist_ok=True)
        with self._lock, (self.directory / ".decision-layer.lock").open("w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            self._recipes = self._read_all()
            latest = self._latest(recipe.name) if recipe.name in self._recipes else None
            if (latest.version if latest else None) != base_version:
                raise RecipeConflict("Recipe changed. Reload the latest version before saving.")
            if latest and tuple(map(int, recipe.version.split('.'))) <= tuple(map(int, latest.version.split('.'))):
                raise RecipeConflict("Save a new version; existing Recipe versions are immutable.")
            self._write_version(recipe)
            self._recipes.setdefault(recipe.name, {})[recipe.version] = recipe.model_copy(deep=True)
            return recipe

    def publish(self, name: str, base_version: str) -> Recipe:
        from .authoring import RecipeConflict, RecipeEditError

        if not self._writable:
            raise RecipeEditError(_("Configure DL_RECIPES_DIR to publish Recipes."))
        with self._lock, (self.directory / ".decision-layer.lock").open("w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            self._recipes = self._read_all()
            latest = self._latest(name) if name in self._recipes else None
            if latest is None or latest.version != base_version or latest.status != "draft":
                raise RecipeConflict(_("The draft changed or was already published. Reload before publishing."))
            major, minor, patch = (int(part) for part in latest.version.split("."))
            published = latest.model_copy(update={"version": f"{major}.{minor}.{patch + 1}", "status": "published"})
            self.validate(published)
            self._write_version(published)
            self._recipes[name][published.version] = published.model_copy(deep=True)
            return published

    def delete(self, name: str, base_version: str) -> None:
        from .authoring import RecipeConflict, RecipeEditError

        if not self._writable:
            raise RecipeEditError("Configure DL_RECIPES_DIR to delete Recipes.")
        if not self.directory.exists():
            raise UnknownRecipe(_("Unknown recipe: {name}", name=name))
        with self._lock, (self.directory / ".decision-layer.lock").open("w") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            self._recipes = self._read_all()
            if name not in self._recipes:
                raise UnknownRecipe(_("Unknown recipe: {name}", name=name))
            if self._latest(name).version != base_version:
                raise RecipeConflict("Recipe changed. Reload the latest version before deleting.")
            paths = [path for path in self.directory.rglob("*.y*ml")
                     if parse_recipe(yaml.safe_load(path.read_text()), self.provider, self.instance).name == name]
            for path in paths:
                path.unlink()
            del self._recipes[name]

    def _write_version(self, recipe: Recipe) -> None:
        from .authoring import RecipeConflict

        target = self.directory / f"{recipe.name}@{recipe.version}.yaml"
        with tempfile.NamedTemporaryFile(mode="w", dir=self.directory, suffix=".tmp", delete=False) as f:
            temporary = Path(f.name)
            try:
                f.write(yaml.safe_dump(recipe.model_dump(mode="json"), allow_unicode=True, sort_keys=False))
                f.flush()
                os.fsync(f.fileno())
                os.link(temporary, target)
            except FileExistsError:
                raise RecipeConflict("This Recipe version already exists. Reload before saving.") from None
            finally:
                temporary.unlink(missing_ok=True)

    def get(self, name: str, version: str | None = None, *, include_drafts: bool = False) -> Recipe:
        self.reload()
        name = name.removeprefix("recipe://")
        if "@" in name:
            name, version = name.split("@", 1)
        versions = self._recipes.get(name)
        if not versions:
            raise UnknownRecipe(_("Unknown recipe: {name}", name=name), available=sorted(self._recipes))
        if version is None:
            selected = self._latest(name) if include_drafts else self._latest_published(name)
            if selected is None:
                raise UnknownRecipe(_("Unknown recipe: {name}", name=name), available=sorted(self._recipes))
            return selected
        if version not in versions:
            raise UnknownRecipe(_("{name} has no version {version}", name=name, version=version), versions=sorted(versions))
        recipe = versions[version]
        if recipe.status == "draft" and not include_drafts:
            raise UnknownRecipe(_("{name} has no version {version}", name=name, version=version), versions=sorted(versions))
        return recipe

    def _latest(self, name: str) -> Recipe:
        versions = self._recipes[name]
        version = max(versions, key=lambda v: tuple(int(x) for x in v.split(".")))
        return versions[version]

    def _latest_published(self, name: str) -> Recipe | None:
        versions = [recipe for recipe in self._recipes[name].values() if recipe.status == "published"]
        return max(versions, key=lambda recipe: tuple(int(x) for x in recipe.version.split("."))) if versions else None
