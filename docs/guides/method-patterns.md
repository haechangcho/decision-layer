# Method authoring patterns

Classify data access by grain and extraction count to avoid overlap within the implemented scope. This does not claim support for every statistical algorithm or data structure. All patterns use the same function, registration and execution model; algorithms need no separate plugin interface.

| Pattern | Data access → combination | Executable cases |
| --- | --- | --- |
| A | One aggregate query → direct result | by-group, trend |
| B | Several aggregate queries → scalar/table combination | period, peer |
| C | One entity dataset → statistical algorithm | ols, dowhy, econml |
| D | Several entity datasets → aligned units | unit-change, unit-change-wide |
| E | One entity × time dataset → panel algorithm | did |
| F | Several entity × time datasets → combined panel | did-split |
| G | Aggregate and entity data → combined result | mixed |

## A. Drilldown and trends

Period and common filters are invocation inputs. The function selects measures and groups or time buckets. Missing buckets are not filled with zero; top-N is not treated as the complete population.

<<< @/../examples/methods/patterns/methods.py#series

## B. Combine several queries

“Inside the same function” means one Method execution sequentially awaits the three `ctx.aggregate(...)` calls below and combines their returned values in Python. No three functions, registrations or Recipe steps are needed. Each request has its own label, budget consumption and provenance; evidence from the first survives a failure in the second. These calls are sequential and do not guarantee one provider snapshot.

`peers` defines the comparison conditions; `subject` defines the target. Invocation filters apply to all three queries. A shared filter on the subject dimension would invalidate the overall benchmark and is refused. The same provider applies permissions to target and exclusion queries.

<<< @/../examples/methods/patterns/methods.py#peer

<<< @/../examples/methods/patterns/methods.py#period_difference

## C–G. Entities and panels

`ctx.entities(entity=unit, measures=..., dimensions=...)` requests complete data at a provider-declared analysis unit. With `by_time` and `time_granularity`, the key becomes unit × bucket. Entity statistics do not use top-N. `stats.ols`, `stats.binary_regression` and `stats.linear_dml` share extraction shape and apply different algorithms.

`query.unit_change` outer-joins two periods or provider-defined pre/post measures on the same unit and verifies identical cohorts. Omitting `stats.two_period_contrast` windows extracts one panel; disjoint windows extract partitions using the same Method. `query.unit_distribution` combines the provider aggregate and unit distribution.

See [advanced mappings and assumptions](statistical-methods.md) and [12 execution / 13 failure scenarios](method-scenarios.md). Streaming, survival analysis, multiple treatments and complex longitudinal inference are outside these examples.
