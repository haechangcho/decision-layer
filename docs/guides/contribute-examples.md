# Three useful first contributions

You can contribute without adding a statistical algorithm. Pick one task and
include reproducible evidence. These are scoped proposals, not published issues.

## 1. Explain an ambiguous selection

**Problem:** the quickstart's March leaders tie. A user should understand what input
is needed and why no regional branch was queried.

**Scope:** improve the existing needs-input explanation and its example. Keep the
canonical selection and refusal rules unchanged.

**Acceptance:** demonstrate the March Run, show both candidates, explain how to
choose one, and cover the behavior with an appropriate UI or engine test. Include
English and Korean text if changing the UI.

## 2. Contribute a reusable analysis example

**Problem:** a second domain would help contributors understand Recipe portability.

**Scope:** supply small synthetic/public data, a provider-owned semantic model and
a Recipe using existing Methods. Do not put metric SQL into the Recipe.

**Acceptance:** document provenance/license, independently expected results, two
execution scopes and at least one failure case. Use the normal engine, and make
clear which bindings are specific to your model. No new package manager or runtime.

## 3. Test first-run installation on another platform

**Problem:** a working maintainer machine does not establish a reliable onboarding experience.

**Scope:** run `bash scripts/demo.sh` from a fresh clone on Linux or Windows WSL2
with Docker Compose v2. Report exact prerequisites and timings.

**Acceptance:** all three expected outcomes, working Web links, successful stop and
repeat execution. Report version, cold versus cached build, and sanitized errors.
Never attach credentials or unrelated local configuration.

See [Contributing](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md)
for implementation ownership and required checks.
