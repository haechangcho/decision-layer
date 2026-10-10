# Contributing

Contributions to Methods, Recipe examples, documentation and usability are welcome. Small fixes can go straight to a pull request. For a new Method or a change to execution contracts, open an issue to discuss the analytical question and scope first.

## First contribution

For a Method, Python 3.11+ is sufficient:

```bash
make setup
make example
```

Edit `examples/methods/first_method/method.py`, rerun its test and read
[the Method guide](docs/guides/methods.md). For three-query combination, run
`.venv/bin/python -m pytest -q examples/methods/peer_comparison`.

Use [local development](docs/guides/development.md) for Web/API changes and
[the sample](examples/complete-journey/README.md) only when live data is needed.
Run focused tests first, then `make test`. [Testing](docs/guides/testing.md) lists
Web, documentation and live checks.

## Choose the right contribution

| Change | Start here |
| --- | --- |
| New analytical capability | [Method contribution guide](docs/guides/methods.md) |
| Procedure using existing Methods | [Recipe contribution guide](docs/guides/methods.md#recipes) and Recipe editor |
| Web interaction or presentation | `web/app/`, `web/features/`, `web/components/` and `web/tests/product/` |
| Provider or execution contract | [Architecture](docs/ARCHITECTURE.md) and [ADRs](docs/DECISIONS.md) |
| Setup or documentation | The relevant task guide under `docs/guides/` |

Read [AGENTS.md](AGENTS.md) before changing product or architecture behavior. The semantic layer owns definitions, joins, grain and permissions; Decision Layer owns analytical procedures and their evidence. All interfaces must use the same engine.

## Pull requests

- Explain the user problem and behavior change. Include screenshots for UI changes.
- Add focused tests and list the commands you ran. Distinguish mocked checks from live integration and AI-client evaluation.
- Keep changes scoped. Update guides when commands or behavior change; record architectural decisions in `docs/DECISIONS.md`.
- Use synthetic or public data with documented source, permission and version. Do not commit tokens, private models, customer results, local databases or infrastructure notes.

Methods are reviewed Python code shipped with the server, not scripts uploaded by users. Recipe drafts require review before publication; neither a draft nor a client-origin label proves approval.

## Bug reports

Include the command or user journey, expected and actual behavior, versions and sanitized logs. For analytical issues, include the Method, semantic grain, expected result and a public or synthetic reproducer. Never attach access tokens or private data.
