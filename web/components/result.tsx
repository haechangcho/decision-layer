"use client";

// Renders any Result by artifact shape, not by Method: tables for row lists, key/value
// grids for objects. A new Method's output shows up without a new component.

import { useState } from "react";

import type { Artifact, Result, SemanticObject, Validation } from "@/lib/api";
import { useT } from "@/lib/i18n";

type Titles = Map<string, SemanticObject>;

function fmt(v: unknown, titles: Titles): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  if (typeof v === "string") return titles.get(v)?.title ?? v;
  if (typeof v === "boolean") return v ? "true" : "false";
  if (Array.isArray(v) && v.every((x) => typeof x !== "object" || x === null)) return v.map((x) => fmt(x, titles)).join(" ~ ");
  return JSON.stringify(v);
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

export function DataTable({ rows, titles }: { rows: Record<string, unknown>[]; titles: Titles }) {
  const flat = rows.map((r) => flatten(r));
  const cols = [...new Set(flat.flatMap((r) => Object.keys(r)))];
  return (
    <div className="scroll">
      <table>
        <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {flat.map((r, i) => (
            <tr key={i}>{cols.map((c) => <td key={c} className={typeof r[c] === "number" ? "num" : ""}>{fmt(r[c], titles)}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Value({ value, titles, depth = 0 }: { value: unknown; titles: Titles; depth?: number }) {
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
                <dt>{k}</dt>
                <dd>{v && typeof v === "object" && !Array.isArray(v) ? <Value value={v} titles={titles} depth={depth + 1} /> : fmt(v, titles)}</dd>
              </div>
            ))}
          </dl>
        )}
        {tables.map(([k, v]) => (
          <div key={k}><div className="subhead">{k}</div><Value value={v} titles={titles} depth={depth + 1} /></div>
        ))}
      </div>
    );
  }
  return <span>{fmt(value, titles)}</span>;
}

export function ArtifactView({ artifact, titles }: { artifact: Artifact; titles: Titles }) {
  return (
    <section className="artifact">
      <h4>{artifact.title || artifact.type} <span className="tag">{artifact.type}</span></h4>
      <Value value={artifact.data} titles={titles} />
    </section>
  );
}

export function ValidationList({ items }: { items: Validation[] }) {
  if (!items.length) return null;
  return (
    <ul className="validation">
      {items.map((v, i) => (
        <li key={i} className={v.status}><b>{v.validator}</b> {v.message}</li>
      ))}
    </ul>
  );
}

export function ResultView({ result, titles }: { result: Result; titles: Titles }) {
  const [showQueries, setShowQueries] = useState(false);
  const t = useT();
  return (
    <div className="result">
      <div className="row">
        <span className={`status ${result.status}`}>{result.status}</span>
        {result.interpretation && <span className="tag">{t("Interpretation: {level}", { level: result.interpretation })}</span>}
        {result.provenance.method && <span className="muted">{result.provenance.method}</span>}
        {result.run_id && <a href={`/runs/${result.run_id}`}>{result.run_id}</a>}
      </div>
      {result.needs_input && (
        <div className="notice">
          <b>{result.needs_input.question}</b> <span className="muted">({result.needs_input.field})</span>
          <ul>{result.needs_input.candidates.map((c, i) => (
            <li key={i}>{c.label}{c.count !== undefined ? ` — ${c.count.toLocaleString()}` : ""} <code>{JSON.stringify(c.value)}</code></li>
          ))}</ul>
          <div className="hint">{t("Put one of these values into the {field} parameter and run again.", { field: result.needs_input.field })}</div>
        </div>
      )}
      {result.warnings.length > 0 && <ul className="warnings">{result.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
      <ValidationList items={result.validation} />
      {result.primary && <ArtifactView artifact={result.primary} titles={titles} />}
      {result.artifacts.map((a, i) => <ArtifactView key={i} artifact={a} titles={titles} />)}
      <button className="ghost" onClick={() => setShowQueries(!showQueries)}>
        {t(showQueries ? "Hide {n} executed queries" : "Show {n} executed queries", { n: result.provenance.queries.length })}
      </button>
      {showQueries && <pre>{JSON.stringify(result.provenance.queries.map((q) => q.native_query), null, 2)}</pre>}
    </div>
  );
}
