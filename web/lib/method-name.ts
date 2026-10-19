const names: Record<string, string> = {
  "analysis.metric_lookup": "지표 조회 · Skill",
  "analysis.trend": "추이 조사 · Skill",
  "stats.period_change": "기간 간 변화 계산",
  "stats.series_diagnostics": "추이 계산·검사",
  "analysis.drilldown": "항목별 조사 · Skill",
  "analysis.peer_comparison": "동료 집단 비교 · Skill",
  "query.aggregate": "지표 조회",
  "query.trend": "시간에 따른 변화",
  "query.drilldown": "항목별로 나눠 보기",
  "query.peer_comparison": "집단 간 비교",
  "causal.cem": "조건을 맞춰 비교",
};

export const methodName = (name: string) => names[name] || name;
