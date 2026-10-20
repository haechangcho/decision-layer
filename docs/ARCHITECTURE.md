# Code structure

Use this page to find execution responsibilities and code locations. See [Development and tests](guides/development.md) for setup and commands.

## Responsibilities

| Area | Owns |
|---|---|
| Semantic layer | Metrics, dimensions, entities, joins, aggregation and access |
| Method | One calculation or analysis guidance for AI |
| Recipe | A reusable procedure using existing Methods and semantic references |
| Run | Executed inputs, versions, queries, validation and results |

Cube REST is the current product connection. Legacy dbt code remains for compatibility tests, not as a new connection option.

## Code map

| Location | Responsibility |
|---|---|
| `src/decision_layer/core/` | Shared models and identifiers |
| `methods/` | Registration, discovery, input checks and calculations |
| `methods/function/` | Ordinary-function registration, querying and execution |
| `recipes/` | Recipe files, input connections and procedure validation |
| `runs/` | Execution state, steps, policy, access and storage |
| `semantic/`, `sources/` | Cube adapter, catalog and connection settings |
| `api/`, `mcp/` | REST and MCP interfaces to the common execution model |
| `project.py`, `project_scaffold.py`, `cli.py`, `starters/` | Shared project loading, CLI and editable starter files |
| `console.py`, `demo/` | Installed admin console and sample launcher |
| `web/features/` | Method, Recipe and Run screens |
| `tests/`, `tests/support/` | Product checks and shared test data |
| `docs/tutorials/`, `examples/` | Learning notebooks and importable examples |

Python paths are relative to `src/decision_layer/`. `methods/catalog.py` assembles defaults; `methods/compatibility.py` retains older implementations.

## Shared execution path

```text
Web / REST / MCP
        ↓
RunEngine: state, inputs and policy
        ↓
MethodRegistry: registered version and input contract
        ↓
ExecutionContext: scope, access and query-attempt recording
        ↓
Cube: query data
        ↓
Method: calculate and validate
        ↓
Result → Run storage → Web and AI
```

`runs/engine.py` owns lifecycle and jobs, `runs/steps.py` individual steps, and `runs/context.py` query execution and recording. `runs/policy.py` and `runs/access.py` own limits and read authorization.

`MethodSession.run()` uses the Registry and Context directly for development. Calculation runs in the caller's Python process for debugging and does not create a server Run. Server Python calculations run in bounded child processes.

## Method registration and execution

Ordinary `Column` and `DataInput` declarations compile to the shared manifest and input contract. Web, REST and MCP consume that manifest; new Methods do not require separate screens or execution rules.

`methods/function/registration.py` compiles registration, `inputs.py` connects query columns to function inputs, and `execution.py` validates data and calls the function. Calculations receive no provider client or credentials.

Team projects contain `decision-layer.yaml`, `method.py` and `SKILL.md`. Python sessions, CLI and server startup share `project.py`. New projects generate two Skill files and two self-contained Python calculations with local tests. Their configuration disables built-in defaults; older projects retain the previous catalog. Package updates never rewrite user-owned definitions (ADR-116). Legacy module-loading settings remain supported.

External AI clients drive Skill execution. `runs/skills.py` validates structured Cube queries and records actual requests and results. The pipeline waits for querying and completion before continuing. Reading guidance alone is neither execution nor validation.

## Scope, validation and evidence

- Queries obey selected dates, shared filters, access and query budgets. All-period execution requires an explicit choice and policy permission.
- Each query attempt is recorded before execution. Failures and interruptions consume budget and remain visible.
- Entity queries validate provider-declared keys and uniqueness. Multiple queries do not guarantee the same warehouse snapshot.
- Successful querying does not establish analytical validity. Failed validation limits supported conclusions and capabilities. Association or assumption-dependent results do not establish causation.
- One MCP question records goals, steps and evidence in one Run. Arbitrary AI-generated Python or SQL is not an execution path.

## Versions and storage

Recipes are versioned YAML. A separate Run store retains execution-time Methods, Recipes, inputs, queries and results. Stores support memory, SQLite and PostgreSQL. Version changes do not rewrite historical evidence.

`methods/source.py` captures executed source and hashes. It does not archive every external dependency or dynamic import.

The optional Method editor uses `methods/assets.py` for drafts and immutable releases. It does not overwrite installed Git files or synchronize with Git automatically. Missing pinned versions and conflicting installed/managed sources under the same version are not silently replaced.

Background jobs run in-process; recovery records interrupted work. This is not a distributed scheduler.

## Packaging and access boundaries

The PyPI package contains the Python server and built admin console. `console.py` serves API routes and `/ui`; editable frontend source lives in `web/`. Release CI generates `src/decision_layer/static/`, which is not edited directly. VitePress documentation deploys separately.

`decision-layer demo` creates a visible project in the current empty/virtualenv-only workspace (or a safe child directory if populated), then starts sample PostgreSQL and Cube in Docker and launches the installed server. Subsequent commands inside that project select the same root (ADR-118). Its own project and containers do not inherit organization source settings. Source data remains in a PostgreSQL volume; Runs use the sample project's SQLite database.

Only local and isolated demo deployments are supported. Shared deployment is blocked pending independent application identity and execution isolation. Source administration requires an operator key and approved endpoint. Recipe and Method editing/publication have separate permissions.

Runs belong to their caller. Shared reads still validate semantic access. Python module imports and publication are trusted operator code; child-process checks are not an untrusted-code sandbox.

## Making changes

Add a Method for a new calculation, a Recipe for composition, or a Validator for a data condition. Change metric definitions and joins in Cube. Model-improvement drafts are review material; they do not automatically edit the source.

Read [Product context](https://github.com/haechangcho/decision-layer/blob/main/docs/PRODUCT_CONTEXT.md) before implementation and update [Decisions](https://github.com/haechangcho/decision-layer/blob/main/docs/DECISIONS.md) when architecture changes. Historical implementation decisions live there as well.
