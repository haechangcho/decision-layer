"use client";

import { useEffect, useRef, useState } from "react";
import { Play } from "lucide-react";
import { api, type Run, type SemanticObject } from "@/lib/api";
import { suggestedDateRange } from "@/lib/semantic-dates";
import { useT } from "@/lib/i18n";
import styles from "@/app/library.module.css";

export function periodLabel(run: Run) {
  if (run.plan.scope.period?.mode === "unresolved" || run.needs_input) return "기간 확인 필요";
  return run.plan.scope.date_range?.join(" ~ ") || (run.plan.scope.period?.mode === "all" ? "전체 기간 · 명시적 선택" : "기간 선택 기록 없음");
}

export function RunPeriodInput({ run, objects, onDone }: { run: Run; objects: SemanticObject[]; onDone: (run: Run) => void }) {
  const t = useT();
  const metricRef = run.recipe_snapshot?.semantic_scope.primary_metric ?? run.pending_execution?.step?.bindings.metric ?? run.plan.resolved?.primary_metric;
  const metric = objects.find(object => object.ref === metricRef);
  const times = objects.filter(object => object.kind === "time_dimension" && (!metric || metric.dimension_refs?.includes(object.ref)));
  const [time, setTime] = useState(run.plan.scope.time_dimension || metric?.time_dimension || (times.length === 1 ? times[0].ref : ""));
  const selectedTime = times.some(object => object.ref === time) ? time : metric?.time_dimension || (times.length === 1 ? times[0].ref : "");
  const suggested = suggestedDateRange(objects.find(object => object.ref === selectedTime));
  const touched = useRef(false);
  const [dates, setDates] = useState<[string, string]>(run.plan.scope.date_range ?? suggested ?? ["", ""]);
  const suggestedKey = suggested?.join("/");
  useEffect(() => { if (!touched.current && !run.plan.scope.date_range && suggested) setDates(suggested); }, [suggestedKey]);
  function chooseDates(next: [string, string]) { touched.current = true; setDates(next); }
  const [all, setAll] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const periodMessages: Record<string, string> = {
    PERIOD_UNRESOLVED: "Choose an analysis period or explicitly request all periods.",
    ALL_PERIODS_DISABLED: "The server does not allow all-period queries. Choose a date range.",
    RANGE_REQUIRED: "This analysis needs a date range. Choose its start and end dates.",
    PERIOD_TOO_LONG: "Choose a period of at most {days} days.",
  };
  const question = periodMessages[run.needs_input?.reason_code || ""] || run.needs_input?.question || "Choose a period to continue the same analysis.";
  async function resume() {
    setBusy(true); setError("");
    try {
      const next = await api<Run>(`/runs/${run.id}/scope`, { method: "PUT", body: { base_revision: run.scope_revision ?? 0,
        scope: { period: all ? { mode: "all" } : { mode: "range", date_range: dates }, ...(selectedTime ? { time_dimension: selectedTime } : {}) } } });
      onDone(next);
    } catch (cause) { setError(cause instanceof Error ? cause.message : t("Could not apply the period.")); }
    finally { setBusy(false); }
  }
  return <section className={styles.formPanel} aria-label={t("Confirm analysis period")}>
    <h2>{t("Choose the analysis period")}</h2>
    <p>{t(question, { days: run.needs_input?.max_period_days ?? 0 })}</p>
    {run.needs_input?.allow_all && <label className="check"><input type="checkbox" checked={all} onChange={event => setAll(event.target.checked)} />{t("All periods")}</label>}
    {!all && <>
      {times.length > 1 && <label className={styles.runField}>{t("Date dimension")}<select aria-label={t("Date dimension")} value={selectedTime} onChange={event => { setTime(event.target.value); const hint = suggestedDateRange(objects.find(object => object.ref === event.target.value)); if (hint && !touched.current) setDates(hint); }}><option value="">{t("Choose a date dimension")}</option>{times.map(object => <option key={object.ref} value={object.ref}>{object.title}</option>)}</select></label>}
      <div className={styles.dateFields}><label className={styles.runField}>{t("Start date")}<input type="date" value={dates[0]} onChange={event => chooseDates([event.target.value, dates[1]])} /></label><label className={styles.runField}>{t("End date")}<input type="date" value={dates[1]} onChange={event => chooseDates([dates[0], event.target.value])} /></label></div>
      {run.needs_input?.max_period_days && <p className="hint">{t("Maximum period")}: {run.needs_input.max_period_days} {t("days")}</p>}
    </>}
    {error && <p className={styles.error} role="alert">{error}</p>}
    <button type="button" className={styles.runPrimary} disabled={busy || !all && (!dates[0] || !dates[1] || dates[0] > dates[1] || times.length > 0 && !selectedTime)} onClick={resume}><Play size={16} />{t(busy ? "Starting analysis…" : "Continue with this period")}</button>
  </section>;
}
