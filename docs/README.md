# Documentation

[Read the documentation](https://decision-layer-docs.vercel.app/) · [한국어](https://decision-layer-docs.vercel.app/ko/)

Read these pages as a searchable documentation site from the repository root:

```bash
npm ci
npm run docs:dev
```

Open the URL shown by VitePress. `npm run docs:build` checks the static site and links. The documentation site is separate from the Decision Layer Web app and does not add a service to the sample Docker stack.

| Goal | Guide |
| --- | --- |
| Try the complete sample | [Complete Journey](../examples/complete-journey/README.md) · [한국어](../examples/complete-journey/README.ko.md) |
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

## Sample environment

- [Complete Journey](../examples/complete-journey/README.md): default multi-table retail example, campaigns and coupon usage. Observational, not causal ground truth.

The sample is isolated from production services. Public regression cases are not blind benchmarks or proof of improved AI accuracy; see the [evaluation protocol](guides/evaluation.md).
