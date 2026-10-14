import type { Artifact } from "@/lib/api";

// Old Runs retain their stored time_series payload. New Tables carry governed
// column metadata separately from rows; date-looking strings alone are not axes.
export function timeSeriesData(artifact: Artifact): Record<string, unknown> | null {
  if (artifact.type === "time_series" && artifact.data && typeof artifact.data === "object" && !Array.isArray(artifact.data)) {
    return artifact.data as Record<string, unknown>;
  }
  if (artifact.type !== "table" || !Array.isArray(artifact.data)) return null;
  const columns = artifact.columns ?? [];
  const time = columns.filter(column => column.role === "time" && column.granularity);
  const measures = columns.filter(column => column.role === "measure");
  // Grouped and entity panels need an explicit series selection before plotting.
  if (time.length !== 1 || !measures.length || columns.some(column => column.role === "dimension" || column.role === "entity")) return null;
  return {
    rows: artifact.data,
    time_key: time[0].name,
    granularity: time[0].granularity,
    metric: measures[0].name,
    metric_ref: measures[0].ref,
    related: measures.slice(1).map(column => column.name),
  };
}
