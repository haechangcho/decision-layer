# Decision Layer — Product Context

## 1. Product summary

Decision Layer is an open-source analytics knowledge and execution layer that sits above a semantic layer.

Its purpose is to turn:
- governed semantic objects,
- reusable analytical methods,
- and senior analysts' procedural knowledge

into reproducible analyses that humans and AI agents can execute consistently.

A concise product description:

> Connect your semantic layer once, encode how your organization analyzes recurring questions, and run those procedures consistently through Web, Python, API, or MCP.

## 2. The problem

Modern analytics stacks solve two separate problems well.

### Semantic layers solve “What does the data mean?”

Systems such as Cube define:
- metrics/measures,
- dimensions,
- entities,
- joins,
- access rules,
- grain,
- canonical business definitions.

This reduces metric ambiguity and keeps downstream consumers aligned.

### Statistical and causal libraries solve “How do I compute this?”

Libraries such as:
- statsmodels,
- scikit-learn,
- DoWhy,
- EconML,
- CausalML,
- MatchIt,

provide statistical algorithms once a correct dataset already exists.

### The gap

Organizations also possess **procedural analytical knowledge** such as:

- “When revenue drops, first compare with the previous complete period.”
- “Break it down by product, region, customer segment, and channel.”
- “Inspect quantity, average unit price, and discount rate together.”
- “When estimating observational treatment effects, use pre-treatment covariates.”
- “Do not interpret an OLS coefficient causally without an identification strategy.”
- “For this KPI, always exclude test users.”
- “This metric is only stable after D+2.”

This knowledge is often scattered across:
- senior analysts' heads,
- notebooks,
- SQL history,
- dashboards,
- docs,
- Slack threads.

It is difficult for:
- junior analysts,
- non-technical stakeholders,
- and AI agents

to reproduce reliably.

Decision Layer exists to make that knowledge **executable, inspectable, versionable, and reusable**.

## 3. Product thesis

The product should not be centered on a catalog of statistical algorithms.

“CEM, DiD, OLS in a GUI” is too narrow and does not by itself create a strong product.

The stronger thesis is:

> Organizations repeatedly answer similar analytical questions within bounded business contexts. If those procedures can be encoded as reusable Recipes that operate over governed semantic models, analysts and AI agents can produce more consistent, auditable results.

This thesis is supported by lessons from Meta and Anthropic:

- Meta reports that much analytical work is repetitive and built from familiar data; it introduced reusable Recipes that encode senior-analyst-style procedures.
- Anthropic emphasizes that analytics accuracy is mainly a context, entity-resolution, freshness, and verification problem rather than a code-generation problem.
- Both separate **what the data means** from **how the analysis should be performed**.

## 4. Core concepts

### 4.1 Semantic Source

An external governed semantic system.

MVP:
- Cube
- dbt Semantic Layer's official GraphQL API (ADR-058)

Future candidates:
- Malloy
- Sidemantic
- others

Decision Layer does not replace the semantic layer.

### 4.2 Semantic Catalog

Decision Layer's canonical internal representation of semantic objects discovered from a provider.

Examples:
- metric,
- measure,
- dimension,
- entity,
- time dimension,
- grain,
- provider capabilities.

Decision Layer should preserve stable external references such as:

```text
cube://production/sales/revenue
cube://production/customer/segment
```

### 4.3 Method

An atomic analytical capability.

Examples:

Query/exploration:
- `query.compare`
- `query.drilldown`
- `query.contribution`
- `query.related_metrics`

Statistics:
- `stats.ols`
- `stats.correlation`
- `stats.t_test`

Causal:
- `causal.cem`
- `causal.psm`
- `causal.did.simple`

A Method defines:
- input roles,
- parameter schema,
- dataset requirements,
- validation rules,
- executor,
- diagnostics,
- typed outputs.

### 4.4 Recipe

A reusable analytical procedure, usually organization-specific.

A Recipe answers:

> “How should an experienced analyst investigate this kind of question?”

Example:

**Revenue Investigation**
1. Compare current complete period vs previous complete period.
2. Identify contribution by preferred dimensions.
3. Drill down by product, region, customer segment, and channel.
4. Inspect quantity, average unit price, and discount rate.
5. Continue investigating the dominant branch.
6. Validate freshness and required filters.
7. Produce a concise result with provenance.

Recipes reference semantic objects and Methods. They do not redefine metrics.

### 4.5 Validator

A reusable rule that verifies an analysis or result.

Examples:
- freshness,
- required filter,
- complete comparison period,
- expected range,
- non-empty result,
- minimum sample,
- overlap,
- covariate balance,
- panel completeness,
- causal assumptions.

Validators may come from:
- a Method,
- a Recipe,
- provider metadata,
- future scoped policy/namespace configuration.

### 4.6 Analysis Plan

A concrete plan produced for one request.

Example:

```text
Question
“Why did revenue fall last month?”

Resolved metric
sales.revenue

Selected recipe
revenue_investigation@2.1

Steps
1. compare
2. contribution by product
3. contribution by region
4. inspect related metrics for dominant product
```

The Plan is more concrete than a Recipe and is tied to one question/run.

### 4.7 Run

One execution instance.

A Run records:
- requested question or invocation,
- resolved semantic references,
- Method/Recipe versions,
- generated dataset/query specs,
- compiled query where available,
- validator results,
- runtime versions,
- timestamps,
- result references.

### 4.8 Result

A typed analytical output.

Examples:
- scalar estimate,
- confidence interval,
- contribution table,
- breakdown table,
- balance diagnostics,
- coefficients,
- time series,
- warnings,
- provenance.

The same Result should be renderable in:
- Web,
- MCP,
- Python,
- API clients.

### 4.9 Eval

A regression test for analytical behavior.

Examples:
- question should resolve to canonical revenue metric,
- revenue investigation should use the approved Recipe,
- must use product as a breakdown dimension,
- must exclude test users,
- must not use raw SQL when Cube covers the question,
- causal Recipe must refuse if treatment timing is incompatible.

Evals should eventually be runnable in CI.

## 5. Method vs Recipe

This distinction is foundational.

### Method

Generic computation.

Example:
```text
query.drilldown
```

It knows how to:
- receive one metric,
- receive dimensions,
- query at the appropriate grain,
- return a typed breakdown result.

It does not know that Revenue should be broken down by Product.

### Recipe

Organization-specific procedural knowledge.

Example:
```text
Revenue Investigation
```

It knows:
- primary metric: Revenue,
- preferred dimensions: Product, Region, Customer Segment,
- companion metrics: Quantity, Average Unit Price, Discount Rate,
- preferred comparison: previous complete month,
- how to proceed after detecting a dominant contributor.

This separation allows one Method implementation to support many business Recipes.

## 6. Deterministic vs agentic execution

Not every analysis should be executed in the same way.

### Deterministic/pipeline-style

Examples:
- OLS,
- CEM,
- simple DiD.

A known sequence runs over a dataset:
```text
Dataset -> Fit/Match -> Diagnostics -> Typed Result
```

### Agentic investigation

Examples:
- “Why did revenue drop?”
- “What changed in signups?”

The next analytical step depends on previous results:

```text
Compare
  ↓
Product explains most change
  ↓
Inspect product
  ↓
Quantity changed, price did not
  ↓
Break quantity down by region
```

Recipes should support a constrained investigation mode.

The agent is not allowed arbitrary SQL/Python by default. It receives:
- a bounded semantic catalog,
- an allowed Method set,
- Recipe instructions,
- query/step limits,
- validators.

## 7. Natural language behavior

Natural language should not compile directly into arbitrary Python or SQL.

Preferred flow:

```text
User question
  ↓
Context / scope resolution
  ↓
Semantic entity resolution
  ↓
Recipe or Method selection
  ↓
Typed Analysis Plan
  ↓
Dataset planning
  ↓
Semantic provider execution
  ↓
Method execution
  ↓
Validation
  ↓
Typed Result
  ↓
Narration
```

LLM responsibilities:
- resolve intent,
- map terms to existing semantic objects,
- choose among registered Recipes/Methods,
- decide next allowed investigation step,
- explain typed results.

LLM must not:
- invent semantic objects,
- silently redefine metrics,
- bypass validation,
- fabricate causal interpretations,
- generate arbitrary execution code as the normal path.

## 8. Example: Revenue Investigation

A senior analyst wants to encode:

- automatically drill down by region, product, customer segment, channel,
- inspect quantity, average unit price, discount rate,
- compare with previous complete period,
- surface largest contributors first.

A Recipe could look conceptually like:

```yaml
kind: AnalysisRecipe

metadata:
  name: revenue_investigation
  version: 1.0.0

routing:
  use_for:
    - revenue_drop
    - revenue_growth
    - metric_change
  do_not_use_for:
    - causal_effect

semantic_scope:
  primary_metric: cube://production/sales/revenue

  related_metrics:
    - cube://production/sales/quantity
    - cube://production/sales/avg_unit_price
    - cube://production/sales/discount_rate

  preferred_dimensions:
    - cube://production/sales/product
    - cube://production/sales/region
    - cube://production/customer/segment
    - cube://production/sales/channel

execution:
  mode: investigation

  allowed_methods:
    - query.compare
    - query.contribution
    - query.drilldown
    - query.related_metrics

  limits:
    max_steps: 12
    max_queries: 20

validators:
  - complete_period
  - freshness
  - required_filters

output:
  sections:
    - headline
    - largest_contributors
    - supporting_metrics
    - caveats
```

## 9. Example: CEM

Question:

> “Did receiving the promotion increase 30-day revenue? Compare customers with similar age, tenure, and pre-period revenue.”

Flow:

1. Resolve:
   - treatment,
   - outcome,
   - covariates,
   - unit.
2. Match to `causal.cem`.
3. Validate fields are compatible.
4. Build entity-grain Dataset Spec.
5. Query Cube only for required fields.
6. Execute CEM matching/weighting.
7. Run balance diagnostics.
8. Estimate treatment effect.
9. Return:
   - effect,
   - confidence interval,
   - sample retention,
   - balance,
   - warnings,
   - provenance.
10. Narrate carefully:
   - state observed-confounding limitation,
   - do not imply randomization.

## 10. Why Cube first

The initial product should not attempt shallow support for every semantic layer.

Cube is a strong MVP provider because:
- it exposes governed semantic models,
- it supports APIs suitable for downstream analytical tools,
- it can provide semantic metadata,
- it is close to the desired “connect once, consume semantically” experience.

Target onboarding:

```text
Connect Cube
  ↓
Discover models/measures/dimensions/entities
  ↓
Validate provider capabilities
  ↓
Ready to create Recipes/Analyses
```

The provider interface must remain generic enough for future integrations.

## 11. What is explicitly not the MVP

Do not build these unless later evidence justifies them:

- Trigger/scheduler engine,
- Airflow-like DAG orchestration,
- full Decision Graph,
- KPI causal graph,
- notebook editor,
- BI dashboard builder,
- semantic layer replacement,
- unrestricted raw SQL agent,
- arbitrary custom frontend code supplied by Method plugins,
- automatic causal discovery.

## 12. Long-term extension

A future Decision Graph may connect:

```text
Goal
 ↓
Metric
 ↓
Hypothesis
 ↓
Analysis / Recipe
 ↓
Run / Evidence
 ↓
Decision
```

This is intentionally not part of MVP.

To preserve this option, Decision Layer should use stable IDs/references for:
- semantic objects,
- recipes,
- methods,
- runs,
- results.

The graph should later reference Decision Layer; Decision Layer should not depend on the graph to function.

## 13. Product success criteria

The project is useful if organizations:
- connect real semantic models,
- encode reusable Recipes,
- rerun those Recipes,
- use them across human and agent workflows,
- add new Recipes without frontend engineering,
- add new Methods without duplicating API/MCP/UI logic.

A particularly strong signal is:
- users asking how to add their own Recipe or Method,
- the same Recipe being executed repeatedly by multiple consumers.

GitHub stars alone are not product validation.
