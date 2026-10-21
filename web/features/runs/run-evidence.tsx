"use client";

import { useRef, useState } from "react";
import { Check, Copy, FileCode2, X } from "lucide-react";
import type { ExecutionAuthor, MethodManifest, Result, Run, SemanticObject } from "@/lib/api";
import { type Translate, useT } from "@/lib/i18n";
import { methodName } from "@/lib/method-name";
import { sourceLabel } from "@/features/recipes/step-input-source";
import s from "./run-evidence.module.css";

type Titles = Map<string, SemanticObject>;
const names: Record<string, string> = {
  metric: "Analysis metric", dimensions: "Dimensions to break down by", related: "Related metrics", conditions: "Comparison conditions",
  granularity: "Time unit", vs_previous: "Compare with previous period", top_n: "Groups to show", min_count: "Minimum group count",
  rank_by: "Ranked by", direction: "Sort direction", drill_path: "Selected scope", next_dimension: "Next breakdown dimension",
  current: "Analysis period", comparison: "Comparison period", subject: "Comparison subject", peers: "Peer group conditions",
  treatment: "Item to compare", target: "Target group", unit: "Analysis unit", ranges: "Condition ranges", selected_among: "Number of comparison candidates",
  treatment_measure: "Numeric item to compare", min_target_retention: "Minimum target sample retention", min_units_per_group: "Minimum sample per group",
};
const values: Record<string, string> = { month: "Month", week: "Week", day: "Day", quarter: "Quarter", year: "Year", desc: "Highest first", asc: "Lowest first", value: "Metric value", metric: "Metric value", change: "Amount of change", count: "Count" };
const sources = { method_default: "Method default", recipe: "Recipe setting", recipe_fixed: "Recipe fixed value", request: "Run request" };
const fieldName = (key: string, t: Translate) => names[key] ? t(names[key]) : key;

export function readableValue(value: unknown, titles: Titles, t: Translate): string {
  if (value == null) return t("Not configured");
  if (typeof value === "boolean") return t(value ? "Yes" : "No");
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "string") return titles.get(value)?.title ?? (/^[a-z][a-z0-9_-]*:\/\/[^/]+\/[^/]+\/[^/]+$/.test(value) ? t("Name needs checking") : values[value] ? t(values[value]) : value);
  if (Array.isArray(value)) return value.length ? value.map(item => readableValue(item, titles, t)).join(" · ") : t("None");
  if (typeof value === "object") {
    const item = value as Record<string, unknown>;
    if (typeof item.member === "string") {
      const operators: Record<string, string> = { equals: "=", notEquals: "≠", gt: ">", gte: "≥", lt: "<", lte: "≤", contains: t("contains"), notContains: t("does not contain"), set: t("has a value"), notSet: t("has no value"), inDateRange: t("within period"), notInDateRange: t("outside period"), beforeDate: t("before"), afterDate: t("after") };
      return `${readableValue(item.member, titles, t)} ${operators[String(item.operator)] ?? item.operator ?? "="} ${readableValue(item.value ?? item.values, titles, t)}`;
    }
    return Object.entries(item).map(([key, child]) => `${fieldName(key, t)}: ${readableValue(child, titles, t)}`).join(" · ");
  }
  return String(value);
}

export function RunSettings({ record, titles, manifest }: { record: Run["steps"][number]; titles: Titles; manifest?: MethodManifest }) {
  const t = useT();
  const params = Object.entries(record.step.params).filter(([, value]) => value != null && (!Array.isArray(value) || value.length));
  const data = record.result.primary?.data;
  const period = data && typeof data === "object" && !Array.isArray(data) ? (data as Record<string, unknown>).analysis_period as { date_range?: string[] | null; source?: string } | undefined : undefined;
  return <div className={s.settings}>
    {period && <section><h3>{t("Period actually queried")}</h3><dl><div><dt>{t("Applied period")}</dt><dd>{period.date_range?.join(" ~ ") ?? t("All periods")}<small>{t(period.source === "method_parameters" ? "Step setting" : "Run shared period")}</small></dd></div></dl></section>}
    <section><h3>{t("Inputs used in the analysis")}</h3><dl>{Object.entries(record.step.bindings).map(([name, value]) => <div key={name}><dt>{fieldName(name, t)}</dt><dd>{readableValue(value, titles, t)}</dd></div>)}</dl></section>
    <section><h3>{t("Options applied")}</h3><dl>{params.map(([name, value]) => <div key={name}><dt>{manifest?.parameters[name]?.type === "group" ? t(name === "target" ? "Target group" : "Comparison group") : names[name] ? t(names[name]) : name.replaceAll("_", " ")}</dt><dd><span>{name === "min_target_retention" && typeof value === "number" ? `${value * 100}%` : readableValue(value, titles, t)}</span><small>{t(record.parameter_sources?.[name] ? sources[record.parameter_sources[name]] : "No origin recorded")}</small></dd></div>)}</dl></section>
    {!!record.input_resolutions?.length && <section><h3>{t("Values selected in this run")}</h3><dl>{record.input_resolutions.map((item, index) => <div key={index}><dt>{names[item.field.split(".").at(-1) ?? ""] ? t(names[item.field.split(".").at(-1)!]) : item.field}</dt><dd><span>{sourceLabel(item.source, t)}</span><strong>{readableValue(item.resolved, titles, t)}</strong></dd></div>)}</dl></section>}
    {!params.length && <p className={s.muted}>{t("No additional settings were recorded.")}</p>}
  </div>;
}

export function AuthorInfo({ author, label }: { author?: ExecutionAuthor | null; label: string }) {
  const t = useT();
  const source = { protocol: "Reported via MCP", client_reported: "Self-reported by the client", runner: "Reported by the runner" };
  return <section className={s.author}><h3>{label}</h3><dl>
    <div><dt>{t("Product")}</dt><dd>{author?.client_name || t("Not provided")}{author?.client_version && ` · ${author.client_version}`}{author?.client_name && <small>{t(source[author.client_source ?? "client_reported"])}</small>}</dd></div>
    <div><dt>{t("AI model")}</dt><dd>{[author?.model_provider, author?.model_id].filter(Boolean).join(" · ") || t("Not provided")}{author?.model_id && <small>{t(source[author.model_source ?? "client_reported"])}</small>}</dd></div>
    {author?.model_revision && <div><dt>{t("Model revision")}</dt><dd>{author.model_revision}</dd></div>}
  </dl></section>;
}

export function RunSources({ result, titles, author }: { result: Result; titles: Titles; author?: ExecutionAuthor | null }) {
  const t = useT();
  const dialog = useRef<HTMLDialogElement>(null);
  const [rawOpen, setRawOpen] = useState(false);
  const reference = result.provenance.method ?? "";
  const [method, version] = reference.replace("method://", "").split("@");
  const label = methodName(method.replaceAll("/", "."), t);
  const kinds: Record<string, string> = { measure: "metric", dimension: "category", time_dimension: "Date dimension" };
  const connections = [...new Set(result.provenance.semantic_refs.map(ref => ref.split("://")[0]))];
  return <div className={s.sources}>
    <section className={s.sourceSection}><h3>{t("Method used")}</h3>
    {reference && <div className={s.method}><strong>{label}</strong><small>v{version || t("not recorded")}</small></div>}
    </section>
    <section className={s.sourceSection}><h3>{t("Data used")}{connections.length > 0 && <small>{connections.join(", ")}</small>}</h3>
    <ul>{result.provenance.semantic_refs.map(ref => {
      const object = titles.get(ref);
      return <li key={ref}><span>{t(object ? kinds[object.kind] ?? "Reference" : "Reference")}</span><div><strong>{object?.title ?? t("Data name needs checking")}</strong>{object?.description && <small>{object.description}</small>}</div></li>;
    })}</ul>
    {!result.provenance.semantic_refs.length && <p className={s.muted}>{t("No data references were recorded.")}</p>}
    </section>
    <AuthorInfo author={author} label={t("Run request for this step")} />
    {result.provenance.runtime && Object.keys(result.provenance.runtime).length > 0 && <section className={s.author}><h3>{t("Analysis runtime")}</h3><dl>{Object.entries(result.provenance.runtime).map(([name, version]) => <div key={name}><dt>{name}</dt><dd>{version}</dd></div>)}</dl></section>}
    <button type="button" className={s.rawButton} onClick={() => { setRawOpen(true); dialog.current?.showModal(); }}><FileCode2 size={15} />{t("View raw record")}</button>
    <dialog ref={dialog} className={s.rawDialog} aria-label={t("Raw run record")} onClose={() => setRawOpen(false)}><header><h2>{t("Raw run record")}</h2><button type="button" aria-label={t("Close")} title={t("Close")} onClick={() => dialog.current?.close()}><X size={18} /></button></header>{rawOpen && <pre tabIndex={0}>{JSON.stringify(result, null, 2)}</pre>}</dialog>
  </div>;
}

export function RunQueries({ result }: { result: Result }) {
  const t = useT();
  const [copied, setCopied] = useState<number | null>(null);
  const [copyError, setCopyError] = useState(false);
  if (!result.provenance.queries.length) return <p className={s.muted}>{t("No queries were recorded for this run.")}</p>;
  return <div className={s.queries}>{result.provenance.queries.map((query, index) => {
    const text = typeof query.native_query === "string" ? query.native_query : JSON.stringify(query.native_query, null, 2);
    return <section key={index}><header><strong>{t("Query {number}", { number: index + 1 })}</strong><span>{t("{rows} rows returned", { rows: query.rows.toLocaleString() })} · {query.elapsed_ms >= 1000 ? t("{seconds} s", { seconds: (query.elapsed_ms / 1000).toLocaleString(undefined, { maximumFractionDigits: 2 }) }) : `${query.elapsed_ms.toLocaleString()} ms`}</span>
      <button type="button" title={t("Copy query")} aria-label={t("Copy query {number}", { number: index + 1 })} onClick={async () => { try { await navigator.clipboard.writeText(text); setCopied(index); setCopyError(false); } catch { setCopyError(true); } }}>{copied === index ? <Check size={16} /> : <Copy size={16} />}</button></header>
      <div className={s.queryContext}><span>{[query.provider, query.instance].filter(Boolean).join(" · ") || t("Provider not recorded")}</span><span>{t(query.compiled_sql ? "Provider request and executed SQL" : "Provider request as sent · SQL not provided")}</span></div><pre tabIndex={0} aria-label={t("Query {number} raw request", { number: index + 1 })}>{text}</pre>
      {query.compiled_sql != null && <section><h4>{t("Executed SQL")}</h4><pre tabIndex={0}>{typeof query.compiled_sql === "string" ? query.compiled_sql : JSON.stringify(query.compiled_sql, null, 2)}</pre></section>}
    </section>;
  })}{copyError && <p role="alert">{t("Copy failed. Select the query text and copy it.")}</p>}</div>;
}
