import type { PlanStep, Recipe } from "./api";
import { methodName } from "./method-name";
import { sourceLabel } from "@/features/recipes/step-input-source";

const equal = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);
const parameterLabels: Record<string, string> = {
  granularity: "시간 단위", vs_previous: "직전 기간 비교", top_n: "표시할 그룹 수",
  min_count: "최소 그룹 건수", rank_by: "정렬 기준",
};

function display(value: unknown, title: (ref: string) => string): string {
  if (value == null || value === "") return "없음";
  const source = sourceLabel(value);
  if (source) return source;
  if (typeof value === "boolean") return value ? "사용" : "사용 안 함";
  if (typeof value === "string") return value.startsWith("$scope.") ? "Recipe 공통 설정"
    : /^[a-z][a-z0-9+.-]*:\/\//i.test(value) ? title(value) : value;
  if (Array.isArray(value)) return value.length ? value.map(item => display(item, title)).join(" → ") : "없음";
  return JSON.stringify(value);
}

function stepChanges(before: PlanStep | undefined, after: PlanStep | undefined, index: number, title: (ref: string) => string): string[] {
  const prefix = `${index + 1}단계`;
  if (!before && after) return [`${prefix} 추가 · ${methodName(after.method)}`];
  if (before && !after) return [`${prefix} 삭제 · ${methodName(before.method)}`];
  if (!before || !after) return [];
  const changes: string[] = [];
  if (before.method !== after.method) changes.push(`${prefix} 방법 · ${methodName(before.method)} → ${methodName(after.method)}`);
  for (const field of new Set([...Object.keys(before.bindings), ...Object.keys(after.bindings)])) {
    if (!equal(before.bindings[field], after.bindings[field]))
      changes.push(`${prefix} ${field === "metric" ? "분석 지표" : field === "dimensions" ? "나눠 볼 순서" : field} · ${display(before.bindings[field], title)} → ${display(after.bindings[field], title)}`);
  }
  for (const field of new Set([...Object.keys(before.params), ...Object.keys(after.params)])) {
    if (!equal(before.params[field], after.params[field]))
      changes.push(`${prefix} ${parameterLabels[field] || field} · ${display(before.params[field], title)} → ${display(after.params[field], title)}`);
  }
  return changes;
}

export function recipeChanges(before: Recipe | undefined, after: Recipe, title: (ref: string) => string): string[] {
  const changes: string[] = [];
  if (!before) {
    changes.push(`분석 지표 · ${display(after.semantic_scope.primary_metric, title)}`);
    if (after.description) changes.push(`분석 목적 · ${after.description}`);
    after.steps.forEach((step, index) => changes.push(...stepChanges(undefined, step, index, title)));
    if (after.origin_runs?.length) changes.push(`원본 실행 기록 · ${after.origin_runs.join(", ")}`);
    return changes;
  }
  if (before.description !== after.description) changes.push(`분석 목적 · ${display(before.description, title)} → ${display(after.description, title)}`);
  if (!equal(before.default_scope, after.default_scope)) changes.push(`기본 실행 범위 · ${display(after.default_scope, title)}`);
  const scopeFields: [keyof Recipe["semantic_scope"], string][] = [
    ["primary_metric", "분석 지표"], ["related_metrics", "함께 볼 지표"], ["preferred_dimensions", "분류 기준"], ["required_filters", "필수 필터"],
  ];
  for (const [field, label] of scopeFields) {
    if (!equal(before.semantic_scope[field], after.semantic_scope[field]))
      changes.push(`${label} · ${display(before.semantic_scope[field], title)} → ${display(after.semantic_scope[field], title)}`);
  }
  const longest = Math.max(before.steps.length, after.steps.length);
  for (let index = 0; index < longest; index++) changes.push(...stepChanges(before.steps[index], after.steps[index], index, title));
  const policies = new Set([...Object.keys(before.method_parameters ?? {}), ...Object.keys(after.method_parameters ?? {})]);
  for (const method of policies) {
    const oldPolicy = before.method_parameters?.[method];
    const nextPolicy = after.method_parameters?.[method];
    const fixedNames = new Set([...Object.keys(oldPolicy?.fixed ?? {}), ...Object.keys(nextPolicy?.fixed ?? {})]);
    for (const name of fixedNames) {
      if (!equal(oldPolicy?.fixed[name], nextPolicy?.fixed[name]))
        changes.push(`${methodName(method)} · ${parameterLabels[name] || name} 고정 · ${display(oldPolicy?.fixed[name], title)} → ${display(nextPolicy?.fixed[name], title)}`);
    }
    if (!equal(oldPolicy?.runtime_allowed ?? null, nextPolicy?.runtime_allowed ?? null))
      changes.push(`${methodName(method)} · 실행 중 변경 허용 · ${oldPolicy?.runtime_allowed == null ? "전체" : display(oldPolicy.runtime_allowed, title)} → ${nextPolicy?.runtime_allowed == null ? "전체" : display(nextPolicy.runtime_allowed, title)}`);
  }
  for (const [field, label] of [["inputs", "실행 입력"], ["allowed_methods", "허용 방법"], ["routing", "선택 조건"], ["validators", "검증 규칙"], ["limits", "실행 한도"], ["instructions", "분석 지침"], ["origin_runs", "원본 실행 기록"]] as const) {
    if (!equal(before[field], after[field])) changes.push(`${label} · ${display(before[field], title)} → ${display(after[field], title)}`);
  }
  if (before.mode !== after.mode) changes.push(`분석 방식 · ${before.mode} → ${after.mode}`);
  return changes;
}
