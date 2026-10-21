import type { Translate } from "./i18n";

const names: Record<string, string> = {
  "analysis.metric_lookup": "Metric lookup",
  "stats.regression_adjustment": "OLS regression",
  "stats.binary_matching": "Matching analysis",
  "analysis.trend": "Trend investigation / Skill",
  "stats.period_change": "Period change calculation",
  "stats.series_diagnostics": "Trend calculation and checks",
  "analysis.drilldown": "Group analysis",
  "analysis.peer_comparison": "Peer comparison / Skill",
  "query.aggregate": "Metric lookup",
  "query.trend": "Change over time",
  "query.drilldown": "Break down by dimension",
  "query.peer_comparison": "Compare with peers and overall",
  "causal.cem": "Compare with conditions matched",
};

export const methodName = (name: string, t: Translate) => names[name] ? t(names[name]) : name;

/** Short navigation labels; full contracts remain on the detail page. */
export const methodTitle = (method: { name: string; label?: string }, t: Translate) => names[method.name] ? t(names[method.name]) : method.label || method.name;
const summaries: Record<string, string> = {
  "analysis.metric_lookup": "Choose a metric and dates to query its values.",
  "analysis.drilldown": "Break a metric down by group, then investigate a selected group.",
  "stats.regression_adjustment": "Analyze the relationship between a variable and the outcome while adjusting for other variables.",
  "stats.binary_matching": "Match observations with similar conditions and compare their outcomes.",
};
export const methodSummary = (method: { name: string; description: string }, t: Translate) => summaries[method.name] ? t(summaries[method.name]) : method.description;
