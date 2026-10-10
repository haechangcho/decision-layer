"use client";

import { useRef, useState } from "react";
import { Check, Copy, FileCode2, X } from "lucide-react";
import type { ExecutionAuthor, MethodManifest, Result, Run, SemanticObject } from "@/lib/api";
import { methodName } from "@/lib/method-name";
import { sourceLabel } from "./step-input-source";
import s from "./run-evidence.module.css";

type Titles = Map<string, SemanticObject>;
const names: Record<string, string> = {
  metric: "분석 지표", dimensions: "나눠 볼 항목", related: "함께 볼 지표", conditions: "비교 조건",
  granularity: "시간 단위", vs_previous: "직전 기간 비교", top_n: "표시할 그룹 수", min_count: "최소 그룹 건수",
  rank_by: "정렬 기준", direction: "정렬 방향", drill_path: "선택한 범위", next_dimension: "다음 분류 항목",
  current: "분석 기간", comparison: "비교 기간", subject: "비교 대상", peers: "동료 집단 조건",
  treatment: "비교할 항목", target: "대상 집단", unit: "분석 단위", ranges: "조건 구간", selected_among: "비교 후보 수",
  treatment_measure: "비교할 수치 항목", min_target_retention: "최소 대상 표본 유지 비율", min_units_per_group: "집단별 최소 표본 수",
};
const values: Record<string, string> = { month: "월", week: "주", day: "일", quarter: "분기", year: "년", desc: "높은 순", asc: "낮은 순", value: "지표 값", metric: "지표 값", change: "변화량", count: "건수" };
const sources = { method_default: "Method 기본값", recipe: "Recipe 설정", recipe_fixed: "Recipe 고정값", request: "실행 요청" };

export function readableValue(value: unknown, titles: Titles): string {
  if (value == null) return "설정 안 함";
  if (typeof value === "boolean") return value ? "예" : "아니요";
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "string") return titles.get(value)?.title ?? (/^[a-z][a-z0-9_-]*:\/\/[^/]+\/[^/]+\/[^/]+$/.test(value) ? "이름 확인 필요" : values[value] ?? value);
  if (Array.isArray(value)) return value.length ? value.map(item => readableValue(item, titles)).join(" · ") : "없음";
  if (typeof value === "object") {
    const item = value as Record<string, unknown>;
    if (typeof item.member === "string") {
      const operators: Record<string, string> = { equals: "=", notEquals: "≠", gt: ">", gte: "≥", lt: "<", lte: "≤", contains: "포함", notContains: "미포함", set: "값 있음", notSet: "값 없음", inDateRange: "기간 내", notInDateRange: "기간 외", beforeDate: "이전", afterDate: "이후" };
      return `${readableValue(item.member, titles)} ${operators[String(item.operator)] ?? item.operator ?? "="} ${readableValue(item.value ?? item.values, titles)}`;
    }
    return Object.entries(item).map(([key, child]) => `${names[key] ?? key}: ${readableValue(child, titles)}`).join(" · ");
  }
  return String(value);
}

export function RunSettings({ record, titles, manifest }: { record: Run["steps"][number]; titles: Titles; manifest?: MethodManifest }) {
  const params = Object.entries(record.step.params).filter(([, value]) => value != null && (!Array.isArray(value) || value.length));
  const data = record.result.primary?.data;
  const period = data && typeof data === "object" && !Array.isArray(data) ? (data as Record<string, unknown>).analysis_period as { date_range?: string[] | null; source?: string } | undefined : undefined;
  return <div className={s.settings}>
    {period && <section><h3>실제 조회 기간</h3><dl><div><dt>적용 기간</dt><dd>{period.date_range?.join(" ~ ") ?? "전체 기간"}<small>{period.source === "method_parameters" ? "단계 설정" : "Run 공통 기간"}</small></dd></div></dl></section>}
    <section><h3>분석에 사용한 입력</h3><dl>{Object.entries(record.step.bindings).map(([name, value]) => <div key={name}><dt>{names[name] ?? name}</dt><dd>{readableValue(value, titles)}</dd></div>)}</dl></section>
    <section><h3>적용한 옵션</h3><dl>{params.map(([name, value]) => <div key={name}><dt>{manifest?.parameters[name]?.type === "group" ? name === "target" ? "대상 집단" : "비교 집단" : names[name] ?? name.replaceAll("_", " ")}</dt><dd><span>{name === "min_target_retention" && typeof value === "number" ? `${value * 100}%` : readableValue(value, titles)}</span><small>{record.parameter_sources?.[name] ? sources[record.parameter_sources[name]] : "출처 기록 없음"}</small></dd></div>)}</dl></section>
    {!!record.input_resolutions?.length && <section><h3>이번 실행에서 선택된 값</h3><dl>{record.input_resolutions.map((item, index) => <div key={index}><dt>{names[item.field.split(".").at(-1) ?? ""] ?? item.field}</dt><dd><span>{sourceLabel(item.source)}</span><strong>{readableValue(item.resolved, titles)}</strong></dd></div>)}</dl></section>}
    {!params.length && <p className={s.muted}>기록된 추가 설정이 없습니다.</p>}
  </div>;
}

export function AuthorInfo({ author, label }: { author?: ExecutionAuthor | null; label: string }) {
  const source = { protocol: "MCP 전달 정보", client_reported: "클라이언트 자기보고", runner: "실행 도구 전달 정보" };
  return <section className={s.author}><h3>{label}</h3><dl>
    <div><dt>사용 제품</dt><dd>{author?.client_name || "미제공"}{author?.client_version && ` · ${author.client_version}`}{author?.client_name && <small>{source[author.client_source ?? "client_reported"]}</small>}</dd></div>
    <div><dt>AI 모델</dt><dd>{[author?.model_provider, author?.model_id].filter(Boolean).join(" · ") || "미제공"}{author?.model_id && <small>{source[author.model_source ?? "client_reported"]}</small>}</dd></div>
    {author?.model_revision && <div><dt>모델 리비전</dt><dd>{author.model_revision}</dd></div>}
  </dl></section>;
}

export function RunSources({ result, titles, author }: { result: Result; titles: Titles; author?: ExecutionAuthor | null }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [rawOpen, setRawOpen] = useState(false);
  const reference = result.provenance.method ?? "";
  const [method, version] = reference.replace("method://", "").split("@");
  const label = methodName(method.replaceAll("/", "."));
  const kinds: Record<string, string> = { measure: "지표", dimension: "분류", time_dimension: "날짜 기준" };
  const connections = [...new Set(result.provenance.semantic_refs.map(ref => ref.split("://")[0]))];
  return <div className={s.sources}>
    <section className={s.sourceSection}><h3>사용한 분석 방법</h3>
    {reference && <div className={s.method}><strong>{label}</strong><small>v{version || "미기록"}</small></div>}
    </section>
    <section className={s.sourceSection}><h3>사용한 데이터{connections.length > 0 && <small>{connections.join(", ")}</small>}</h3>
    <ul>{result.provenance.semantic_refs.map(ref => {
      const object = titles.get(ref);
      return <li key={ref}><span>{object ? kinds[object.kind] ?? "참조" : "참조"}</span><div><strong>{object?.title ?? ref}</strong>{object?.description && <small>{object.description}</small>}</div></li>;
    })}</ul>
    {!result.provenance.semantic_refs.length && <p className={s.muted}>기록된 데이터 참조가 없습니다.</p>}
    </section>
    <AuthorInfo author={author} label="이 단계의 실행 요청" />
    {result.provenance.runtime && Object.keys(result.provenance.runtime).length > 0 && <section className={s.author}><h3>분석 실행 환경</h3><dl>{Object.entries(result.provenance.runtime).map(([name, version]) => <div key={name}><dt>{name}</dt><dd>{version}</dd></div>)}</dl></section>}
    <button type="button" className={s.rawButton} onClick={() => { setRawOpen(true); dialog.current?.showModal(); }}><FileCode2 size={15} />원본 기록 보기</button>
    <dialog ref={dialog} className={s.rawDialog} aria-label="원본 실행 기록" onClose={() => setRawOpen(false)}><header><h2>원본 실행 기록</h2><button type="button" aria-label="닫기" title="닫기" onClick={() => dialog.current?.close()}><X size={18} /></button></header>{rawOpen && <pre tabIndex={0}>{JSON.stringify(result, null, 2)}</pre>}</dialog>
  </div>;
}

export function RunQueries({ result }: { result: Result }) {
  const [copied, setCopied] = useState<number | null>(null);
  const [copyError, setCopyError] = useState(false);
  if (!result.provenance.queries.length) return <p className={s.muted}>이 실행에 기록된 쿼리가 없습니다.</p>;
  return <div className={s.queries}>{result.provenance.queries.map((query, index) => {
    const text = typeof query.native_query === "string" ? query.native_query : JSON.stringify(query.native_query, null, 2);
    return <section key={index}><header><strong>쿼리 {index + 1}</strong><span>반환 {query.rows.toLocaleString()}행 · {query.elapsed_ms >= 1000 ? `${(query.elapsed_ms / 1000).toLocaleString(undefined, { maximumFractionDigits: 2 })}초` : `${query.elapsed_ms.toLocaleString()} ms`}</span>
      <button type="button" title="쿼리 복사" aria-label={`쿼리 ${index + 1} 복사`} onClick={async () => { try { await navigator.clipboard.writeText(text); setCopied(index); setCopyError(false); } catch { setCopyError(true); } }}>{copied === index ? <Check size={16} /> : <Copy size={16} />}</button></header>
      <div className={s.queryContext}><span>{[query.provider, query.instance].filter(Boolean).join(" · ") || "제공자 정보 미기록"}</span><span>{query.compiled_sql ? "제공자 요청과 실행 SQL" : "실제로 전송한 제공자 요청 · SQL은 제공되지 않음"}</span></div><pre tabIndex={0} aria-label={`쿼리 ${index + 1} 원본 요청`}>{text}</pre>
      {query.compiled_sql != null && <section><h4>실행 SQL</h4><pre tabIndex={0}>{typeof query.compiled_sql === "string" ? query.compiled_sql : JSON.stringify(query.compiled_sql, null, 2)}</pre></section>}
    </section>;
  })}{copyError && <p role="alert">복사하지 못했습니다. 쿼리 내용을 직접 선택해 복사하세요.</p>}</div>;
}
