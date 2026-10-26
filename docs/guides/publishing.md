# Publishing the Python package

The Python distribution contains Method authoring tools, the admin Web UI and the
API. Release CI builds the shared React pages before packaging. A Cube server is
not bundled.

## First PyPI release

Sign in to PyPI and open https://pypi.org/manage/account/publishing/ . Add a pending
GitHub publisher with these values:

| Field | Value |
| --- | --- |
| PyPI project name | `decision-layer` |
| Owner | `haechangcho` |
| Repository | `decision-layer` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

This authorizes that repository's release workflow to publish this package. No
long-lived API token is required. Confirm the publisher registration with the
account owner before submitting it.

## Release

1. Update `project.version` in `pyproject.toml` and `decision_layer.__version__`
   together. Keep the release classification consistent with the version.
2. Run the tests and commit the intended release source and workflow to GitHub.
3. Publish a GitHub Release tagged `v<version>` against that tested commit. Mark
   alpha/beta/RC versions as prereleases. The tag must match the package version.
4. `publish.yml` builds wheel and sdist, checks their metadata, installs the wheel
   into a separate environment and runs `scripts/smoke_distribution.py`.
5. Only a successful build proceeds to the `pypi` environment and Trusted Publishing.
6. Verify the public installation from an empty directory:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install decision-layer
decision-layer init my_team
cd my_team
decision-layer new python rank
decision-layer check
decision-layer list
decision-layer serve --port 8010
```

When a package has only prereleases, pip can select one without `--pre`. Once a
stable release exists, ordinary pip prefers stable releases; preview testing can
request an explicit version or use `--pre`. Verify that the plain public install
resolves to the intended release before announcing it. Statistics and MCP are
base dependencies; release CI must install without extras.
PyPI files cannot be overwritten; a failed published artifact needs a new version.

References: [PyPA publishing guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/),
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/).
