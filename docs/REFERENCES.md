# Decision Layer — Design References

This document records the external references that shaped the architecture and the lessons we intend to adopt or reject.

It is not a requirement to copy these systems literally.

---

## 1. Meta — “Inside Meta’s Home Grown AI Analytics Agent”

Source:
https://medium.com/@AnalyticsAtMeta/inside-metas-home-grown-ai-analytics-agent-4ea6779acfb3

### Relevant lessons

#### Repetitive analytics is highly automatable

Meta describes a key property of data work: analysts repeatedly work within familiar subsets of data and perform recurring forms of analysis.

Implication for Decision Layer:
- optimize for recurring analytical procedures,
- make those procedures reusable assets,
- do not assume every question is a net-new workflow.

#### Context must be bounded

Meta narrows the agent’s environment using users’ prior analytical domain and relevant context rather than searching the whole warehouse blindly.

Implication:
- semantic discovery and Recipe scope should narrow the search space,
- future namespaces/domain packs may group context,
- do not expose the full universe when a smaller relevant catalog is available.

#### Recipe = procedural knowledge

Meta’s Recipe concept encodes how a senior analyst would analyze a recurring question.

This directly supports Decision Layer’s separation:

```text
Semantic Layer = what the data means
Recipe         = how to analyze
```

#### Ingredients and Recipes should stay separate

Meta explicitly separates analytical procedure from business/data meaning.

Implication:
- Decision Layer Recipes reference Cube objects,
- they do not own metric definitions.

#### Iterative reasoning matters

Analytics is often a loop:
- run query,
- inspect result,
- choose next query.

Implication:
- support constrained `investigation` mode,
- do not model every Recipe as a static pipeline.

#### Show your work

Meta emphasizes transparency and showing the queries behind analytical claims.

Implication:
- provenance is a product requirement,
- not an optional debug page.

#### Community-created Recipes are meaningful assets

Meta reports substantial internal creation and reuse of Recipes.

Implication:
- Recipe authoring and sharing may be a stronger ecosystem surface than adding dozens of built-in algorithms.

---

## 2. Anthropic — “How Anthropic enables self-service data analytics with Claude”

Source:
https://claude.com/blog/how-anthropic-enables-self-service-data-analytics-with-claude

### Relevant lessons

#### Analytics accuracy is mainly a context and verification problem

Anthropic identifies major failure modes:
- concept-to-entity ambiguity,
- staleness,
- retrieval failure.

Implication:
- semantic entity resolution,
- freshness,
- validation,
- and structured context
are core system concerns.

#### Semantic layer should be the default source of truth

Anthropic routes analytical questions through governed semantic definitions first.

Implication:
- Decision Layer should not casually bypass Cube for raw SQL,
- semantic-provider-first is a product principle.

#### Human-owned semantic definitions

Anthropic reports poor results from auto-generating semantic definitions with LLMs.

Implication:
- do not let Decision Layer invent metrics,
- keep semantic definitions human-governed in the provider.

#### Skills = procedural knowledge

Anthropic distinguishes declarative data knowledge from procedural Skills.

This maps closely to:

```text
Semantic Catalog = declarative meaning
Recipe            = procedural analytical knowledge
```

#### Structured patterns outperform unstructured historical-query retrieval

Anthropic reports limited value from directly retrieving large query corpora and stronger results from curated reference docs and reusable analysis patterns.

Implication:
- historical SQL is raw material for curation,
- not the runtime source of truth.

#### Maintenance is an engineering problem

Analytical instructions and docs go stale as the data model changes.

Implication:
- version Recipes,
- support Git/export,
- add CI/evals over time,
- preserve semantic references.

#### Offline evals matter

Anthropic uses question/answer or query-oriented evals to detect regressions.

Implication:
- Decision Layer should treat Evals as a first-class long-term object,
- Recipe changes should be testable.

#### Provenance and freshness matter

Anthropic exposes:
- source tier,
- freshness,
- ownership,
- review information.

Implication:
- Result schema must contain provenance.

---

## 3. Cube

Source:
https://cube.dev/

### What to learn from Cube

- A strong semantic abstraction can support many downstream consumers.
- “Connect once, consume semantically” is a powerful onboarding model.
- Provider metadata and semantic APIs are useful foundations for governed analytics.

### What not to duplicate

Decision Layer should not become a new semantic layer.

Cube remains responsible for:
- metric definitions,
- dimensions,
- entities,
- joins,
- access semantics,
- canonical business meaning.

Decision Layer consumes those objects.

---

## 4. jamovi / JASP / Orange

These systems demonstrate that:
- analysis capabilities can be modular,
- schema/module-driven UIs are viable,
- users benefit from reusable analytical components.

### What to adopt

- Method registry,
- declarative parameters,
- generic result renderers.

### What not to adopt

- desktop statistical-suite product scope,
- file-first/local-data UX as the main architecture.

---

## 5. DoWhy / EconML / CausalML / statsmodels

These projects should be treated primarily as execution backends or design references.

### Principle

Decision Layer should avoid reimplementing mature statistical algorithms unless:
- integration requirements demand it,
- dependency licensing is problematic,
- or the algorithm is simple enough that a native implementation materially improves portability.

Decision Layer’s primary value is:
- semantic integration,
- dataset planning,
- Method/Recipe contracts,
- validation,
- provenance,
- reusable procedures.

Not inventing another statistical library.

---

## 6. Dagster / Airflow / Prefect

These systems solve orchestration and automation.

### Design lesson

Separate:
- analytical definition,
from:
- execution scheduling/triggering.

Decision Layer should expose run APIs and allow orchestrators to call them.

Do not build a scheduler/trigger engine in MVP.

---

## 7. Airbyte

Airbyte is a useful design reference for extensibility:

- common declarative path for most integrations,
- code escape hatch for advanced cases.

Decision Layer analogy:

```text
Most Methods/Recipes
→ declarative schema

Advanced analytics
→ Python Method plugin
```

Avoid forcing every extension into bespoke frontend development.

---

## 8. Great Expectations

Useful reference for:
- plugin-like expectations,
- standardized validation results,
- renderable structured outputs,
- data-quality lifecycle.

Decision Layer should borrow the principle that validation results are structured data, not plain logs.

---

## 9. Reference principles distilled

The architecture should preserve these rules:

1. Governed semantics first.
2. Procedures separate from meaning.
3. Reusable typed procedures over free-form prompts.
4. Bounded context over global search.
5. Iterative investigation where needed.
6. Deterministic execution for statistical methods.
7. Validation before narration.
8. Provenance with every answer.
9. Version procedural knowledge.
10. Evaluate changes.
11. Human ownership of core definitions.
12. External orchestration rather than embedded trigger engines.
