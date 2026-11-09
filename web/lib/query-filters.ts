import type { SemanticObject } from "./api";

export type FilterOperator = "equals" | "notEquals" | "gt" | "gte" | "lt" | "lte" | "contains" | "set" | "notSet";
export type QueryFilter = { member: string; operator: FilterOperator; values: (string | number | boolean)[] };

export function filterOperators(type?: string): FilterOperator[] {
  return ["equals", "notEquals", ...(type === "number" ? ["gt", "gte", "lt", "lte"] as const : []),
    ...(type === "string" ? ["contains"] as const : []), "set", "notSet"];
}

export function filterValue(text: string, type?: string): string | number | boolean {
  if (type === "boolean" && (text === "true" || text === "false")) return text === "true";
  if (type === "number" && text.trim() && Number.isFinite(Number(text))) return Number(text);
  return text;
}

/** UI completeness only; canonical API/provider validation remains authoritative. */
export function completeFilters(value: unknown, objects: SemanticObject[]): boolean {
  if (value == null) return true;
  if (!Array.isArray(value)) return typeof value === "object" && ["step", "input"].includes(String((value as { source?: string }).source));
  return value.every(item => {
    if (!item || typeof item !== "object") return false;
    const field = objects.find(object => object.ref === item.member);
    if (!field || field.public === false || !filterOperators(field.data_type).includes(item.operator) || !Array.isArray(item.values)) return false;
    if (["set", "notSet"].includes(item.operator)) return item.values.length === 0;
    if (!item.values.length) return false;
    return item.values.every((value: unknown) => {
      if (field.data_type === "number") return (typeof value === "number" || typeof value === "string" && value.trim() !== "") && Number.isFinite(Number(value));
      if (field.data_type === "boolean") return typeof value === "boolean" || value === "true" || value === "false";
      return typeof value === "string" ? value.trim() !== "" : typeof value === "boolean" || typeof value === "number" && Number.isFinite(value);
    });
  });
}
