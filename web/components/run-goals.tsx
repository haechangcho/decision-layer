"use client";

import { useRef, useState } from "react";
import { ExternalLink, GitPullRequest, X } from "lucide-react";
import { api, type GoalOutcome, type Run } from "@/lib/api";
import { useT } from "@/lib/i18n";
import s from "./run-goals.module.css";

const labels: Record<string, string> = { supported: "Evidence recorded", needs_input: "Input needed", unsupported: "Not supported", blocked: "Execution blocked", inconclusive: "Unable to judge", pending: "Not yet answered" };

export function RunGoals({ run, mine, onSelect }: { run: Run; mine: boolean; onSelect: (index: number) => void }) {
  const t = useT();
  const dialog = useRef<HTMLDialogElement>(null);
  const [goalId, setGoalId] = useState("");
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [expected, setExpected] = useState("");
  const [draft, setDraft] = useState<{ body: string; url: string; existing_issues_url: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const unresolvedGoals = (run.goals || []).filter(goal =>
    run.conclusion?.goal_outcomes?.find(outcome => outcome.goal_id === goal.id)?.status !== "supported" &&
    !(run.remediations || []).some(item => item.goal_id === goal.id || item.related_goal_ids?.includes(goal.id)));
  if (!unresolvedGoals.length) return null;
  async function prepare(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { setDraft(await api(`/runs/${run.id}/method-proposal`, { body: { goal_id: goalId, title, public_question: question, expected_result: expected } })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : t("Could not prepare the proposal.")); }
    finally { setBusy(false); }
  }
  return <section className={s.section} aria-label={t("Unanswered questions")}>
    <h2>{t("Unanswered questions")}</h2>
    <ul className={s.goals}>{unresolvedGoals.map(goal => {
      const outcome = run.conclusion?.goal_outcomes?.find(item => item.goal_id === goal.id);
      return <li key={goal.id}><div><strong>{goal.description}</strong><span className={s.status}>{t(labels[outcome?.status || "pending"])}</span></div>
        {outcome?.reason && <p>{outcome.reason}</p>}
        {!!outcome?.step_indices.length && <div className={s.links}>{outcome.step_indices.map(index => <button key={index} type="button" onClick={() => onSelect(index)}>{t("Step {number}", { number: index + 1 })}</button>)}</div>}
        {mine && outcome?.status === "unsupported" && outcome.reason_code === "method_missing" && <button type="button" className={s.propose} onClick={() => { setGoalId(goal.id); setTitle(""); setQuestion(""); setExpected(""); setDraft(null); setError(""); dialog.current?.showModal(); }}><GitPullRequest size={15} />{t("Propose an analysis Method")}</button>}
      </li>;
    })}</ul>
    <dialog ref={dialog} className={s.dialog} aria-label={t("Propose an analysis Method")}>
      <header><h2>{t("Propose an analysis Method")}</h2><button type="button" aria-label={t("Close")} title={t("Close")} onClick={() => dialog.current?.close()}><X size={18} /></button></header>
      <p>{t("Use public or synthetic examples. Your Run data and queries are not copied.")}</p>
      {draft ? <><label>{t("Public issue draft")}<textarea rows={12} readOnly value={draft.body} /></label><div className={s.links}><a href={draft.existing_issues_url} target="_blank" rel="noreferrer">{t("Check existing proposals")}<ExternalLink size={14} /></a><a href={draft.url} target="_blank" rel="noreferrer">{t("Review on GitHub")}<ExternalLink size={14} /></a></div><p>{t("The issue is submitted only after you review and submit it on GitHub.")}</p></> : <form onSubmit={prepare}><label>{t("Method proposal title")}<input required maxLength={120} value={title} onChange={event => setTitle(event.target.value)} /></label><label>{t("Public example question")}<textarea required maxLength={1000} rows={3} value={question} onChange={event => setQuestion(event.target.value)} /></label><label>{t("Expected analysis result")}<textarea required maxLength={1000} rows={3} value={expected} onChange={event => setExpected(event.target.value)} /></label><button type="submit" disabled={busy}>{t(busy ? "Preparing draft…" : "Prepare public draft")}</button></form>}
      {error && <p role="alert">{error}</p>}
    </dialog>
  </section>;
}

export function suggestedOutcomes(run: Run): GoalOutcome[] {
  return (run.goals || []).map(goal => {
    const indices = run.steps.flatMap((record, index) => record.step.goal_ids?.includes(goal.id) && record.result.status === "success" && record.result.primary &&
      (goal.interpretation === "descriptive" || record.result.interpretation === goal.interpretation) &&
      goal.semantic_refs.every(ref => record.result.provenance.semantic_refs.includes(ref)) ? [index] : []);
    const provided = new Set(indices.flatMap(index => run.steps[index].result.provides || []));
    const refs = new Set(indices.flatMap(index => run.steps[index].result.provenance.semantic_refs));
    const supported = indices.length > 0 && goal.required_capabilities.every(capability => provided.has(capability)) && goal.semantic_refs.every(ref => refs.has(ref));
    return { goal_id: goal.id, status: supported ? "supported" : "inconclusive", step_indices: indices, reason: "" };
  });
}
