"use client";

import { useState } from "react";
import { ArrowUpRight, Database } from "lucide-react";
import { InspectorDialog } from "@/components/inspector-dialog";
import { ResultView } from "@/components/result";
import type { SemanticObject, SkillExecution } from "@/lib/api";
import styles from "./skill-query-activity.module.css";

const statusLabels = { success: "조회 완료", failed: "조회 실패", running: "조회 중", interrupted: "실행 중단" };
export function SkillQueryActivity({ skill, titles }: { skill: SkillExecution; titles: Map<string, SemanticObject> }) {
  const [selectedId, select] = useState<string | null>(null);
  const [requestOpen, setRequestOpen] = useState(false);
  const selected = skill.queries.find(query => query.id === selectedId) ?? skill.queries.find(query => query.error) ?? skill.queries[0];
  if (!selected) return <div className={styles.empty}><Database size={24} /><h3>아직 실행한 쿼리가 없습니다.</h3><p>AI가 조회하면 요청과 결과가 여기에 기록됩니다.</p></div>;
  return <section className={styles.workspace} aria-label="Skill 실행 로그">
    <div className={styles.list} aria-label="조회 목록">
      {skill.queries.map((query, index) => <button key={query.id} type="button" aria-pressed={selected.id === query.id} onClick={() => { select(query.id); setRequestOpen(false); }}>
        <span className={styles.ordinal}>{index + 1}</span><span><strong>{query.purpose || query.id}</strong><small>{query.id} / {statusLabels[query.status]}</small></span>
      </button>)}
    </div>
    <section className={styles.inspector} aria-label="조회 상세">
      <header><div><span className={selected.error ? styles.failed : styles.state}>{statusLabels[selected.status]}</span><h3>{selected.purpose || selected.id}</h3><small>{selected.id} / {new Date(selected.started_at).toLocaleString()}</small></div>
        <button type="button" className="ghost" onClick={() => setRequestOpen(true)}>요청 원문 <ArrowUpRight size={14} /></button></header>
      {selected.error && <p className={styles.error} role="alert">{selected.error.message}<small>{selected.error.code}</small></p>}
      {selected.result ? <ResultView key={selected.id} result={selected.result} titles={titles} showRunLink={false} showEvidence={false} showPrimaryTitle={false} expanded /> : !selected.error && <p className={styles.pending}>응답을 기다리고 있습니다.</p>}
      {!!selected.result?.warnings.length && <ul className={styles.warnings}>{selected.result.warnings.map((warning,index) => <li key={index}>{warning}</li>)}</ul>}
      {selected.result?.validation && selected.result.validation.length > 0 && <section className={styles.checks}><h4>조회 검사</h4>{selected.result.validation.map((item, index) => <p key={index}><span>{item.status === "pass" ? "통과" : item.status === "warning" ? "주의" : "미충족"}</span>{item.message}</p>)}</section>}
      <InspectorDialog title="조회 요청 원문" open={requestOpen} onClose={() => setRequestOpen(false)}><p>저장된 요청과 응답의 원본입니다.</p><pre>{JSON.stringify({ request: selected.spec, result: selected.result, error: selected.error }, null, 2)}</pre></InspectorDialog>
    </section>
  </section>;
}
