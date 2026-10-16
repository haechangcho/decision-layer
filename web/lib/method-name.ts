import type { Translate } from "./i18n";

const names: Record<string, string> = {
  "query.aggregate": "Metric lookup",
  "query.trend": "Change over time",
  "query.drilldown": "Break down by dimension",
  "query.peer_comparison": "Compare with peers and overall",
  "causal.cem": "Compare with conditions matched",
};

export const methodName = (name: string, t: Translate) => names[name] ? t(names[name]) : name;
