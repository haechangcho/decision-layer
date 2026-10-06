import type { SemanticObject } from "./api";

export function suggestedDateRange(object: SemanticObject | undefined): [string, string] | null {
  const range = object?.metadata?.suggestedDateRange;
  if (!Array.isArray(range) || range.length !== 2 || !range.every(value => {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const date = new Date(`${value}T00:00:00Z`);
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }) || range[0] > range[1]) return null;
  return [range[0], range[1]];
}

export function suggestedTimeDimension(objects: SemanticObject[], metric: string): SemanticObject | undefined {
  const selected = objects.find(object => object.ref === metric);
  if (selected?.time_dimension) return objects.find(object => object.ref === selected.time_dimension);
  const dates = objects.filter(object => object.kind === "time_dimension" && suggestedDateRange(object)
    && selected?.dimension_refs?.includes(object.ref));
  return dates.length === 1 ? dates[0] : undefined;
}
