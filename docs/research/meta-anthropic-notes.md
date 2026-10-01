# Meta + Anthropic Analytics Agent Notes

These notes capture only the design lessons relevant to Decision Layer.

## Meta

Key ideas:
- much analytics work is repetitive within a bounded data domain,
- personal/business context sharply improves usefulness,
- analysis is iterative, not always a static pipeline,
- Recipes encode reusable analyst SOPs,
- Ingredients encode what data/business concepts mean,
- Cookbooks package context for a domain/team,
- showing queries/work is important for trust,
- user-created Recipes became a meaningful internal ecosystem.

Decision Layer adaptation:
- keep semantics in Cube,
- use Recipes for procedural knowledge,
- allow constrained iterative investigation,
- make provenance visible,
- prioritize Recipe authoring/reuse.

Do not copy literally:
- Decision Layer does not need a full Cookbook/Domain object in MVP,
- personal query history should not become a hard dependency.

## Anthropic

Key ideas:
- analytics errors often come from concept/entity ambiguity, staleness, and retrieval failure,
- governed canonical data dramatically reduces ambiguity,
- semantic layer should be mandatory/default when it covers the question,
- human-owned definitions are safer than auto-generated semantic metrics,
- Skills encode procedural knowledge,
- raw query-history retrieval produced limited gains compared with structured references/patterns,
- skill/reference maintenance needs engineering discipline,
- offline evals and online validation are necessary,
- provenance/freshness helps users judge trust.

Decision Layer adaptation:
- Cube-first semantic resolution,
- Recipe + Validator + Eval as durable assets,
- typed plans rather than arbitrary code,
- version Recipes and expose provenance,
- eventually colocate/export Recipes and data-model-adjacent docs into Git.

## Combined design principle

```text
Semantic layer = what the data means
Method         = atomic analytical operation
Recipe         = how experts analyze recurring questions
Validator      = what must be true for the result to be trusted
Eval           = how we prevent procedure regressions
Result         = typed output + provenance
```
