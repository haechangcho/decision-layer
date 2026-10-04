"use client";

import { useRef, useState } from "react";
import { Check, Copy, FileCode2, X } from "lucide-react";
import type { Result, Run, SemanticObject } from "@/lib/api";
import { methodName } from "@/lib/method-name";
import s from "./run-evidence.module.css";

type Titles = Map<string, SemanticObject>;
const names: Record<string, string> = {
  metric: "분석 지표", dimensions: "나눠 볼 항목", related: "함께 볼 지표", conditions: "비교 조건",
  granularity: "시간 단위", vs_previous: "직전 기간 비교", top_n: "표시할 그룹 수", min_count: "최소 그룹 건수",
  rank_by: "정렬 기준", direction: "정렬 방향", drill_path: "선택한 범위", next_dimension: "다음 분류 항목",
  current: "분석 기간", comparison: "비교 기간", subject: "비교 대상", peers: "동료 집단 조건",
};
const values: Record<string, string> = { month: "월", week: "주", day: "일", quarter: "분기", year: "년", desc: "높은 순", asc: "낮은 순", value: "지표 값", metric: "지표 값", change: "변화량", count: "건수" };
const sources = { method_default: "Method 기본값", recipe: "Recipe 설정", recipe_fixed: "Recipe 고정값", request: "실행 요청" };

export function readableValue(value: unknown, titles: Titles): string {
  if (value == null) return "설정 안 함";
  if (typeof value === "boolean") return value ? "예" : "아니요";
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "string") return titles.get(value)?.title ?? (value.startsWith("cube://") ? "이름 확인 필요" : values[value] ?? value);
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

export function RunSettings({ record, titles }: { record: Run["steps"][number]; titles: Titles }) {
  const params = Object.entries(record.step.params).filter(([, value]) => value != null && (!Array.isArray(value) || value.length));
  return <div className={s.settings}>
    <dl>{Object.entries(record.step.bindings).map(([name, value]) => <div key={name}><dt>{names[name] ?? name}</dt><dd>{readableValue(value, titles)}</dd></div>)}</dl>
    <dl>{params.map(([name, value]) => <div key={name}><dt>{names[name] ?? name.replaceAll("_", " ")}</dt><dd><span>{readableValue(value, titles)}</span><small>{record.parameter_sources?.[name] ? sources[record.parameter_sources[name]] : "출처 기록 없음"}</small></dd></div>)}</dl>
    {!params.length && <p className={s.muted}>기록된 추가 설정이 없습니다.</p>}
  </div>;
}

export function RunSources({ result, titles }: { result: Result; titles: Titles }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [rawOpen, setRawOpen] = useState(false);
  const reference = result.provenance.method ?? "";
  const [method, version] = reference.replace("method://", "").split("@");
  const label = methodName(method.replaceAll("/", "."));
  const kinds: Record<string, string> = { measure: "지표", dimension: "분류", time_dimension: "날짜 기준" };
  return <div className={s.sources}>
    {reference && <div className={s.method}><span>분석 방법</span><strong>{label}</strong><small>v{version || "미기록"}</small></div>}
    <ul>{result.provenance.semantic_refs.map(ref => {
      const object = titles.get(ref);
      const parts = ref.replace("cube://", "").split("/");
      return <li key={ref}><span>{object ? kinds[object.kind] : "참조"}</span><div><strong>{object?.title ?? "이름 확인 필요"}</strong><small>{parts.slice(1).join(" / ")}</small></div><small>Cube · {parts[0]}</small></li>;
    })}</ul>
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
    return <section key={index}><header><strong>쿼리 {index + 1}</strong><span>{query.rows.toLocaleString()}행 · {query.elapsed_ms.toLocaleString()} ms</span>
      <button type="button" title="쿼리 복사" aria-label={`쿼리 ${index + 1} 복사`} onClick={async () => { try { await navigator.clipboard.writeText(text); setCopied(index); setCopyError(false); } catch { setCopyError(true); } }}>{copied === index ? <Check size={16} /> : <Copy size={16} />}</button></header>
      <pre tabIndex={0}>{text}</pre>
      {query.compiled_sql != null && <section><h4>실행 SQL</h4><pre tabIndex={0}>{typeof query.compiled_sql === "string" ? query.compiled_sql : JSON.stringify(query.compiled_sql, null, 2)}</pre></section>}
    </section>;
  })}{copyError && <p role="alert">복사하지 못했습니다. 쿼리 내용을 직접 선택해 복사하세요.</p>}</div>;
}
