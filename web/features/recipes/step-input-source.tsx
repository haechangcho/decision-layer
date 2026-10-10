"use client";

import type { MethodManifest, ParamSpec, PlanStep, Result, SemanticObject } from "@/lib/api";

type SourceContext = { titles?: Map<string, SemanticObject>; steps?: PlanStep[]; observedSteps?: PlanStep[]; results?: Result[] };

export function declaredPath(step: PlanStep, steps: PlanStep[], seen = new Set<string>()): string[] {
  if (step.id && seen.has(step.id)) return [];
  if (step.id) seen.add(step.id);
  const source = step.params.drill_path;
  let used = Array.isArray(source) ? source.map(item => item.member).filter((member): member is string => typeof member === "string") : [];
  if (source && typeof source === "object" && !Array.isArray(source)) {
    const ref = source as { source?: string; step_id?: string; project?: string };
    const prior = steps.find(item => item.id === ref.step_id);
    if (ref.source === "step" && prior) {
      const path = declaredPath(prior, steps, seen);
      used = ref.project === "condition" ? path.slice(-1) : ref.project === "parents" ? path.slice(0, -1) : path;
    } else return []; // A runtime input cannot reveal its dimension before execution.
  }
  const dimensions = Array.isArray(step.bindings.dimensions) ? step.bindings.dimensions as string[] : [];
  const next = typeof step.params.next_dimension === "string" ? step.params.next_dimension : dimensions.find(ref => !used.includes(ref));
  return [...used, ...(next ? [next] : [])];
}

export function selectionLabel(step: PlanStep, project: string, methods: MethodManifest[], context: SourceContext = {}): string {
  const observed = context.observedSteps?.find(item => item.id === step.id) ?? step;
  const output = context.results?.[context.observedSteps?.findIndex(item => item.id === step.id) ?? -1]?.selections?.ranked_groups;
  const path = output?.candidates[0]?.path.map(item => item.member) ?? declaredPath(observed, context.steps ?? context.observedSteps ?? []);
  const title = (ref: unknown, fallback: string) => typeof ref === "string" ? context.titles?.get(ref)?.title ?? fallback : fallback;
  const dimension = title(path.at(-1), "항목");
  const metric = title(step.bindings.metric, "지표");
  const manifest = methods.find(method => method.name === step.method);
  const rank = output?.rank_by ?? step.params.rank_by ?? manifest?.parameters.rank_by?.default;
  const direction = output?.direction ?? step.params.direction ?? manifest?.parameters.direction?.default;
  const selected = ["value", "metric"].includes(String(rank)) && ["asc", "desc"].includes(String(direction))
    ? `${metric}이 가장 ${direction === "asc" ? "작은" : "큰"} ${dimension}`
    : rank === "count" && ["asc", "desc"].includes(String(direction))
      ? `건수가 가장 ${direction === "asc" ? "적은" : "많은"} ${dimension}`
      : rank === "vs_rest" && ["asc", "desc"].includes(String(direction))
        ? `${metric}의 다른 집단 대비 차이가 가장 ${direction === "asc" ? "작은" : "큰"} ${dimension}` : `이 단계의 정렬 기준으로 선택한 ${dimension}`;
  if (project === "condition") return selected;
  if (project === "parents") return path.length > 1 ? `${selected}과 같은 ${path.slice(0, -1).map(ref => title(ref, "분류")).join(" · ")}` : `${selected}을 찾은 전체 분석 범위`;
  return `${selected} 안에서 분석${path.length > 1 ? ` (${path.slice(0, -1).map(ref => title(ref, "분류")).join(" · ")} 조건 포함)` : ""}`;
}

export function sourceLabel(value: unknown, steps: PlanStep[] = []): string | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const ref = value as Record<string, unknown>;
  if (ref.source === "input") return `실행 시 입력 · ${ref.name}`;
  if (ref.source !== "step") return null;
  const index = steps.findIndex(step => step.id === ref.step_id);
  const origin = index >= 0 ? `${index + 1}단계` : "앞 단계";
  const projection = ref.project === "condition" ? "찾은 대상" : ref.project === "parents" ? "찾은 대상과 같은 조건의 집단" : "찾은 대상 안에서 분석";
  return `${origin}에서 ${projection} · 실행할 때 다시 선택`;
}

export function StepInputSource({ value, onChange, steps, methods, inputs, type, label, disabled, literal, parameter, spec, titles, observedSteps, results }: {
  value: unknown; onChange: (value: unknown) => void; steps: PlanStep[]; methods: MethodManifest[];
  inputs?: Record<string, ParamSpec>; type: string; label: string; disabled?: boolean; literal?: unknown;
  parameter?: string; spec?: ParamSpec; titles?: Map<string, SemanticObject>; observedSteps?: PlanStep[]; results?: Result[];
}) {
  const choices = steps.filter(step => methods.find(method => method.name === step.method)?.selection_outputs?.includes("ranked_groups"));
  const ref = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
  const selected = ref?.source === "step" ? `step:${ref.step_id}:${ref.project || "path"}` : ref?.source === "input" ? `input:${ref.name}` : "fixed";
  const change = (value: string) => {
    const [kind, id, project] = value.split(":");
    onChange(kind === "step" ? { source: "step", step_id: id, output: "ranked_groups", select: "first", project }
      : kind === "input" ? { source: "input", name: id } : literal ?? []);
  };
  const allowed = spec?.source_policy?.allowed ?? ["literal", "input", "step"];
  const options = [...(allowed.includes("literal") ? [{ value: "fixed", label: "직접 지정한 조건 사용" }] : []), ...(type === "drill_path" && allowed.includes("step") ? choices.flatMap(step => {
      const observed = observedSteps?.find(item => item.id === step.id) ?? step;
      const depth = Array.isArray(observed.params.drill_path) ? observed.params.drill_path.length + 1 : 1;
      const projects = spec?.source_policy ? [spec.source_policy.project] : parameter === "subject" ? ["condition"] : parameter === "drill_path" ? ["path"] : parameter === "peers" ? [depth > 1 ? "parents" : "path"] : ["path", "condition", "parents"];
      if (ref?.source === "step" && ref.step_id === step.id && !projects.includes(String(ref.project))) projects.push(String(ref.project));
      return projects.map(project => ({ value: `step:${step.id}:${project}`, label: `${steps.indexOf(step) + 1}단계에서 ${selectionLabel(step, project, methods, { titles, steps, observedSteps, results })}` }));
    }) : []), ...(allowed.includes("input") ? Object.entries(inputs ?? {}).filter(([, spec]) => spec.type === type).map(([name, spec]) => ({ value: `input:${name}`, label: `실행 시 입력 · ${spec.label || spec.description || name}` })) : [])];
  return <label>{label} 설정 방식<select aria-label={`${label} 설정 방식`} disabled={disabled} value={selected} onChange={event => change(event.target.value)}>{options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>;
}
