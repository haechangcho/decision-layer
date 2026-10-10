"use client";

// Renders any Result by artifact shape, not by Method: tables for row lists, key/value
// grids for objects. A new Method's output shows up without a new component.

import type { Artifact, Result, SemanticObject, Validation } from "@/lib/api";
import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useT } from "@/lib/i18n";
import { populationLabel } from "@/lib/run-story";
import { RunQueries, RunSources } from "./run-evidence";
import styles from "./result-table.module.css";

type Titles = Map<string, SemanticObject>;

const labels: Record<string, string> = {
  value: "그룹", metric: "지표 값", count: "건수", share_of_count: "건수 비중 (%)",
  vs_overall: "전체 대비", rank: "순위", current: "분석 기간", comparison: "비교 기간",
  change: "변화", change_pct: "변화율 (%)", period: "기간", before: "이전", after: "이후",
  selected_among: "비교 대상 그룹", excluded_small: "최소 건수 미만 그룹", drill_path: "드릴다운 경로",
  direction: "정렬 방향", rank_by: "정렬 기준", granularity: "시간 단위",
  difference_from_subject: "대상 값 − 비교 집단 값",
  target: "대상 집단", difference: "차이", raw: "조건 맞춤 전", matched: "조건 맞춤 후",
  treatment: "비교할 항목", conditions: "맞춘 조건", path: "분석 범위", units: "표본 수",
  target_units: "대상 표본 수", comparison_units: "비교 표본 수", target_retention: "대상 표본 유지 비율",
  strata_common: "두 집단에 공통인 조건 조합 수", excluded: "제외된 표본", target_without_comparison: "같은 조건의 비교 표본이 없는 대상",
  comparison_without_target: "같은 조건의 대상 표본이 없는 비교 표본", condition: "조건 조합",
  lower: "하한", upper: "상한", low: "하한", high: "상한", confidence: "신뢰 수준", p_value: "p값",
  significant: "통계적으로 유의한 차이", same_value: "같은 값", same_range: "같은 구간",
  member: "항목", title: "이름", match: "맞춤 방식", edges: "구간 경계", edges_source: "구간 설정 출처",
  target_matched_units: "비교에 포함된 대상 표본", comparison_matched_units: "비교에 포함된 비교 표본",
  strata_total: "전체 조건 조합 수", imbalance_before: "맞춤 전 조건 불균형", imbalance_after: "맞춤 후 조건 불균형",
  target_missing_condition: "조건 값이 없는 대상 표본", comparison_missing_condition: "조건 값이 없는 비교 표본",
  thresholds: "비교 허용 기준", min_target_retention: "최소 대상 표본 유지 비율", min_units_per_group: "집단별 최소 표본 수", min_strata: "최소 공통 조건 조합 수",
  standard_error: "표준 오차", ci95: "95% 신뢰구간", z: "검정 통계량 (z)", selection: "다중 비교 보정",
  significant_after_selection: "다중 비교 보정 후 유의함", adjusted_critical_z: "보정된 판정 기준 (z)",
};
const artifactNames: Record<string, string> = { estimate: "비교 결과", interval: "차이의 신뢰구간", balance: "비교 표본과 조건 일치", sample_summary: "표본 요약", table: "세부 데이터", time_series: "기간별 값", breakdown_table: "그룹별 값", warning: "해석 시 주의사항" };
const labelFor = (key: string, titles: Titles) => {
  if (titles.has(key)) return titles.get(key)!.title;
  if (key.endsWith("#units")) return `${titles.get(key.slice(0, -6))?.title ?? "지표"} 건수`;
  if (/^[a-z][a-z0-9_-]*:\/\//.test(key)) return "지표 값";
  if (key.includes(".")) return key.split(".").map(part => labels[part] ?? part.replaceAll("_", " ")).join(" · ");
  return labels[key] ?? key.replaceAll("_", " ");
};

function fmt(v: unknown, titles: Titles): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  if (typeof v === "string") return titles.get(v)?.title ?? (/^[a-z][a-z0-9_-]*:\/\/[^/]+\/[^/]+\/[^/]+$/.test(v) ? "이름 확인 필요" : v);
  if (typeof v === "boolean") return v ? "예" : "아니요";
  if (Array.isArray(v) && v.every((x) => typeof x !== "object" || x === null)) return v.length ? v.map((x) => fmt(x, titles)).join(" ~ ") : "없음";
  if (Array.isArray(v)) return v.map(item => fmt(item, titles)).join(" · ");
  if (typeof v === "object") return Object.entries(v).map(([key, value]) => `${labelFor(key, titles)}: ${fmt(value, titles)}`).join(" · ");
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
      <div className={styles.scroll} tabIndex={0} role="region" aria-label="결과 데이터 표">
      <table className={styles.table}>
        <thead><tr>{cols.map((c) => <th scope="col" key={c} className={numeric.has(c) ? styles.numeric : ""}>{columnLabels?.[c] ?? t(labelFor(c, titles))}</th>)}</tr></thead>
        <tbody>
          {visible.map((r, i) => (
            <tr key={i}>{cols.map((c) => <td key={c} className={numeric.has(c) ? styles.numeric : ""}>{fmt(r[c], titles)}</td>)}</tr>
          ))}
        </tbody>
      </table>
      </div>
      {lastPage > 0 && <div className={styles.pagination}><span aria-live="polite">{currentPage * pageSize + 1}–{Math.min((currentPage + 1) * pageSize, flat.length)} / {flat.length}행</span><div>
        <button type="button" aria-label="이전 행" title="이전 행" disabled={!currentPage} onClick={() => setPage(currentPage - 1)}><ChevronLeft size={16} /></button>
        <button type="button" aria-label="다음 행" title="다음 행" disabled={currentPage === lastPage} onClick={() => setPage(currentPage + 1)}><ChevronRight size={16} /></button>
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
                <dt>{t(labelFor(k, titles))}</dt>
                <dd>{v && typeof v === "object" && !Array.isArray(v) ? <Value value={v} titles={titles} depth={depth + 1} /> : typeof v === "number" && ["target_retention", "min_target_retention"].includes(k) ? `${(v * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}%` : fmt(v, titles)}</dd>
              </div>
            ))}
          </dl>
        )}
        {tables.map(([k, v]) => (
          <div key={k}><div className="subhead">{labelFor(k, titles)}</div><Value value={v} titles={titles} depth={depth + 1} /></div>
        ))}
      </div>
    );
  }
  return <span>{fmt(value, titles)}</span>;
}

export function ArtifactView({ artifact, titles, expanded = false }: { artifact: Artifact; titles: Titles; expanded?: boolean }) {
  if (artifact.type === "estimate" && artifact.data && typeof artifact.data === "object") {
    const data = artifact.data as Record<string, unknown>;
    if (data.raw && data.matched && typeof data.raw === "object" && typeof data.matched === "object") {
      const groupLabel = (value: unknown, fallback: string) => value && typeof value === "object" && typeof (value as Record<string, unknown>).label === "string" ? String((value as Record<string, unknown>).label) : fallback;
      const rows = ["raw", "matched"].map(key => ({ stage: labels[key], ...(data[key] as Record<string, unknown>) }));
      return <section className="artifact"><h4>{typeof data.metric === "string" ? titles.get(data.metric)?.title ?? "분석 지표" : "비교 결과"}</h4>
        <DataTable rows={rows} titles={titles} columns={["stage", "target", "comparison", "difference"]} columnLabels={{ stage: "비교 방식", target: groupLabel(data.target, "대상 집단"), comparison: groupLabel(data.comparison, "비교 집단"), difference: "대상 − 비교 집단" }} />
        {Array.isArray(data.conditions) && data.conditions.length > 0 && <p className="result-note">맞춘 조건: {data.conditions.map(item => item.title ?? titles.get(item.member)?.title ?? "항목 이름 확인 필요").join(" · ")}</p>}
      </section>;
    }
  }
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
    const populationComparison = data.benchmark_aggregation === "semantic_provider";
    const displayedRows = populationComparison && isRowList(rows) ? rows.map((row, index) => ({ ...row,
      value: populationLabel(index, row.value) })) : rows;
    if (isRowList(displayedRows)) return <section className="artifact">
      <h4>{artifact.title || artifactNames[artifact.type] || artifact.type}</h4>
      {populationComparison && <div className="result-note"><p><strong>비교 기준</strong> 각 집단 전체에 지표 정의를 적용한 값입니다. 구성원별 값의 단순 평균이 아닙니다.</p><p>비교 집단에는 지정한 조건을 적용하고, 전체 집단에는 그 조건을 적용하지 않습니다. 두 집단 모두 선택한 대상은 제외하며, 공통 필터와 실행 기간은 유지합니다.</p>{data.statistical_judgement === "not_tested" && <p><strong>수치 비교만 수행</strong> 차이의 통계적 유의성이나 원인 관계는 판단하지 않습니다. 표본 건수가 있더라도 이 Method는 유의성을 검정하지 않습니다.</p>}</div>}
      <DataTable rows={displayedRows} titles={titles} columns={["value", "metric", "count", "share_of_count", "difference_from_subject"].filter((key) => key in displayedRows[0])} />
      {!expanded && <details className="artifact-details"><summary>전체 결과 보기</summary><Value value={data} titles={titles} /></details>}
    </section>;
  }
  return (
    <section className="artifact">
      <h4>{artifact.title || artifactNames[artifact.type] || artifact.type}</h4>
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
      {(result.status !== "success" || (showRunLink && result.run_id)) && <div className="row">
        {result.status !== "success" && <span className={`status ${result.status}`}>{statusLabel}</span>}
        {showRunLink && result.run_id && <a href={`/runs/${result.run_id}`}>{t("Open run")}</a>}
      </div>}
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
      {!expanded && result.warnings.length > 0 && <ul className="warnings">{result.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
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
