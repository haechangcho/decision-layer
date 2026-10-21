"""Repository entry point for the shared installed demo asset."""

from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(
        str(
            Path(__file__).resolve().parents[2]
            / "src/decision_layer/demo/assets/journey/verify.py"
        ),
        run_name="__main__",
    )
