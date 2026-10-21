"use client";

import type { MethodManifest, ParamSpec, PlanStep, Result, SemanticObject } from "@/lib/api";
import { type Translate, useT } from "@/lib/i18n";

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

export function selectionLabel(step: PlanStep, project: string, methods: MethodManifest[], t: Translate, context: SourceContext = {}): string {
  const observed = context.observedSteps?.find(item => item.id === step.id) ?? step;
  const selections = context.results?.[context.observedSteps?.findIndex(item => item.id === step.id) ?? -1]?.selections;
  const output = selections?.selected_group ?? selections?.ranked_groups;
  const path = output?.candidates[0]?.path.map(item => item.member) ?? declaredPath(observed, context.steps ?? context.observedSteps ?? []);
  const title = (ref: unknown, fallback: string) => typeof ref === "string" ? context.titles?.get(ref)?.title ?? fallback : fallback;
  const dimension = title(path.at(-1), t("item"));
  const metric = title(step.bindings.metric, t("metric"));
  const manifest = methods.find(method => method.name === step.method);
  const rank = output?.rank_by ?? step.params.rank_by ?? manifest?.parameters.rank_by?.default;
  const direction = output?.direction ?? step.params.direction ?? manifest?.parameters.direction?.default;
  const asc = direction === "asc";
  const sorted = ["asc", "desc"].includes(String(direction));
  const selected = manifest?.agent_executable ? t("{dimension} selected from this step’s query results", { dimension }) : ["value", "metric"].includes(String(rank)) && sorted
    ? t(asc ? "{dimension} with the lowest {metric}" : "{dimension} with the highest {metric}", { metric, dimension })
    : rank === "count" && sorted
      ? t(asc ? "{dimension} with the fewest rows" : "{dimension} with the most rows", { dimension })
      : rank === "vs_rest" && sorted
        ? t(asc ? "{dimension} whose {metric} differs least from the rest" : "{dimension} whose {metric} differs most from the rest", { metric, dimension })
        : t("{dimension} selected by this step's ranking", { dimension });
  const groups = path.slice(0, -1).map(ref => title(ref, t("category"))).join(" · ");
  if (project === "condition") return selected;
  if (project === "parents") return path.length > 1 ? t("Same {groups} as the {selected}", { selected, groups }) : t("Whole analysis scope where the {selected} was found", { selected });
  return path.length > 1 ? t("Analyze within the {selected} (including {groups} conditions)", { selected, groups }) : t("Analyze within the {selected}", { selected });
}

export function sourceLabel(value: unknown, t: Translate, steps: PlanStep[] = []): string | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const ref = value as Record<string, unknown>;
  if (ref.source === "input") return t("Runtime input · {name}", { name: String(ref.name) });
  if (ref.source !== "step") return null;
  const index = steps.findIndex(step => step.id === ref.step_id);
  const origin = index >= 0 ? t("Step {number}", { number: index + 1 }) : t("the previous step");
  return t(ref.project === "condition" ? "Subject found in {origin} · selected again at run time"
    : ref.project === "parents" ? "Group sharing the conditions of the subject found in {origin} · selected again at run time"
    : "Analyze within the subject found in {origin} · selected again at run time", { origin });
}

export function StepInputSource({ value, onChange, steps, methods, inputs, type, label, disabled, literal, parameter, spec, titles, observedSteps, results }: {
  value: unknown; onChange: (value: unknown) => void; steps: PlanStep[]; methods: MethodManifest[];
  inputs?: Record<string, ParamSpec>; type: string; label: string; disabled?: boolean; literal?: unknown;
  parameter?: string; spec?: ParamSpec; titles?: Map<string, SemanticObject>; observedSteps?: PlanStep[]; results?: Result[];
}) {
  const t = useT();
  const choices = steps.filter(step => methods.find(method => method.name === step.method)?.selection_outputs?.length);
  const ref = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
  const selected = ref?.source === "step" ? `step:${ref.step_id}:${ref.project || "path"}` : ref?.source === "input" ? `input:${ref.name}` : "fixed";
  const change = (value: string) => {
    const [kind, id, project] = value.split(":");
    onChange(kind === "step" ? { source: "step", step_id: id, output: methods.find(method => method.name === steps.find(step => step.id === id)?.method)?.selection_outputs?.[0] || "ranked_groups", select: "first", project }
      : kind === "input" ? { source: "input", name: id } : literal ?? []);
  };
  const allowed = spec?.source_policy?.allowed ?? ["literal", "input", "step"];
  const options = [...(allowed.includes("literal") ? [{ value: "fixed", label: t("Use the conditions set here") }] : []), ...(type === "drill_path" && allowed.includes("step") ? choices.flatMap(step => {
      const observed = observedSteps?.find(item => item.id === step.id) ?? step;
      const depth = Array.isArray(observed.params.drill_path) ? observed.params.drill_path.length + 1 : 1;
      const projects = spec?.source_policy ? [spec.source_policy.project] : parameter === "subject" ? ["condition"] : parameter === "drill_path" ? ["path"] : parameter === "peers" ? [depth > 1 ? "parents" : "path"] : ["path", "condition", "parents"];
      if (ref?.source === "step" && ref.step_id === step.id && !projects.includes(String(ref.project))) projects.push(String(ref.project));
      return projects.map(project => ({ value: `step:${step.id}:${project}`, label: t("From step {number}: {selection}", { number: steps.indexOf(step) + 1, selection: selectionLabel(step, project, methods, t, { titles, steps, observedSteps, results }) }) }));
    }) : []), ...(allowed.includes("input") ? Object.entries(inputs ?? {}).filter(([, spec]) => spec.type === type).map(([name, spec]) => ({ value: `input:${name}`, label: t("Runtime input · {name}", { name: spec.label || spec.description || name }) })) : [])];
  return <label>{t("{label} source", { label })}<select aria-label={t("{label} source", { label })} disabled={disabled} value={selected} onChange={event => change(event.target.value)}>{options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>;
}
