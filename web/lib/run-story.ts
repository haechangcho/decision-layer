import type { PlanStep, Run } from "@/lib/api";

const defaultPurposes: Record<string, string> = {
  "query.trend": "기간별 값과 변화 확인",
  "query.drilldown": "그룹별 차이 확인",
  "query.peer_comparison": "비교 집단·전체 집단과 차이 확인",
  "causal.cem": "조건을 맞춘 차이 확인",
};

export function isSourcePurpose(step: PlanStep, run: Run): boolean {
  return !!run.plan.recipe && (step.purpose_context === "source_run" ||
    !step.purpose_context && !!run.recipe_snapshot?.origin_runs?.length);
}

export function stepPurpose(step: PlanStep, run?: Run): string {
  if (run && isSourcePurpose(step, run)) return defaultPurposes[step.method] || "저장된 분석 단계 실행";
  return step.purpose?.trim() || defaultPurposes[step.method] || "이 방법으로 결과 확인";
}

const number = (value: number) => value.toLocaleString("ko-KR", { maximumFractionDigits: 2 });

export function populationLabel(index: number, fallback: unknown): unknown {
  return ["선택한 대상", "비교 집단 (대상 제외)", "전체 집단 (대상 제외)"][index] ?? fallback;
}

export function stepFinding(record: Run["steps"][number]): string {
  const result = record.result;
  if (result.status === "needs_input") return "추가 입력이 필요합니다";
  if (result.status === "refused") return "분석 조건을 확인해야 합니다";
  if (result.status === "failed") return "분석에 실패했습니다";
  const primary = result.primary;
  if (!primary || !primary.data || typeof primary.data !== "object") return "결과 보기";
  const data = primary.data as Record<string, unknown>;
  if (primary.type === "time_series" && Array.isArray(data.rows)) {
    const metric = record.step.bindings.metric;
    const last = data.rows.at(-1);
    const value = typeof metric === "string" && last && typeof last === "object" ? (last as Record<string, unknown>)[metric] : null;
    if (typeof value === "number") return data.rows.length === 1 ? `선택 기간 ${number(value)}` : `최근 기간 ${number(value)}`;
  }
  if (primary.type === "breakdown_table" && Array.isArray(data.rows) && data.rows.length) {
    if (data.subject && data.rows.length === 3) {
      const [subject, peers, overall] = data.rows as Record<string, unknown>[];
      if (typeof subject.metric === "number" && typeof peers.difference_from_subject === "number" && typeof overall.difference_from_subject === "number")
        return `대상 ${number(subject.metric)} · 비교 집단 대비 ${number(peers.difference_from_subject)} · 전체 대비 ${number(overall.difference_from_subject)}`;
    }
    const first = data.rows[0] as Record<string, unknown>;
    if (typeof first.value === "string") return `${first.value}${typeof first.metric === "number" ? ` · ${number(first.metric)}` : ""}`;
  }
  return primary.title || "결과 보기";
}
