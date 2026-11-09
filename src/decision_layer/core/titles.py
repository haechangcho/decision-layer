"""Short display metadata, separate from the original analytical question."""

from typing import Annotated

from pydantic import BeforeValidator, Field
from ..i18n import _


def single_line(value):
    return " ".join(value.split()) if isinstance(value, str) else value


RunTitle = Annotated[
    str, BeforeValidator(single_line), Field(min_length=1, max_length=80)
]


def fallback_title(text: str) -> str:
    """Bound older/client-less labels; semantic summarization belongs to the MCP client."""
    text = single_line(text) or _("Analysis result")
    return text if len(text) <= 80 else text[:79].rstrip() + "…"
