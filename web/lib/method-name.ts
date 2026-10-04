const names: Record<string, string> = {
  "query.trend": "시간에 따른 변화",
  "query.drilldown": "항목별로 나눠 보기",
  "query.peer_comparison": "동료·전체 집단과 비교",
  "causal.cem": "조건을 맞춰 비교",
};

export const methodName = (name: string) => names[name] || name;
