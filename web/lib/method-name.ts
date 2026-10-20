const names: Record<string, string> = {
  "analysis.metric_lookup": "지표 조회",
  "stats.regression_adjustment": "OLS 회귀분석",
  "stats.binary_matching": "매칭 분석",
  "analysis.trend": "추이 조사 · Skill",
  "stats.period_change": "기간 간 변화 계산",
  "stats.series_diagnostics": "추이 계산·검사",
  "analysis.drilldown": "그룹별 분석",
  "analysis.peer_comparison": "동료 집단 비교 · Skill",
  "query.aggregate": "지표 조회",
  "query.trend": "시간에 따른 변화",
  "query.drilldown": "항목별로 나눠 보기",
  "query.peer_comparison": "집단 간 비교",
  "causal.cem": "조건을 맞춰 비교",
};

export const methodName = (name: string) => names[name] || name;

/** Short navigation labels; full contracts remain on the detail page. */
export const methodTitle = (method: { name: string; label?: string }) => names[method.name] || method.label || method.name;
const summaries: Record<string, string> = {
  "analysis.metric_lookup": "지표와 기간을 선택해 값을 조회합니다.",
  "analysis.drilldown": "지표를 그룹별로 나누고, 선택한 그룹을 이어서 살펴봅니다.",
  "stats.regression_adjustment": "다른 변수를 고려해 관심 변수와 결과의 관계를 분석합니다.",
  "stats.binary_matching": "조건이 비슷한 대상을 짝지어 두 집단의 결과를 비교합니다.",
};
export const methodSummary = (method: { name: string; description: string }) => summaries[method.name] || method.description;
