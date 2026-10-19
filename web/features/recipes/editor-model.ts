/** Recipe editor values and selectors, independent of React rendering. */
import { ApiError, type Recipe, type RoleSpec, type SemanticObject } from "@/lib/api";

export const blank = (): Recipe => ({ name: "", version: "1.0.0", description: "", status: "draft", mode: "pipeline", routing: { use_for: [], do_not_use_for: [] }, semantic_scope: { primary_metric: "", related_metrics: [], preferred_dimensions: [], required_filters: [] }, steps: [], allowed_methods: [], validators: [], limits: { max_steps: 12, max_queries: 30 } });
export const bump = (version: string) => version.replace(/\d+$/, n => String(Number(n) + 1));
export const refs = (value: unknown): string[] => Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
export const newName = (metric: string) => `${metric.split("/").pop()?.replaceAll("_", "-") || "analysis"}-${crypto.randomUUID().slice(0, 6)}`;
export const previewDates = (): [string, string] => {
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), 1);
  const date = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
  return [date(start), date(today)];
};
export const explainError = (error: unknown) => {
  if (error instanceof ApiError && error.details && typeof error.details === "object" && "field" in error.details) {
    const field = (error.details as { field?: unknown }).field;
    if (typeof field === "string") return `${field}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Recipe를 저장하지 못했습니다.";
};
export type FieldError = { field: string; message: string };
export function validationField(error: unknown): FieldError | null {
  if (!(error instanceof ApiError)) return null;
  const details = error.details;
  if (details && typeof details === "object" && "field" in details && typeof details.field === "string")
    return { field: details.field, message: error.message };
  if (Array.isArray(details) && Array.isArray(details[0]?.loc)) {
    const path = details[0].loc.filter((part: unknown) => part !== "body").reduce((value: string, part: unknown) =>
      typeof part === "number" ? `${value}[${part}]` : value ? `${value}.${part}` : String(part), "");
    return path ? { field: path, message: String(details[0].msg || error.message) } : null;
  }
  return null;
}

export function roleObjects(role: RoleSpec, objects: SemanticObject[]) {
  if (role.accepted_kinds) return objects.filter(object => role.accepted_kinds!.includes(object.kind));
  if (role.kind === "measure") return objects.filter((object) => object.kind === "measure" && (!role.metric_kinds || role.metric_kinds.includes(object.metric_kind ?? "")));
  if (role.kind === "dimension") return objects.filter((object) => object.kind === "dimension" || object.kind === "time_dimension");
  if (role.kind === "time_dimension") return objects.filter((object) => object.kind === "time_dimension");
  if (role.kind === "entity") return objects.filter(object => object.kind === "dimension" && objects.some(member => member.entity === object.ref));
  return objects.filter((object) => !!object.entity);
}

export const roleLabels: Record<string, string> = {
  metric: "분석 지표", related: "함께 볼 지표", dimensions: "나눠 볼 순서", conditions: "비교 조건",
  treatment: "비교 대상", treatment_measure: "비교 기준 지표", entity: "분석 단위",
};
export const parameterLabel = (name: string) => ({ subject: "비교 대상", peers: "동료 집단 조건", drill_path: "분석 범위", granularity: "시간 단위", vs_previous: "직전 같은 길이와 비교", top_n: "표시할 그룹 수", min_count: "최소 그룹 건수", rank_by: "정렬 기준" } as Record<string, string>)[name] || name;
