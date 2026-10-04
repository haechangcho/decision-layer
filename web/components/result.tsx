"use client";

// Renders any Result by artifact shape, not by Method: tables for row lists, key/value
// grids for objects. A new Method's output shows up without a new component.

import type { Artifact, Result, SemanticObject, Validation } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { RunQueries, RunSources } from "./run-evidence";

type Titles = Map<string, SemanticObject>;

const labels: Record<string, string> = {
  value: "그룹", metric: "지표 값", count: "건수", share_of_count: "건수 비중 (%)",
  vs_overall: "전체 대비", rank: "순위", current: "분석 기간", comparison: "비교 기간",
  change: "변화", change_pct: "변화율 (%)", period: "기간", before: "이전", after: "이후",
  selected_among: "비교 대상 그룹", excluded_small: "최소 건수 미만 그룹", drill_path: "드릴다운 경로",
  direction: "정렬 방향", rank_by: "정렬 기준", granularity: "시간 단위",
  difference_from_subject: "대상 값 − 비교 집단 값",
};
const labelFor = (key: string, titles: Titles) => {
  if (titles.has(key)) return titles.get(key)!.title;
  if (key.endsWith("#units")) return `${titles.get(key.slice(0, -6))?.title ?? "지표"} 건수`;
  if (key.startsWith("cube://")) return "지표 값";
  return labels[key] ?? key.replaceAll("_", " ");
};

function fmt(v: unknown, titles: Titles): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  if (typeof v === "string") return titles.get(v)?.title ?? (v.startsWith("cube://") ? "이름 확인 필요" : v);
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

export function DataTable({ rows, titles, columns, columnLabels }: { rows: Record<string, unknown>[]; titles: Titles; columns?: string[]; columnLabels?: Record<string, string> }) {
  const t = useT();
  const flat = rows.map((r) => flatten(r));
  const cols = columns ?? [...new Set(flat.flatMap((r) => Object.keys(r)))];
  return (
    <div className="scroll">
      <table>
        <thead><tr>{cols.map((c) => <th key={c}>{columnLabels?.[c] ?? t(labelFor(c, titles))}</th>)}</tr></thead>
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
                <dt>{t(labelFor(k, titles))}</dt>
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

export function ArtifactView({ artifact, titles, expanded = false }: { artifact: Artifact; titles: Titles; expanded?: boolean }) {
  if (artifact.type === "time_series" && artifact.data && typeof artifact.data === "object") {
    const data = artifact.data as Record<string, unknown>;
    const rows = Array.isArray(data.rows) ? data.rows.filter((row): row is Record<string, unknown> => !!row && typeof row === "object" && !Array.isArray(row)) : [];
    const metric = typeof data.metric === "string" ? data.metric : "";
    const metricTitle = titles.get(metric)?.title ?? "지표";
    const units = data.units && typeof data.units === "object" ? data.units as Record<string, unknown> : {};
    const columns = rows.length ? Object.keys(rows[0]) : [];
    const columnLabels = Object.fromEntries(columns.filter((column) => column.endsWith("#units")).map((column) => {
      const unitRef = units[column.slice(0, -6)];
      return [column, typeof unitRef === "string" ? titles.get(unitRef)?.title ?? "건수" : "건수"];
    }));
    return <section className="artifact"><h4>{metricTitle} · 기간별 값</h4>
      {!expanded && rows.length === 1 && typeof rows[0][metric] === "number" && <p className="result-lead">해당 기간 값 <strong>{fmt(rows[0][metric], titles)}</strong></p>}
      {rows.length === 1 && <p className="result-note">기간이 하나뿐이라 증가·감소 추이는 판단할 수 없습니다.</p>}
      {rows.length ? <DataTable rows={rows} titles={titles} columns={columns} columnLabels={columnLabels} /> : <p className="result-note">표시할 기간 데이터가 없습니다.</p>}
    </section>;
  }
  if (artifact.type === "breakdown_table" && artifact.data && typeof artifact.data === "object") {
    const data = artifact.data as Record<string, unknown>;
    const rows = data.rows;
    if (isRowList(rows)) return <section className="artifact">
      <h4>{artifact.title || artifact.type}</h4>
      <DataTable rows={rows} titles={titles} columns={["value", "metric", "count", "share_of_count", "difference_from_subject"].filter((key) => key in rows[0])} />
      {!expanded && <details className="artifact-details"><summary>전체 결과 보기</summary><Value value={data} titles={titles} /></details>}
    </section>;
  }
  return (
    <section className="artifact">
      <h4>{artifact.title || artifact.type}</h4>
      <Value value={artifact.data} titles={titles} />
    </section>
  );
}

export function ValidationList({ items }: { items: Validation[] }) {
  const important = items.filter((item) => item.status !== "pass");
  if (!important.length) return null;
  return (
    <ul className="validation">
      {important.map((v, i) => (
        <li key={i} className={v.status}><b>{({ freshness: "데이터 최신성", complete_period: "분석 기간", non_empty: "데이터 유무", min_count: "표본 수", overlap: "집단 비교 가능성" } as Record<string, string>)[v.validator] ?? v.validator.replaceAll("_", " ")}</b> {v.code === "DATA_STALE" && typeof v.details?.latest === "string" && typeof v.details?.end === "string"
          ? `데이터가 ${v.details.latest}까지만 있어 선택한 종료일(${v.details.end})까지의 결과가 불완전할 수 있습니다.` : v.message}</li>
      ))}
    </ul>
  );
}

export function ResultView({ result, titles, showRunLink = true, showEvidence = true, expanded = false }: { result: Result; titles: Titles; showRunLink?: boolean; showEvidence?: boolean; expanded?: boolean }) {
  const t = useT();
  const statusLabel = { success: "분석 완료", needs_input: "추가 입력 필요", refused: "비교 불가", failed: "실패" }[result.status];
  const breakdown = result.primary?.type === "breakdown_table" && result.primary.data && typeof result.primary.data === "object"
    ? (result.primary.data as Record<string, unknown>) : null;
  const leading = breakdown && isRowList(breakdown.rows) ? breakdown.rows[0] : null;
  const supportingArtifacts = result.artifacts.filter((artifact) => !Array.isArray(artifact.data) || artifact.data.length > 0);
  return (
    <div className="result">
      <div className="row">
        <span className={`status ${result.status}`}>{statusLabel}</span>
        {showRunLink && result.run_id && <a href={`/runs/${result.run_id}`}>{t("Open run")}</a>}
      </div>
      {!expanded && leading && <p className="result-lead">{breakdown?.subject ? "비교 대상" : "대표 그룹"} <strong>{fmt(leading.value, titles)}</strong>{leading.metric != null && <span> · 지표 값 {fmt(leading.metric, titles)}</span>}</p>}
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
      {!expanded && <ValidationList items={result.validation} />}
      {result.primary && <ArtifactView artifact={result.primary} titles={titles} expanded={expanded} />}
      {!expanded && supportingArtifacts.length > 0 && <details className="artifact-details">
        <summary>추가 분석 결과</summary>
        {supportingArtifacts.map((a, i) => <ArtifactView key={i} artifact={a} titles={titles} />)}
      </details>}
      {showEvidence && (result.provenance.method || result.provenance.semantic_refs.length || result.provenance.queries.length) ? <details>
        <summary>실행 근거{result.provenance.queries.length > 0 ? ` · 쿼리 ${result.provenance.queries.length}개` : ""}</summary>
        {result.interpretation && <p className="muted">해석 범위: {result.interpretation === "descriptive" ? "기술 분석" : result.interpretation}</p>}
        {result.validation.filter((item) => item.status === "pass").length > 0 && <p className="muted">통과한 검증: {result.validation.filter((item) => item.status === "pass").map((item) => item.validator).join(", ")}</p>}
        <RunSources result={result} titles={titles} />
        <RunQueries result={result} />
      </details> : null}
    </div>
  );
}
