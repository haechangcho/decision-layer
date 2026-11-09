# Retail receipt review

Two ordinary registered Python Methods demonstrate a reusable investigation with
the public Complete Journey semantic model:

1. Query overall receipts and rank departments.
2. Pass the leading department's filters to the commodity ranking.
3. Pass the top three commodities and their parent department to daily inspection.
4. Repeat for another period; selected group names are computed again.

Load this directory as a Method project. The provider must expose the Complete
Journey `journey` references; no provider credentials are stored here. Each Method
uses governed `DataInput` queries and requires complete retrieval. Ranking retains
all candidates independently of the table display limit, allowing the runtime to
refuse ties at a later selection boundary.

For example, connect a later step's `filters` parameter explicitly:

```yaml
filters:
  source: step
  step_id: categories
  output: ranked_groups
  select: top
  count: 3
  project: filters
```

`daily_profile` accepts additive, non-negative metrics and summarizes observed days.
It does not fill missing dates with zero, test significance, establish ingestion
completeness or identify causes. A high peak share is a descriptive follow-up
candidate, not an anomaly verdict.
