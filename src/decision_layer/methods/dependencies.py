"""Dependency metadata preflight; never installs packages or imports heavy backends."""
from importlib.metadata import PackageNotFoundError, version
from packaging.specifiers import SpecifierSet
from ..i18n import _


def dependency_issue(requirements):
    for package, constraint in requirements.items():
        try:
            installed = version(package)
        except PackageNotFoundError:
            return _("Optional dependency {package}{constraint} is unavailable. Install the Method's documented extra before executing.", package=package, constraint=constraint)
        if installed not in SpecifierSet(constraint):
            return _("Optional dependency {package} has unsupported version {installed}; expected {constraint}.", package=package, installed=installed, constraint=constraint)
    return None


def runtime_versions(requirements):
    installed = {}
    for package in requirements:
        try:
            installed[package] = version(package)
        except PackageNotFoundError:
            pass  # Missing dependency is recorded as a refusal, never installed.
    return installed
