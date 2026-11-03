"use client";
import { useT } from "@/lib/i18n";

import { useState } from "react";
import { ArrowUpRight, Database } from "lucide-react";
import { InspectorDialog } from "@/components/inspector-dialog";
import { ResultView } from "@/components/result";
import { RunQueries } from "./run-evidence";
import { isRoutineSkillNotice, useRuntimeMessage } from "@/lib/runtime-messages";
import type { SemanticObject, SkillExecution } from "@/lib/api";
import styles from "./skill-query-activity.module.css";

const statusLabels = { success: "Query complete", failed: "Query failed", running: "Querying", interrupted: "Execution interrupted" };
export function SkillQueryActivity({ skill, titles }: { skill: SkillExecution; titles: Map<string, SemanticObject> }) {
  const t = useT();
  const runtime = useRuntimeMessage();
  const [selectedId, select] = useState<string | null>(null);
  const [requestOpen, setRequestOpen] = useState(false);
  const selected = skill.queries.find(query => query.id === selectedId) ?? skill.queries.find(query => query.error) ?? skill.queries[0];
  const warnings = selected?.result?.warnings.filter(warning => !isRoutineSkillNotice(warning)) ?? [];
  const checks = selected?.result?.validation.filter(item => item.status !== "pass") ?? [];
  if (!selected) return <div className={styles.empty}><Database size={24} /><h3>{t("No queries have run yet.")}</h3><p>{t("AI queries and responses are recorded here.")}</p></div>;
  return <section className={`${styles.workspace} ${skill.queries.length === 1 ? styles.single : ""}`} aria-label={t("Skill activity")}>
    {skill.queries.length > 1 && <div className={styles.list} aria-label={t("Query list")}>
      {skill.queries.map((query, index) => <button key={query.id} type="button" aria-pressed={selected.id === query.id} onClick={() => { select(query.id); setRequestOpen(false); }}>
        <span className={styles.ordinal}>{index + 1}</span><span><strong>{query.purpose || query.id}</strong><small>{query.id} / {t(statusLabels[query.status])}</small></span>
      </button>)}
    </div>}
    <section className={styles.inspector} aria-label={t("Query details")}>
      <header><div>{selected.status !== "success" && <span className={selected.error ? styles.failed : styles.state}>{t(statusLabels[selected.status])}</span>}<h3>{selected.purpose || selected.id}</h3></div>
        <button type="button" className="ghost" onClick={() => setRequestOpen(true)}>{t("Original request")} <ArrowUpRight size={14} /></button></header>
      {selected.error && <p className={styles.error} role="alert">{runtime(selected.error.message)}<small>{selected.error.code}</small></p>}
      {selected.result ? <ResultView key={selected.id} result={selected.result} titles={titles} showRunLink={false} showEvidence={false} showPrimaryTitle={false} expanded /> : !selected.error && <p className={styles.pending}>{t("Waiting for a response.")}</p>}
      {selected.result && <section className={styles.evidence} aria-label={t("Recorded query evidence")}><RunQueries result={selected.result} /></section>}
      {warnings.length > 0 && <ul className={styles.warnings}>{warnings.map((warning,index) => <li key={index}>{runtime(warning)}</li>)}</ul>}
      {checks.length > 0 && <section className={styles.checks}><h4>{t("Query checks")}</h4>{checks.map((item, index) => <p key={index}><span>{item.status === "pass" ? t("Passed") : item.status === "warning" ? t("Caution") : t("Not met")}</span>{runtime(item.message)}</p>)}</section>}
      <InspectorDialog title={t("Original query request")} open={requestOpen} onClose={() => setRequestOpen(false)}><pre>{JSON.stringify({ request: selected.spec, result: selected.result, error: selected.error }, null, 2)}</pre></InspectorDialog>
    </section>
  </section>;
}
