"""Build immutable PoC images from committed poc/deployment sources only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import tempfile

BRANCH = "poc/deployment"
ROOT = Path(__file__).resolve().parents[2]


def git(source: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=("heartcube", "decision-layer"))
    parser.add_argument("--source", type=Path, help="Override the component source repository")
    parser.add_argument("--plan", action="store_true", help="Validate sources and print the build without using Docker")
    args = parser.parse_args()
    source = (args.source or (ROOT.parent / "heartcube" if args.component == "heartcube" else ROOT)).resolve()
    try:
        branch = git(source, "branch", "--show-current")
        if branch != BRANCH:
            parser.error(f"{source}: switch to {BRANCH}; current branch is {branch or 'detached HEAD'}")
        if git(source, "status", "--porcelain", "--untracked-files=no"):
            parser.error(f"{source}: commit tracked changes before building. Ignored/untracked files are excluded by git archive.")
        revision = git(source, "rev-parse", "HEAD")
        short = git(source, "rev-parse", "--short=7", "HEAD")
        image = f"{args.component}:poc-{short}"
        dockerfile = "Dockerfile" if args.component == "heartcube" else "deploy/poc/Dockerfile.decision-layer"
        git(source, "cat-file", "-e", f"{revision}:{dockerfile}")
        build_arg = f"IMAGE_VERSION=poc-{short}" if args.component == "heartcube" else f"VCS_REF={revision}"

        def command(context):
            return ["docker", "buildx", "build", "--platform", "linux/amd64", "--load",
                    "--build-arg", build_arg,
                    "--label", f"org.opencontainers.image.revision={revision}",
                    "--label", f"io.decision-layer.poc.branch={BRANCH}",
                    "-t", image, "-f", str(Path(context) / dockerfile), str(context)]

        if args.plan:
            print(json.dumps({"source": str(source), "branch": branch, "commit": revision,
                              "image": image, "command": shlex.join(command("<committed-source>"))}, indent=2))
            return
        subprocess.run(["docker", "info", "--format", "{{.OSType}}"], check=True, capture_output=True, text=True)
        exists = subprocess.run(["docker", "image", "inspect", image], capture_output=True, text=True)
        if exists.returncode == 0:
            parser.error(f"{image} already exists; reuse the verified image or commit a new revision. Tags are never overwritten.")
        with tempfile.TemporaryDirectory(prefix="poc-image-") as temp:
            context = Path(temp) / "source"
            context.mkdir()
            archive = Path(temp) / "source.tar"
            subprocess.run(["git", "-C", str(source), "archive", "--format=tar",
                            "--output", str(archive), revision], check=True)
            subprocess.run(["tar", "-xf", str(archive), "-C", str(context)], check=True)
            subprocess.run(command(context), check=True)
        info = json.loads(subprocess.check_output(["docker", "image", "inspect", image], text=True))[0]
        record = {"image": image, "branch": branch, "commit": revision, "source": str(source),
                  "image_id": info["Id"], "architecture": info["Architecture"],
                  "verified": False, "deployed": False}
        destination = ROOT / "deploy/poc/builds" / f"{args.component}-{short}.local.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps({**record, "record": str(destination)}, indent=2))
    except (OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Build failed: {exc}\n")


if __name__ == "__main__":
    main()
