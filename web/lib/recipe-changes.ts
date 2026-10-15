import type { PlanStep, Recipe } from "./api";
import type { Translate } from "./i18n";
import { methodName } from "./method-name";
import { sourceLabel } from "@/features/recipes/step-input-source";

const equal = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);
const parameterLabels: Record<string, string> = {
  granularity: "Time unit", vs_previous: "Compare with previous period", top_n: "Groups to show",
  min_count: "Minimum group count", rank_by: "Ranked by",
};

function display(value: unknown, title: (ref: string) => string, t: Translate): string {
  if (value == null || value === "") return t("None");
  const source = sourceLabel(value, t);
  if (source) return source;
  if (typeof value === "boolean") return value ? t("On") : t("Off");
  if (typeof value === "string") return value.startsWith("$scope.") ? t("Recipe shared setting")
    : /^[a-z][a-z0-9+.-]*:\/\//i.test(value) ? title(value) : value;
  if (Array.isArray(value)) return value.length ? value.map(item => display(item, title, t)).join(" → ") : t("None");
  return JSON.stringify(value);
}

function stepChanges(before: PlanStep | undefined, after: PlanStep | undefined, index: number, title: (ref: string) => string, t: Translate): string[] {
  const prefix = t("Step {number}", { number: index + 1 });
  const show = (value: unknown) => display(value, title, t);
  if (!before && after) return [t("{step} added · {method}", { step: prefix, method: methodName(after.method, t) })];
  if (before && !after) return [t("{step} removed · {method}", { step: prefix, method: methodName(before.method, t) })];
  if (!before || !after) return [];
  const changes: string[] = [];
  if (before.method !== after.method) changes.push(`${t("{step} Method", { step: prefix })} · ${methodName(before.method, t)} → ${methodName(after.method, t)}`);
  for (const field of new Set([...Object.keys(before.bindings), ...Object.keys(after.bindings)])) {
    if (!equal(before.bindings[field], after.bindings[field]))
      changes.push(`${prefix} ${field === "metric" ? t("Analysis metric") : field === "dimensions" ? t("Breakdown order") : field} · ${show(before.bindings[field])} → ${show(after.bindings[field])}`);
  }
  for (const field of new Set([...Object.keys(before.params), ...Object.keys(after.params)])) {
    if (!equal(before.params[field], after.params[field]))
      changes.push(`${prefix} ${parameterLabels[field] ? t(parameterLabels[field]) : field} · ${show(before.params[field])} → ${show(after.params[field])}`);
  }
  return changes;
}

export function recipeChanges(before: Recipe | undefined, after: Recipe, title: (ref: string) => string, t: Translate): string[] {
  const changes: string[] = [];
  const show = (value: unknown) => display(value, title, t);
  if (!before) {
    changes.push(`${t("Analysis metric")} · ${show(after.semantic_scope.primary_metric)}`);
    if (after.description) changes.push(`${t("Analysis purpose")} · ${after.description}`);
    after.steps.forEach((step, index) => changes.push(...stepChanges(undefined, step, index, title, t)));
    if (after.origin_runs?.length) changes.push(`${t("Source runs")} · ${after.origin_runs.join(", ")}`);
    return changes;
  }
  if (before.description !== after.description) changes.push(`${t("Analysis purpose")} · ${show(before.description)} → ${show(after.description)}`);
  if (!equal(before.default_scope, after.default_scope)) changes.push(`${t("Default run scope")} · ${show(after.default_scope)}`);
  const scopeFields: [keyof Recipe["semantic_scope"], string][] = [
    ["primary_metric", "Analysis metric"], ["related_metrics", "Related metrics"], ["preferred_dimensions", "Breakdown dimensions"], ["required_filters", "Required filters"],
  ];
  for (const [field, label] of scopeFields) {
    if (!equal(before.semantic_scope[field], after.semantic_scope[field]))
      changes.push(`${t(label)} · ${show(before.semantic_scope[field])} → ${show(after.semantic_scope[field])}`);
  }
  const longest = Math.max(before.steps.length, after.steps.length);
  for (let index = 0; index < longest; index++) changes.push(...stepChanges(before.steps[index], after.steps[index], index, title, t));
  const policies = new Set([...Object.keys(before.method_parameters ?? {}), ...Object.keys(after.method_parameters ?? {})]);
  for (const method of policies) {
    const oldPolicy = before.method_parameters?.[method];
    const nextPolicy = after.method_parameters?.[method];
    const fixedNames = new Set([...Object.keys(oldPolicy?.fixed ?? {}), ...Object.keys(nextPolicy?.fixed ?? {})]);
    for (const name of fixedNames) {
      if (!equal(oldPolicy?.fixed[name], nextPolicy?.fixed[name]))
        changes.push(`${methodName(method, t)} · ${t("{parameter} fixed", { parameter: parameterLabels[name] ? t(parameterLabels[name]) : name })} · ${show(oldPolicy?.fixed[name])} → ${show(nextPolicy?.fixed[name])}`);
    }
    if (!equal(oldPolicy?.runtime_allowed ?? null, nextPolicy?.runtime_allowed ?? null))
      changes.push(`${methodName(method, t)} · ${t("Changeable at run time")} · ${oldPolicy?.runtime_allowed == null ? t("All") : show(oldPolicy.runtime_allowed)} → ${nextPolicy?.runtime_allowed == null ? t("All") : show(nextPolicy.runtime_allowed)}`);
  }
  for (const [field, label] of [["inputs", "Run inputs"], ["allowed_methods", "Allowed Methods"], ["routing", "Selection conditions"], ["validators", "Validation rules"], ["limits", "Run limits"], ["instructions", "Analysis instructions"], ["origin_runs", "Source runs"]] as const) {
    if (!equal(before[field], after[field])) changes.push(`${t(label)} · ${show(before[field])} → ${show(after[field])}`);
  }
  if (before.mode !== after.mode) changes.push(`${t("Analysis mode")} · ${before.mode} → ${after.mode}`);
  return changes;
}
