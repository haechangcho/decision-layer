"""Format current Method authoring surfaces."""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "src/decision_layer/starters",
    "src/decision_layer/methods/formatting.py",
    "src/decision_layer/methods/python.py",
    "src/decision_layer/methods/function",
    "examples/methods/authoring/plain_python.py",
    "examples/recipes/skill_chain.py",
    "docs/tutorials/methods/write_your_method.ko.ipynb",
    "docs/tutorials/methods/write_your_method.en.ipynb",
    "tests/support/methods",
    "scripts/format_methods.py",
    "examples/methods/project/methods/rank/method.py",
    "examples/methods/project/methods/ols/method.py",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    command = [sys.executable, "-m", "ruff", "format"]
    if args.check:
        command.append("--check")
    return subprocess.call([*command, *FILES], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
