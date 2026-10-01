"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, CircleCheck, Clock3, History, Search, XCircle } from "lucide-react";

import type { Run } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import styles from "../library.module.css";

const displayName = (run: Run) => run.recipe_snapshot?.name ?? run.plan.recipe?.replace("recipe://", "") ?? run.steps[0]?.step.method ?? "분석 실행";
const statusLabel = (status: Run["status"]) => status === "completed" ? "완료" : status === "failed" ? "실패" : "진행 중";

export default function RunsPage() {
  const { data, error, loading, reload } = useApi<Run[]>("/runs?limit=100");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const shown = useMemo(() => (data ?? []).filter((run) => {
    const matchesStatus = status === "all" || run.status === status;
    const text = `${displayName(run)} ${run.plan.question ?? ""} ${run.summary ?? ""} ${run.caller.subject ?? ""}`.toLowerCase();
    return matchesStatus && text.includes(search.trim().toLowerCase());
  }), [data, search, status]);
  const selected = shown.find((run) => run.id === selectedId) ?? shown[0] ?? null;

  useEffect(() => {
    if (selected && selected.id !== selectedId) setSelectedId(selected.id);
  }, [selected, selectedId]);

  const count = (value: string) => value === "all" ? data?.length ?? 0 : (data ?? []).filter((run) => run.status === value).length;

  return <div className={styles.page}>
    <div className={styles.heading}><div><p className={styles.eyebrow}>ANALYSIS HISTORY</p><h1>실행 기록</h1><p className={styles.intro}>분석 결과와 근거를 다시 확인하고 다음 단계로 이어가세요.</p></div><button className="ghost" onClick={reload} disabled={loading}><History size={15} />새로고침</button></div>
    {error && <div className={styles.error} role="alert">실행 기록을 불러오지 못했습니다. {error.message} <button className="ghost" onClick={reload}>다시 시도</button></div>}
    {!loading && data?.length === 0 ? <section className={styles.empty}><History size={24} /><h2>아직 실행 기록이 없습니다</h2><p>분석 Recipe나 분석 방법을 실행하면 결과와 근거가 여기에 저장됩니다.</p><div className={styles.emptyActions}><Link href="/recipes">Recipe 살펴보기 <ArrowRight size={15} /></Link><Link href="/methods">분석 방법 살펴보기 <ArrowRight size={15} /></Link></div></section> : <div className={styles.layout}>
      <section className={styles.list} aria-label="실행 기록 목록">
        <div className={styles.toolbar}><label className={styles.search}><Search size={17} /><input aria-label="실행 기록 검색" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="질문, Recipe 또는 결론 검색" /></label><span className={styles.count}>{data?.length ?? 0}회 실행</span></div>
        <div className={styles.filters} role="group" aria-label="실행 상태">
          {["all", "open", "completed", "failed"].map((value) => <button key={value} className={status === value ? styles.active : ""} aria-pressed={status === value} onClick={() => setStatus(value)}>{value === "all" ? `전체 ${count(value)}` : `${statusLabel(value as Run["status"])} ${count(value)}`}</button>)}
        </div>
        {loading && !data ? <div aria-label="불러오는 중">{[0, 1, 2].map((row) => <div className={styles.skeleton} key={row} />)}</div> : shown.map((run) => <button key={run.id} className={`${styles.row} ${selected?.id === run.id ? styles.selected : ""}`} onClick={() => setSelectedId(run.id)} aria-pressed={selected?.id === run.id}>
          <span className={styles.icon}>{run.status === "completed" ? <CircleCheck size={17} /> : run.status === "failed" ? <XCircle size={17} /> : <Clock3 size={17} />}</span><span className={styles.copy}><strong>{run.plan.question || displayName(run)}</strong><small>{displayName(run)} · {new Date(run.created_at).toLocaleString()}</small></span><span className={`${styles.badge} ${run.status === "failed" ? styles.badgeFailed : run.status === "open" ? styles.badgeOpen : ""}`}>{statusLabel(run.status)}</span>
        </button>)}
        {!loading && !error && shown.length === 0 && <div className={styles.noResults}>조건에 맞는 실행 기록이 없습니다.</div>}
      </section>
      <aside className={styles.detail} aria-label="실행 기록 상세">
        {selected ? <>
          <div className={styles.detailHeader}><span className={styles.icon}><History size={18} /></span><span className={`${styles.badge} ${selected.status === "failed" ? styles.badgeFailed : selected.status === "open" ? styles.badgeOpen : ""}`}>{statusLabel(selected.status)}</span></div>
          <h2>{selected.plan.question || displayName(selected)}</h2><p className={styles.description}>{displayName(selected)}</p>
          <dl className={styles.meta}>
            <div className={styles.metaRow}><dt>시작 시각</dt><dd>{new Date(selected.created_at).toLocaleString()}</dd></div>
            <div className={styles.metaRow}><dt>분석 단계</dt><dd>{selected.steps.length}단계</dd></div>
            <div className={styles.metaRow}><dt>실행자</dt><dd>{selected.caller.subject ?? "—"}</dd></div>
            {selected.summary && <div className={styles.metaRow}><dt>요약</dt><dd>{selected.summary}</dd></div>}
          </dl>
          <Link className={styles.primary} href={`/runs/${selected.id}`}>결과와 근거 보기 <ArrowRight size={16} /></Link>
        </> : <div className={styles.empty}><History size={22} /><h2>{loading ? "기록을 불러오는 중" : "실행 기록을 선택하세요"}</h2><p>선택한 실행의 결과와 검증 상태를 확인할 수 있습니다.</p></div>}
      </aside>
    </div>}
  </div>;
}
