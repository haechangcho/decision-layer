"""Message localisation. English is the source language; catalogs map an English
message id to a translation with the same {placeholders}.

    raise Refused(_("'{ref}' has no time dimension", ref=ref))

The active locale is per request (Accept-Language, else DL_LOCALE, else
en) and carries into background jobs through the context. Messages are rendered
when raised, so a stored run keeps the language it was executed in.
"""
from __future__ import annotations

import json
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

DEFAULT = "en"
_HERE = Path(__file__).parent
_locale: ContextVar[str] = ContextVar("decision_layer_locale", default=DEFAULT)


@lru_cache
def catalog(locale: str) -> dict[str, str]:
    path = _HERE / f"{locale}.json"
    return json.loads(path.read_text()) if path.exists() else {}


def available() -> list[str]:
    return [DEFAULT, *sorted(p.stem for p in _HERE.glob("*.json"))]


def negotiate(accept_language: str | None, default: str = DEFAULT) -> str:
    """First supported language in an Accept-Language header (quality order is the header's order)."""
    supported = set(available())
    for part in (accept_language or "").split(","):
        lang = part.split(";")[0].strip().lower().split("-")[0]
        if lang in supported:
            return lang
    return default if default in supported else DEFAULT


def set_locale(locale: str):
    return _locale.set(locale)


def get_locale() -> str:
    return _locale.get()


def _(msgid: str, **values) -> str:
    """Translate msgid into the active locale and fill its placeholders."""
    template = catalog(_locale.get()).get(msgid, msgid) if _locale.get() != DEFAULT else msgid
    return template.format(**values) if values else template
