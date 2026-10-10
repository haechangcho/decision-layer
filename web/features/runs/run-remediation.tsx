"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Plus, Copy, FileCode2 } from "lucide-react";
import { api, type Run, type RunRemediation, type SemanticObject } from "@/lib/api";
import { useT } from "@/lib/i18n";
import s from "./run-remediation.module.css";

export function RunRemediations({ run, mine, objects, onDone }: { run: Run; mine: boolean; objects: SemanticObject[]; onDone: () => void }) {
  const t = useT();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const gaps = run.conclusion?.goal_outcomes?.filter(item => item.reason_code === "semantic_missing" && !(run.remediations || []).some(fix => fix.goal_id === item.goal_id || fix.related_goal_ids?.includes(item.goal_id))) || [];
  if (!run.remediations?.length && !gaps.length && !run.retry_of) return null;
  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      await api(`/runs/${run.id}/remediations`, { body: { goal_id: data.get("goal"), reason: gaps.find(gap => gap.goal_id === data.get("goal"))?.reason || "Semantic information needs review",
        evidence: data.get("evidence"), proposal: data.get("proposal"), requirements: [{ description: data.get("description"), kind: data.get("kind") }] } });
      setCreating(false); onDone();
    } catch (cause) { setError((cause as Error).message); } finally { setBusy(false); }
  }
  return <section className={s.section} aria-label={t("Model improvements")}>
    {run.retry_of && <p className={s.origin}>{t("Reanalysis after a model review")} <Link href={`/runs/${run.retry_of.run_id}`}>{t("View original analysis")}<ArrowRight size={14} /></Link></p>}
    {!!run.remediations?.length && <><h2>{t("Model improvements")}</h2>{run.remediations.map(item => <Improvement key={item.id} run={run} item={item} objects={objects} />)}</>}
    {mine && !!gaps.length && !creating && <button type="button" className="ghost" onClick={() => setCreating(true)}><Plus size={15} />{t("Record a model improvement")}</button>}
    {creating && <form className={s.form} onSubmit={create}><h3>{t("Record a model improvement")}</h3>
      <label>{t("Question to address")}<select name="goal">{gaps.map(gap => <option key={gap.goal_id} value={gap.goal_id}>{run.goals?.find(goal => goal.id === gap.goal_id)?.description}</option>)}</select></label>
      <label>{t("What did you check?")}<textarea name="evidence" rows={2} required maxLength={1200} /></label>
      <label>{t("Suggested model improvement")}<textarea name="proposal" rows={2} required maxLength={600} /></label>
      <label>{t("Required definition")}<input name="description" required maxLength={400} /></label>
      <label>{t("Definition type")}<select name="kind"><option value="dimension">{t("Dimension")}</option><option value="measure">{t("Metric")}</option><option value="time_dimension">{t("Time dimension")}</option></select></label>
      <div className={s.actions}><button type="submit" disabled={busy}>{t("Save proposal")}</button><button type="button" className="ghost" onClick={() => setCreating(false)}>{t("Cancel")}</button></div>
    </form>}
    {error && <p role="alert">{error}</p>}
  </section>;
}

function Improvement({ run, item, objects }: { run: Run; item: RunRemediation; objects: SemanticObject[] }) {
  const t = useT();
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const retries = item.events.filter(event => event.action === "retry_started");
  return <article className={s.item}>
    <header><h3>{item.requirements.map(required => required.description).join(", ")}</h3></header>
    <p className={s.reason}>{item.reason}</p>
    <div className={s.next}><span>{t("What to change")}</span><p>{item.proposal}</p></div>
    <ModelDrafts run={run} item={item} objects={objects} />
    <button type="button" className={s.evidenceButton} aria-expanded={evidenceOpen} onClick={() => setEvidenceOpen(!evidenceOpen)}>{t(evidenceOpen ? "Hide evidence" : "View evidence")}</button>
    {evidenceOpen && <div className={s.evidence}><h4>{t("Question to address")}</h4>{run.goals?.filter(goal => [item.goal_id, ...(item.related_goal_ids || [])].includes(goal.id)).map(goal => <p key={goal.id}>{goal.description}</p>)}<h4>{t("What was checked")}</h4><p>{item.evidence}</p></div>}
    {retries.map(event => <Link className={s.retry} key={event.run_id} href={`/runs/${event.run_id}`}>{t("View reanalysis")}<ArrowRight size={14} /></Link>)}
  </article>;
}

function ModelDrafts({ run, item, objects }: { run: Run; item: RunRemediation; objects: SemanticObject[] }) {
  const t = useT();
  const [selected, setSelected] = useState(0);
  const [copyState, setCopyState] = useState("");
  const recordedRefs = [...item.requirements.flatMap(required => required.ref ? [required.ref] : []), ...(run.goals || []).flatMap(goal => goal.semantic_refs || []), ...run.steps.flatMap(step => step.result.provenance.semantic_refs)];
  const refs = recordedRefs.length ? recordedRefs : objects.map(object => object.ref);
  const provider = refs.some(ref => ref.startsWith("dbt://")) ? "dbt" : refs.some(ref => ref.startsWith("cube://")) ? "cube" : null;
  // Historical Runs have no proposed YAML. Show a clearly unbound fragment, never infer physical columns.
  const fallback = provider && item.requirements.every(required => required.kind === "dimension") ? [{
    provider, title: t("Dimension template"),
    yaml: provider === "cube" ? 'dimensions:\n  - name: "<dimension_name>"\n    sql: "<source_column_or_expression>"\n    type: string' : 'dimensions:\n  - name: "<dimension_name>"\n    type: categorical\n    expr: "<source_column_or_expression>"',
    unresolved: [t("Confirm the source column, data type and model to edit."), t("Confirm this dimension can group and filter the requested metric.")],
    basis: [t("Template only; no physical column or relationship was confirmed.")],
  }] : [];
  const drafts = item.model_drafts?.length ? item.model_drafts : fallback;
  const draft = drafts[Math.min(selected, drafts.length - 1)];
  if (!draft) return <p className={s.note}>{t("A model owner must confirm the source columns and relationships before a YAML draft can be prepared.")}</p>;
  async function copy() {
    try { await navigator.clipboard.writeText(draft.yaml); setCopyState(t("Copied")); }
    catch { setCopyState(t("Copy failed. Select the YAML text below.")); }
  }
  return <div className={s.draft}>
    <div className={s.draftHeader}><h4><FileCode2 size={16} />{t(item.model_drafts?.length ? "Suggested YAML" : "YAML template")}<span>{draft.provider === "cube" ? "Cube" : "dbt"}</span></h4><button type="button" className="ghost" onClick={copy}><Copy size={14} />{t("Copy YAML")}</button></div>
    {drafts.length > 1 && <div className={s.draftTabs} role="tablist" aria-label={t("Suggested YAML")}>{drafts.map((value, index) => <button type="button" key={index} role="tab" aria-selected={index === selected} onClick={() => { setSelected(index); setCopyState(""); }}>{value.title}</button>)}</div>}
    <p className={s.note}>{t("Review draft, not applied. Update the model in your semantic layer.")}</p>
    <pre><code>{draft.yaml}</code></pre>
    {!!draft.unresolved.length && <div className={s.unknown}><strong>{t("Confirm before applying")}</strong><ul>{draft.unresolved.map((value, index) => <li key={index}>{value}</li>)}</ul></div>}
    {item.model_drafts?.length ? <p className={s.note}>{t("Draft basis")}: {draft.basis.join("; ")}</p> : null}
    <span role="status" className={s.note}>{copyState}</span>
  </div>;
}
