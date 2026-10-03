# Contributing

Contributions to Methods, Recipe examples, documentation and usability are welcome. Small fixes can go straight to a pull request. For a new Method or a change to execution contracts, open an issue to discuss the analytical question and scope first.

## Development

1. Follow [local development](docs/guides/development.md) to install the API and Web.
2. Run the [test suite](docs/guides/testing.md). Unit and mocked browser tests do not need Cube.
3. Use the [Chinook sample](examples/chinook/README.md) for reproducible live integration checks.

## Choose the right contribution

| Change | Start here |
| --- | --- |
| New analytical capability | [Method contribution guide](docs/guides/methods.md) |
| Procedure using existing Methods | [Sample Recipe](examples/chinook/templates/music-sales.yaml) and Recipe editor |
| Web interaction or presentation | `web/app/`, `web/components/` and `web/tests/product/` |
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
