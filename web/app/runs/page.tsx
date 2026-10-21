"use client";
import { type Translate, useT } from "@/lib/i18n";

import { RequestError } from "@/components/request-error";
import { LoadingState } from "@/components/loading-indicator";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, History, RefreshCw, Search, X } from "lucide-react";

import type { Run } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { methodName } from "@/lib/method-name";
import { runOriginLabel } from "@/lib/run-origin";
import { RunDelete } from "@/features/runs/run-delete";
import { RunProcedure } from "@/features/runs/run-procedure";
import styles from "../library.module.css";

const displayName = (run: Run, t: Translate) => run.recipe_snapshot?.description || run.recipe_snapshot?.name || run.plan.recipe?.replace("recipe://", "") || (run.steps[0] ? methodName(run.steps[0].step.method, t) : t("Run analysis"));
const methodNames = (run: Run, t: Translate) => [...new Set(run.steps.map(step => methodName(step.step.method, t)))].join(" · ");
const runStatusLabel = (run: Run, t: Translate) => run.status === "completed" ? t("Done") : run.status === "failed" ? t("Failed") : run.running ? t("In progress")
  : run.needs_input || run.steps.at(-1)?.result.status === "needs_input" ? t("Input needed")
    : run.steps.at(-1)?.result.status === "refused" ? t("Stopped") : run.steps.length ? t("Awaiting conclusion") : t("Waiting");

export default function RunsPage() {
  const t = useT();
  const { data, error, loading, reload } = useApi<Run[]>("/runs?limit=100");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [origin, setOrigin] = useState("all");
  const [deleted, setDeleted] = useState(false);
  const shown = useMemo(() => (data ?? []).filter((run) => {
    const text = `${displayName(run, t)} ${run.recipe_snapshot?.name ?? ""} ${run.plan.recipe ?? ""} ${run.plan.question ?? ""} ${run.summary ?? ""} ${methodNames(run, t)}`.toLowerCase();
    return (status === "all" || run.status === status) && (origin === "all" || run.origin === origin)
      && text.includes(search.trim().toLowerCase());
  }), [data, search, status, origin, t]);
  const count = (value: string) => value === "all" ? data?.length ?? 0 : (data ?? []).filter((run) => run.status === value).length;

  return <div className={styles.page}>
    <div className={styles.libraryHeader}><div><h1>{t("Runs")}</h1><p>{data ? t("{count} saved runs", { count: data.length }) : t("Inspect executed inputs, results and query evidence.")}</p></div>
      <button className={styles.refreshButton} onClick={reload} disabled={loading} aria-label={t("Refresh")} title={t("Refresh")}><RefreshCw size={17} /></button></div>
    {deleted && <p role="status">{t("Run deleted.")}</p>}
    {error && <RequestError title={t("Could not load the Runs")} error={error} retry={reload} />}
    {error && !data ? null : !loading && data?.length === 0 ? <section className={styles.empty}><History size={24} /><h2>{t("No runs yet")}</h2><p>{t("Results appear here when you run an analysis procedure.")}</p><div className={styles.emptyActions}><Link href="/recipes">{t("Open Recipes")} <ArrowRight size={15} /></Link></div></section> : <section className={styles.libraryList} aria-label={t("Run list")}>
      <div className={`${styles.libraryToolbar} ${styles.runToolbar}`}><label className={styles.librarySearch}><Search size={17} /><input aria-label={t("Search runs")} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("Search by analysis name or question")} />
        {search && <button type="button" aria-label={t("Clear search")} title={t("Clear search")} onClick={() => setSearch("")}><X size={15} /></button>}
      </label><select className={styles.originSelect} aria-label={t("Run origin")} value={origin} onChange={(event) => setOrigin(event.target.value)}>
        <option value="all">{t("All origins")}</option><option value="mcp">{t("MCP run")}</option><option value="web">{t("Web run")}</option><option value="api">{t("API run")}</option><option value="python">{t("Python run")}</option>
      </select><span className={styles.libraryCount}>{t("{count} results", { count: shown.length })}</span></div>
      <div className={styles.libraryFilters} role="group" aria-label={t("Run status")}>
        {[["all", t("All")], ["open", t("In progress · waiting")], ["completed", t("Done")], ["failed", t("Failed")]].map(([value, label]) => <button type="button" key={value} aria-pressed={status === value} onClick={() => setStatus(value)}>{label} <span>{count(value)}</span></button>)}
      </div>
      <div className={`${styles.libraryColumns} ${styles.runColumns}`} aria-hidden="true"><span>{t("Question and result")}</span><span>{t("Run time")}</span><span>{t("Status")}</span><span /></div>
      {loading && !data ? <LoadingState /> : shown.map((run) => <div key={run.id} className={styles.libraryItem}><Link href={`/runs/${run.id}`} className={`${styles.libraryRow} ${styles.runRow}`}>
        <span className={styles.libraryName}><strong>{run.plan.question || displayName(run, t)}</strong>{run.conclusion?.source !== "execution" && run.conclusion?.answer && <span className={styles.runListSummary}>{run.conclusion.answer}</span>}<span className={styles.runMetadata}><RunProcedure run={run} /><small>{runOriginLabel(run.origin, t)}</small><small>{t("{count} steps", { count: run.steps.length })}</small></span></span>
        <span className={styles.libraryMetric}>{new Date(run.created_at).toLocaleString()}</span>
        <span className={`${styles.libraryState} ${run.status === "completed" ? styles.libraryStateComplete : run.status === "failed" ? styles.libraryStateFailed : styles.libraryStateOpen}`}>{runStatusLabel(run, t)}</span>
        <ArrowRight size={17} className={styles.libraryArrow} />
      </Link><RunDelete run={run} compact onDeleted={() => { setDeleted(true); reload(); }} /></div>)}
      {!loading && !error && shown.length === 0 && <div className={styles.libraryNoResults}><strong>{t("No matching runs")}</strong><button className="ghost" onClick={() => { setSearch(""); setStatus("all"); setOrigin("all"); }}>{t("Clear filters")}</button></div>}
    </section>}
  </div>;
}
