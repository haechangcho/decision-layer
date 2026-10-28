"""Operator-owned plugins. Importing Python executes trusted code at startup."""
import importlib
from .base import Method
from .skills import load_skill_directory


def configured_registry(settings):
    from . import registry
    target = registry.copy()
    for module_name in settings.method_modules:
        module = importlib.import_module(module_name)
        if hasattr(module, "COMPATIBILITY_METHODS"):
            raise ValueError("Hidden Method registration is no longer supported. Export installed Methods in METHODS.")
        for method in module.METHODS:
            if not isinstance(method, Method):
                raise ValueError(f"{module_name}.METHODS must contain registered Methods")
            if method.manifest.name in target._methods:
                raise ValueError(f"Duplicate Method name: {method.manifest.name}")
            target.register(method)
    if settings.skills_dir:
        load_skill_directory(target, settings.skills_dir)
    from ..project import Project
    project = Project.find(settings.project_dir, required=bool(settings.project_dir))
    if project:
        project.load(target)
    return target
