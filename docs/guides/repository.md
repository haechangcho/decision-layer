# Repository structure

| Directory | What belongs here |
| --- | --- |
| `src/decision_layer/` | Installable Python product: contracts, execution, providers, API and MCP |
| `web/` | Admin console source; routes in `app/`, domain UI in `features/`, shared controls in `components/` |
| `docs/guides/`, `docs/ko/guides/` | English and Korean task guides |
| `docs/tutorials/` | Executable learning notebooks |
| `examples/` | Importable example code, complete projects and runnable demos |
| `tests/` | Unit, provider, integration and example checks; shared helpers in `support/` |
| `scripts/` | Repository setup, formatting and release checks |

## Where to make a change

- Write a team Method in your own project's `<name>/methods/<method>/method.py`.
  Use [the complete example](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/project)
  as a reference; team code does not belong in the product package.
- Put a learning walkthrough in `docs/tutorials/`, and reusable example functions or
  fixtures under `examples/`. Keep verification in `tests/examples/`.
- Put Method UI in `web/features/methods/`, Recipe UI in `web/features/recipes/` and
  Run UI in `web/features/runs/`. Route files compose these features.
- Change execution behavior in the shared Python engine, not separately in REST,
  Web or MCP. The [architecture map](../ARCHITECTURE.md) lists the owners.

`decision_layer.methods` is the public authoring API. `methods/catalog.py` assembles
built-ins, while `methods/compatibility.py` retains pinned historical versions.
Existing implementation module paths remain stable for workers and saved definitions.

## Generated files

`src/decision_layer/static/` contains the console build shipped in the Python package.
Edit `web/` and build it with `npm --prefix web run build:console`; do not edit the
compiled files. `.venv/`, `node_modules/`, `.next/` and VitePress build output are
local generated state. Project databases and managed assets live in `.decision-layer/`.

## Previous example paths

The former `examples/methods/patterns/` mixed tutorials, statistics and Recipe demos.
Its notebooks now live in `docs/tutorials/methods/`; its Python modules are grouped
under `examples/methods/authoring/`, `statistics/`, `scenarios/` and `examples/recipes/`.
Update local `DL_METHOD_MODULES` settings that pointed at those example modules.
Historical evidence retains the original paths used at execution time.

Product internals are split by responsibility: function compilation and calculation in
`methods/function/`, Run access/context/steps in `runs/`, HTTP permissions in `api/`,
MCP evidence projection in `mcp/presentation.py`, and Recipe controls in
`web/features/recipes/`. See [the execution boundaries](../ARCHITECTURE.md#internal-execution-boundaries-adr-111).
