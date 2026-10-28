"use client";

// Renders any Result by artifact shape, not by Method: tables for row lists, key/value
// grids for objects. A new Method's output shows up without a new component.

import { InspectorDialog } from "@/components/inspector-dialog";
import type { Artifact, Result, SemanticObject, Validation } from "@/lib/api";
import { timeSeriesData } from "@/lib/artifact-data";
import { isAssociation } from "@/lib/interpretation";
import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { type Translate, useT } from "@/lib/i18n";
import { populationLabel } from "@/lib/run-story";
import { RunQueries, RunSources } from "@/features/runs/run-evidence";
import styles from "./result-table.module.css";

type Titles = Map<string, SemanticObject>;

const labels: Record<string, string> = {
  value: "Group", metric: "Metric value", count: "Count", share_of_count: "Share of count (%)",
  vs_overall: "Compared with overall", rank: "Rank", current: "Analysis period", comparison: "Comparison period",
  change: "Change", change_pct: "Change (%)", period: "Period", before: "Before", after: "After",
  query: "Query", selected_among: "Eligible groups", excluded_small: "Groups below minimum count", drill_path: "Drill path",
  direction: "Sort direction", rank_by: "Ranked by", granularity: "Time unit",
  difference_from_subject: "Subject value − comparison group value",
  target: "Target group", difference: "Difference", raw: "Before matching", matched: "After matching",
  treatment: "Item to compare", conditions: "Matched conditions", path: "Analysis scope", units: "Sample size",
  target_units: "Target sample size", comparison_units: "Comparison sample size", target_retention: "Target sample retention",
  strata_common: "Condition combinations shared by both groups", excluded: "Excluded samples", target_without_comparison: "Targets with no comparison sample under the same conditions",
  comparison_without_target: "Comparison samples with no target under the same conditions", condition: "Condition combination",
  lower: "Lower bound", upper: "Upper bound", low: "Lower bound", high: "Upper bound", confidence: "Confidence level", p_value: "p-value",
  significant: "Statistically significant difference", same_value: "Same value", same_range: "Same range",
  member: "Item", title: "Name", match: "Matching method", edges: "Range boundaries", edges_source: "Range boundary source",
  target_matched_units: "Target samples included in the comparison", comparison_matched_units: "Comparison samples included in the comparison",
  strata_total: "Total condition combinations", imbalance_before: "Condition imbalance before matching", imbalance_after: "Condition imbalance after matching",
  target_missing_condition: "Target samples missing condition values", comparison_missing_condition: "Comparison samples missing condition values",
  thresholds: "Comparison thresholds", min_target_retention: "Minimum target sample retention", min_units_per_group: "Minimum sample per group", min_strata: "Minimum shared condition combinations",
  standard_error: "Standard error", ci95: "95% confidence interval", z: "Test statistic (z)", selection: "Multiple comparison correction",
  significant_after_selection: "Significant after multiple comparison correction", adjusted_critical_z: "Adjusted critical value (z)",
};
const artifactNames: Record<string, string> = { estimate: "Comparison result", interval: "Confidence interval of the difference", balance: "Comparison samples and condition balance", sample_summary: "Sample summary", table: "Detailed data", time_series: "Values by period", breakdown_table: "Values by group", warning: "Cautions for interpretation" };
const label = (key: string, t: Translate) => labels[key] ? t(labels[key]) : key.replaceAll("_", " ");
const labelFor = (key: string, titles: Titles, t: Translate) => {
  if (titles.has(key)) return titles.get(key)!.title;
  if (key.endsWith("#units")) return t("{metric} count", { metric: titles.get(key.slice(0, -6))?.title ?? t("metric") });
  if (/^[a-z][a-z0-9_-]*:\/\//.test(key)) return t("Metric value");
  if (key.includes(".")) return key.split(".").map(part => label(part, t)).join(" · ");
  return label(key, t);
};

function fmt(v: unknown, titles: Titles, t: Translate): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  if (typeof v === "string") return titles.get(v)?.title ?? (/^[a-z][a-z0-9_-]*:\/\/[^/]+\/[^/]+\/[^/]+$/.test(v) ? t("Name needs checking") : v);
  if (typeof v === "boolean") return t(v ? "Yes" : "No");
  if (Array.isArray(v) && v.every((x) => typeof x !== "object" || x === null)) return v.length ? v.map((x) => fmt(x, titles, t)).join(" ~ ") : t("None");
  if (Array.isArray(v)) return v.map(item => fmt(item, titles, t)).join(" · ");
  if (typeof v === "object") return Object.entries(v).map(([key, value]) => `${labelFor(key, titles, t)}: ${fmt(value, titles, t)}`).join(" · ");
  return String(v);
}

function isRowList(v: unknown): v is Record<string, unknown>[] {
  return Array.isArray(v) && v.length > 0 && v.every((r) => r && typeof r === "object" && !Array.isArray(r));
}

function flatten(row: Record<string, unknown>, prefix = ""): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v) && Object.keys(v).length <= 6) Object.assign(out, flatten(v as Record<string, unknown>, key));
    else out[key] = v;
  }
  return out;
}

export function DataTable({ rows, titles, columns, columnLabels }: { rows: Record<string, unknown>[]; titles: Titles; columns?: string[]; columnLabels?: Record<string, string> }) {
  const t = useT();
  const [page, setPage] = useState(0);
  const flat = rows.map((r) => flatten(r));
  const cols = (columns ?? [...new Set(flat.flatMap((r) => Object.keys(r)))]).filter(c => flat.some(r => r[c] != null));
  const numeric = new Set(cols.filter(c => flat.some(r => typeof r[c] === "number") && flat.every(r => r[c] == null || typeof r[c] === "number")));
  const pageSize = 12;
  const lastPage = Math.max(0, Math.ceil(flat.length / pageSize) - 1);
  const currentPage = Math.min(page, lastPage);
  const visible = flat.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  return (
    <div className={styles.container}>
      <div className={styles.scroll} tabIndex={0} role="region" aria-label={t("Result data table")}>
      <table className={styles.table}>
        <thead><tr>{cols.map((c) => <th scope="col" key={c} className={numeric.has(c) ? styles.numeric : ""}>{columnLabels?.[c] ?? labelFor(c, titles, t)}</th>)}</tr></thead>
        <tbody>
          {visible.map((r, i) => (
            <tr key={i}>{cols.map((c) => <td key={c} className={numeric.has(c) ? styles.numeric : ""}>{fmt(r[c], titles, t)}</td>)}</tr>
          ))}
        </tbody>
      </table>
      </div>
      {lastPage > 0 && <div className={styles.pagination}><span aria-live="polite">{t("{from}–{to} / {total} rows", { from: currentPage * pageSize + 1, to: Math.min((currentPage + 1) * pageSize, flat.length), total: flat.length })}</span><div>
        <button type="button" aria-label={t("Previous rows")} title={t("Previous rows")} disabled={!currentPage} onClick={() => setPage(currentPage - 1)}><ChevronLeft size={16} /></button>
        <button type="button" aria-label={t("Next rows")} title={t("Next rows")} disabled={currentPage === lastPage} onClick={() => setPage(currentPage + 1)}><ChevronRight size={16} /></button>
      </div></div>}
    </div>
  );
}

function Value({ value, titles, depth = 0 }: { value: unknown; titles: Titles; depth?: number }) {
  const t = useT();
  if (isRowList(value)) return <DataTable rows={value} titles={titles} />;
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const entries = Object.entries(value as Record<string, unknown>);
    const tables = entries.filter(([, v]) => isRowList(v));
    const scalars = entries.filter(([, v]) => !isRowList(v));
    return (
      <div>
        {scalars.length > 0 && (
          <dl className={depth ? "kv nested" : "kv"}>
            {scalars.map(([k, v]) => (
              <div key={k} className="kvrow">
                <dt>{labelFor(k, titles, t)}</dt>
                <dd>{v && typeof v === "object" && !Array.isArray(v) ? <Value value={v} titles={titles} depth={depth + 1} /> : typeof v === "number" && ["target_retention", "min_target_retention"].includes(k) ? `${(v * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}%` : fmt(v, titles, t)}</dd>
              </div>
            ))}
          </dl>
        )}
        {tables.map(([k, v]) => (
          <div key={k}><div className="subhead">{labelFor(k, titles, t)}</div><Value value={v} titles={titles} depth={depth + 1} /></div>
        ))}
      </div>
    );
  }
  return <span>{fmt(value, titles, t)}</span>;
}

export function ArtifactView({ artifact, titles, expanded = false, showTitle = true }: { artifact: Artifact; titles: Titles; expanded?: boolean; showTitle?: boolean }) {
  const t = useT();
  const [fullOpen, setFullOpen] = useState(false);
  if (artifact.type === "estimate" && artifact.data && typeof artifact.data === "object") {
    const data = artifact.data as Record<string, unknown>;
    if (data.raw && data.matched && typeof data.raw === "object" && typeof data.matched === "object") {
      const groupLabel = (value: unknown, fallback: string) => value && typeof value === "object" && typeof (value as Record<string, unknown>).label === "string" ? String((value as Record<string, unknown>).label) : fallback;
      const rows = ["raw", "matched"].map(key => ({ stage: label(key, t), ...(data[key] as Record<string, unknown>) }));
      return <section className="artifact">{showTitle && <h4>{typeof data.metric === "string" ? titles.get(data.metric)?.title ?? t("Analysis metric") : t("Comparison result")}</h4>}
        <DataTable rows={rows} titles={titles} columns={["stage", "target", "comparison", "difference"]} columnLabels={{ stage: t("Comparison method"), target: groupLabel(data.target, t("Target group")), comparison: groupLabel(data.comparison, t("Comparison group")), difference: t("Target − comparison group") }} />
        {Array.isArray(data.conditions) && data.conditions.length > 0 && <p className="result-note">{t("Matched conditions: {conditions}", { conditions: data.conditions.map(item => item.title ?? titles.get(item.member)?.title ?? t("Item name needs checking")).join(" · ") })}</p>}
      </section>;
    }
  }
  const series = timeSeriesData(artifact);
  if (series) {
    const data = series;
    const rows = Array.isArray(data.rows) ? data.rows.filter((row): row is Record<string, unknown> => !!row && typeof row === "object" && !Array.isArray(row)) : [];
    const metric = typeof data.metric === "string" ? data.metric : "";
    const metricTitle = titles.get(typeof data.metric_ref === "string" ? data.metric_ref : metric)?.title ?? t("metric");
    const units = data.units && typeof data.units === "object" ? data.units as Record<string, unknown> : {};
    const columns = rows.length ? Object.keys(rows[0]) : [];
    const columnLabels = Object.fromEntries(columns.filter((column) => column.endsWith("#units")).map((column) => {
      const unitRef = units[column.slice(0, -6)];
      return [column, typeof unitRef === "string" ? titles.get(unitRef)?.title ?? t("Count") : t("Count")];
    }));
    return <section className="artifact">{showTitle && <h4>{metricTitle} · {t("Values by period")}</h4>}
      {!expanded && rows.length === 1 && typeof rows[0][metric] === "number" && <p className="result-lead">{t("Value for the period")} <strong>{fmt(rows[0][metric], titles, t)}</strong></p>}
      {rows.length === 1 && <p className="result-note">{t("There is only one period, so no upward or downward trend can be judged.")}</p>}
      {rows.length ? <DataTable rows={rows} titles={titles} columns={columns} columnLabels={columnLabels} /> : <p className="result-note">{t("No period data to show.")}</p>}
    </section>;
  }
  if (artifact.type === "breakdown_table" && artifact.data && typeof artifact.data === "object") {
    const data = artifact.data as Record<string, unknown>;
    const rows = data.rows;
    const populationComparison = data.benchmark_aggregation === "semantic_provider";
    const displayedRows = populationComparison && isRowList(rows) ? rows.map((row, index) => ({ ...row,
      value: populationLabel(index, row.value, t) })) : rows;
    if (isRowList(displayedRows)) return <section className="artifact">
      {showTitle && <h4>{artifact.title || (artifactNames[artifact.type] ? t(artifactNames[artifact.type]) : artifact.type)}</h4>}
      {populationComparison && <div className="result-note"><p><strong>{t("Comparison basis")}</strong> {t("Each value uses the metric definition for the whole group, not an average of member values.")}</p><p>{t("Only peers use the selected conditions. Both groups exclude the subject and keep shared filters and dates.")}</p>{data.statistical_judgement === "not_tested" && <p><strong>{t("Numeric comparison only")}</strong> {t("No significance or causality test is performed, even with sample counts.")}</p>}</div>}
      <DataTable rows={displayedRows} titles={titles} columns={["value", "metric", "count", "share_of_count", "difference_from_subject"].filter((key) => key in displayedRows[0])} />
      {!expanded && <><button type="button" className="ghost" onClick={() => setFullOpen(true)}>{t("View full result")}</button><InspectorDialog title={t("Full analysis result")} open={fullOpen} onClose={() => setFullOpen(false)}><Value value={data} titles={titles} /></InspectorDialog></>}
    </section>;
  }
  return (
    <section className="artifact">
      {showTitle && <h4>{artifact.title || (artifactNames[artifact.type] ? t(artifactNames[artifact.type]) : artifact.type)}</h4>}
      <Value value={artifact.data} titles={titles} />
    </section>
  );
}

export function ValidationList({ items }: { items: Validation[] }) {
  const t = useT();
  const important = items.filter((item) => item.status !== "pass");
  if (!important.length) return null;
  return (
    <ul className="validation">
      {important.map((v, i) => (
        <li key={i} className={v.status}><b>{(name => name ? t(name) : v.validator.replaceAll("_", " "))(({ freshness: "Data freshness", complete_period: "Analysis period", non_empty: "Data present", min_count: "Sample size", overlap: "Group comparability" } as Record<string, string>)[v.validator])}</b> {v.code === "DATA_STALE" && typeof v.details?.latest === "string" && typeof v.details?.end === "string"
          ? t("Data ends on {latest}; results through {end} may be incomplete.", { latest: v.details.latest, end: v.details.end }) : v.message}</li>
      ))}
    </ul>
  );
}

export function ResultView({ result, titles, showRunLink = true, showEvidence = true, expanded = false, showPrimaryTitle = true }: { result: Result; titles: Titles; showRunLink?: boolean; showEvidence?: boolean; expanded?: boolean; showPrimaryTitle?: boolean }) {
  const t = useT();
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [additionalOpen, setAdditionalOpen] = useState(false);
  const statusLabel = t({ success: "Analysis complete", needs_input: "More input needed", refused: "Not comparable", failed: "Failed" }[result.status]);
  const breakdown = result.primary?.type === "breakdown_table" && result.primary.data && typeof result.primary.data === "object"
    ? (result.primary.data as Record<string, unknown>) : null;
  const leading = breakdown && isRowList(breakdown.rows) ? breakdown.rows[0] : null;
  const supportingArtifacts = result.artifacts.filter((artifact) => !Array.isArray(artifact.data) || artifact.data.length > 0);
  return (
    <div className="result">
      {(result.status !== "success" || (showRunLink && result.run_id)) && <div className="row">
        {result.status !== "success" && <span className={`status ${result.status}`}>{statusLabel}</span>}
        {showRunLink && result.run_id && <a href={`/runs/${result.run_id}`}>{t("Open run")}</a>}
      </div>}
      {!expanded && leading && <p className="result-lead">{t(breakdown?.subject ? "Comparison subject" : "Top group")} <strong>{fmt(leading.value, titles, t)}</strong>{leading.metric != null && <span> · {t("Metric value")} {fmt(leading.metric, titles, t)}</span>}</p>}
      {result.needs_input && (
        <div className="notice">
          <b>{result.needs_input.question}</b> <span className="muted">({result.needs_input.field})</span>
          <ul>{result.needs_input.candidates.map((c, i) => (
            <li key={i}>{c.label}{c.count !== undefined ? ` — ${c.count.toLocaleString()}` : ""} <code>{JSON.stringify(c.value)}</code></li>
          ))}</ul>
          <div className="hint">{t("Set {field} to one of these values and rerun.", { field: result.needs_input.field })}</div>
        </div>
      )}
      {!expanded && result.warnings.length > 0 && <ul className="warnings">{result.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
      {!expanded && <ValidationList items={result.validation} />}
      {result.primary && <ArtifactView artifact={result.primary} titles={titles} expanded={expanded} showTitle={showPrimaryTitle} />}
      {!expanded && supportingArtifacts.length > 0 && <><button type="button" className="ghost" onClick={() => setAdditionalOpen(true)}>{t("Additional analysis results")} ({supportingArtifacts.length})</button><InspectorDialog title={t("Additional analysis results")} open={additionalOpen} onClose={() => setAdditionalOpen(false)}>
        {supportingArtifacts.map((a, i) => <ArtifactView key={i} artifact={a} titles={titles} />)}
      </InspectorDialog></>}
      {showEvidence && (result.provenance.method || result.provenance.semantic_refs.length || result.provenance.queries.length) ? <><button type="button" className="ghost" onClick={() => setEvidenceOpen(true)}>{t("Execution evidence")}{result.provenance.queries.length > 0 ? ` / ${t("{n} queries", { n: result.provenance.queries.length })}` : ""}</button><InspectorDialog title={t("Execution evidence")} open={evidenceOpen} onClose={() => setEvidenceOpen(false)}>
        {result.interpretation && <p className="muted">{t("Interpretation scope: {scope}", { scope: isAssociation(result.interpretation) ? t("Association — observational summaries and relationships") : result.interpretation })}</p>}
        {result.validation.filter((item) => item.status === "pass").length > 0 && <p className="muted">{t("Passed validation:")} {result.validation.filter((item) => item.status === "pass").map((item) => item.validator).join(", ")}</p>}
        <RunSources result={result} titles={titles} />
        <RunQueries result={result} />
      </InspectorDialog></> : null}
    </div>
  );
}
