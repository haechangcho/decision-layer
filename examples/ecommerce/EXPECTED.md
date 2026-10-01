# Expected answers

The synthetic data plants these effects; Decision Layer's live tests (`pytest -m cube`) and the eval scenarios
(`evals/scenarios.json`) check them. Period 2026-01-01 – 2026-09-30 unless noted.

| Question | Method | Expected |
|---|---|---|
| Return rate by category | `query.drilldown` | top: 여성의류 16.73% |
| Sellers within 여성의류 | `query.drilldown` with `drill_path` | top: S017 22.81% (526 orders), significant after selection among 40 |
| Free shipping vs not, matching category · channel · order amount (30k/100k/300k) | `causal.cem` | +1.569 pp (11.403 vs 9.834), 182 shared strata, 82,601 target orders |
| Late delivery: carrier B vs A, matching region · warehouse | `causal.cem` | +1.962 pp |
| Late delivery: carrier C vs A | `causal.cem` | +0.028 pp, not significant |
| Delivery ≥ 3 days vs < 3, same conditions as free shipping | `causal.cem` (unit path) | +1.814 pp, 172 shared strata |
| Q3 vs Q2 return rate | `query.trend` with `comparison` | +0.09 pp, not significant (95% CI includes 0) — noise |
| Q3 vs Q2 order amount | `query.trend` with `comparison` | +0.65% total, all of it from the extra day (92 vs 91 days); per day, orders and AOV both fell |
