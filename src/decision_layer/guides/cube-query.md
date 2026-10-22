# Governed Cube query guide

## Choose data from the catalog

Read `get_semantic_catalog` before selecting inputs. It returns all caller-visible
objects from Cube metadata, including definitions, data types, aggregation kinds,
entity keys and dates. Choose actual refs from these objects; do not guess an
internal Cube name or invent a metric, formula or join. Ask when units, period,
population or the requested meaning are ambiguous.

The catalog describes available data. It does not contain observations or prove
that a particular query or join will succeed. Cube owns metric definitions,
aggregation and joins. Do not generate warehouse SQL or Wren model definitions.
Do not average ratios or sum non-additive metrics to reconstruct an official value.

## Execute the registered analysis

Use `list_methods` and `describe_method` to choose a registered procedure and read
its inputs. Prefer a suitable existing Recipe. Python Methods receive selected
bindings; the server builds Cube queries and supplies data to the function.

Query-executing Skills receive the shared `analysis-core` guide automatically.
Follow that guide for Run/step identifiers, scoped queries, paging, selection
handoff and completion. Individual Skill text supplies the analytical procedure;
it does not need to repeat the tool protocol.

Inspect recorded values, validation and warnings before explaining a result.
Query success does not prove source completeness, comparable populations or
causality. If the requested calculation is unavailable, report that limitation;
do not bypass it with generated Python, SQL or an invented diagnostic.

## Access and evidence

Execution enforces semantic access, typed inputs, periods, inherited filters,
query budgets and evidence references. Guidance is advisory and grants no access.
Source endpoints remain operator approved. The current local/demo deployment is
not a shared multi-tenant arbitrary-code sandbox.
