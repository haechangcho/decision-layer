# Documentation

| Goal | Guide |
| --- | --- |
| Try the complete sample | [Chinook](../examples/chinook/README.md) · [한국어](../examples/chinook/README.ko.md) |
| Connect an existing semantic source | [Cube connection](guides/cube.md) |
| Connect Claude or Codex | [MCP setup and first analysis](guides/mcp.md) |
| Modify the API or Web | [Local development](guides/development.md) |
| Verify a change | [Testing](guides/testing.md) |
| Contribute an analytical capability | [Add a Method](guides/methods.md) |
| Submit a change | [Contributing](../CONTRIBUTING.md) |

## Understand the system

- [Product context](PRODUCT_CONTEXT.md): users, goals and boundaries.
- [Architecture](ARCHITECTURE.md): contracts, canonical execution and storage.
- [Decisions](DECISIONS.md): accepted decisions and implementation limits.

## Datasets

- [Chinook](../examples/chinook/README.md): small multi-table music store, source integrity and grain checks. Recommended first environment.
- [Online Retail II](../examples/online-retail/README.md): larger real transaction data and an [evaluation protocol](../examples/online-retail/evals/PROTOCOL.md).
- [Synthetic ecommerce](../examples/ecommerce/README.md): planted effects and deterministic analytical checks.

These are separate environments, not services to start together. Use different host ports if running more than one. Public regression cases are not blind benchmarks or proof of improved AI accuracy.
