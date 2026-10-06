"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, History, RefreshCw, Search, X } from "lucide-react";

import type { Run } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { methodName } from "@/lib/method-name";
import { runOriginLabel } from "@/lib/run-origin";
import { RunDelete } from "@/components/run-delete";
import styles from "../library.module.css";

const displayName = (run: Run) => run.recipe_snapshot?.description || run.recipe_snapshot?.name || run.plan.recipe?.replace("recipe://", "") || (run.steps[0] ? methodName(run.steps[0].step.method) : "분석 실행");
const methodNames = (run: Run) => [...new Set(run.steps.map(step => methodName(step.step.method)))].join(" · ");
const runStatusLabel = (run: Run) => run.status === "completed" ? "완료" : run.status === "failed" ? "실패" : run.running ? "진행 중"
  : run.steps.at(-1)?.result.status === "needs_input" ? "입력 필요"
    : run.steps.at(-1)?.result.status === "refused" ? "중단" : "대기 중";

export default function RunsPage() {
  const { data, error, loading, reload } = useApi<Run[]>("/runs?limit=100");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [origin, setOrigin] = useState("all");
  const [deleted, setDeleted] = useState(false);
  const shown = useMemo(() => (data ?? []).filter((run) => {
    const text = `${displayName(run)} ${run.plan.question ?? ""} ${run.summary ?? ""} ${methodNames(run)}`.toLowerCase();
    return (status === "all" || run.status === status) && (origin === "all" || run.origin === origin)
      && text.includes(search.trim().toLowerCase());
  }), [data, search, status, origin]);
  const count = (value: string) => value === "all" ? data?.length ?? 0 : (data ?? []).filter((run) => run.status === value).length;

  return <div className={styles.page}>
    <div className={styles.libraryHeader}><div><h1>실행 기록</h1><p>저장된 실행 {data?.length ?? 0}개</p></div>
      <button className={styles.refreshButton} onClick={reload} disabled={loading} aria-label="새로고침" title="새로고침"><RefreshCw size={17} /></button></div>
    {deleted && <p role="status">실행 기록을 삭제했습니다.</p>}
    {error && <div className={styles.error} role="alert">실행 기록을 불러오지 못했습니다. {error.message} <button className="ghost" onClick={reload}>다시 시도</button></div>}
    {!loading && data?.length === 0 ? <section className={styles.empty}><History size={24} /><h2>아직 실행 기록이 없습니다</h2><p>분석 절차를 실행하면 결과가 여기에 남습니다.</p><div className={styles.emptyActions}><Link href="/recipes">분석 라이브러리 열기 <ArrowRight size={15} /></Link></div></section> : <section className={styles.libraryList} aria-label="실행 기록 목록">
      <div className={`${styles.libraryToolbar} ${styles.runToolbar}`}><label className={styles.librarySearch}><Search size={17} /><input aria-label="실행 기록 검색" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="분석 이름 또는 질문 검색" />
        {search && <button type="button" aria-label="검색 지우기" title="검색 지우기" onClick={() => setSearch("")}><X size={15} /></button>}
      </label><select className={styles.originSelect} aria-label="실행 출처" value={origin} onChange={(event) => setOrigin(event.target.value)}>
        <option value="all">모든 출처</option><option value="mcp">MCP 탐색</option><option value="web">웹 실행</option><option value="api">API 실행</option><option value="python">Python 실행</option>
      </select><span className={styles.libraryCount}>{shown.length}개 결과</span></div>
      <div className={styles.libraryFilters} role="group" aria-label="실행 상태">
        {[["all", "전체"], ["open", "진행·대기"], ["completed", "완료"], ["failed", "실패"]].map(([value, label]) => <button type="button" key={value} aria-pressed={status === value} onClick={() => setStatus(value)}>{label} <span>{count(value)}</span></button>)}
      </div>
      <div className={styles.libraryColumns} aria-hidden="true"><span>분석</span><span>실행 시각</span><span>상태</span><span /></div>
      {loading && !data ? <div aria-label="불러오는 중">{[0, 1, 2].map((row) => <div className={styles.skeleton} key={row} />)}</div> : shown.map((run) => <div key={run.id} className={styles.libraryItem}><Link href={`/runs/${run.id}`} className={styles.libraryRow}>
        <span className={styles.libraryName}><strong>{run.plan.question || displayName(run)}</strong><small>{runOriginLabel(run.origin)} · {run.preview ? "미리보기 · " : ""}{run.steps.length}단계{run.steps.length ? ` · ${methodNames(run)}` : ""}</small>{run.conclusion?.source !== "execution" && run.conclusion?.answer && <span className={styles.runListSummary}>{run.conclusion.answer}</span>}</span>
        <span className={styles.libraryMetric}>{new Date(run.created_at).toLocaleString()}</span>
        <span className={`${styles.libraryState} ${run.status === "completed" ? styles.libraryStateComplete : run.status === "failed" ? styles.libraryStateFailed : styles.libraryStateOpen}`}>{runStatusLabel(run)}</span>
        <ArrowRight size={17} className={styles.libraryArrow} />
      </Link><RunDelete run={run} compact onDeleted={() => { setDeleted(true); reload(); }} /></div>)}
      {!loading && !error && shown.length === 0 && <div className={styles.libraryNoResults}><strong>일치하는 기록이 없습니다</strong><button className="ghost" onClick={() => { setSearch(""); setStatus("all"); setOrigin("all"); }}>필터 지우기</button></div>}
    </section>}
  </div>;
}
