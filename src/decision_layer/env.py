"""Environment variables, with the names used before the rename to Decision Layer.

DL_* is current. The pre-rename ANALYTICA_* names are still read for one release, with a
warning, so existing deployments keep working while they update their configuration.
"""
from __future__ import annotations

import logging
import os

_RENAMED = {"DL_API_URL": "ANALYTICA_URL", "DL_TOKEN": "ANALYTICA_TOKEN"}
_warned: set[str] = set()
log = logging.getLogger("decision_layer")


def env(name: str, default: str | None = None) -> str | None:
    if name in os.environ:
        return os.environ[name]
    old = _RENAMED.get(name) or ("ANALYTICA_" + name[3:] if name.startswith("DL_") else None)
    if old and old in os.environ:
        if old not in _warned:
            _warned.add(old)
            log.warning("%s is deprecated; use %s", old, name)
        return os.environ[old]
    return default
