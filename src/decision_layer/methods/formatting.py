"""Format Python text without importing or executing the supplied module."""

import ast
from pathlib import Path
import subprocess
import sys

from .assets import AssetError

STYLE = Path(__file__).with_name("python-style.toml")


def format_python(content: str) -> str:
    if len(content.encode()) > 150_000:
        raise AssetError("Source exceeds the 150 KB limit")
    try:
        before = ast.parse(content, type_comments=True)
    except (SyntaxError, ValueError) as exc:
        raise AssetError(
            f"Python syntax error at line {getattr(exc, 'lineno', '?')}: {getattr(exc, 'msg', str(exc))}"
        ) from exc
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--config",
                str(STYLE),
                "--stdin-filename",
                "method.py",
                "-",
            ],
            input=content,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        formatted = result.stdout
        if ast.dump(before) != ast.dump(ast.parse(formatted, type_comments=True)):
            raise AssetError("Formatting would change the Python syntax tree")
        return formatted
    except (OSError, subprocess.SubprocessError, SyntaxError) as exc:
        raise AssetError(
            "Python formatter failed; the original code is unchanged"
        ) from exc
