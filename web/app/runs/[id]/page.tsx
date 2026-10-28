"use client";
import { SourceEvidence, MethodMarkdown } from "@/features/methods/method-content";
import { InspectorDialog } from "@/components/inspector-dialog";
import { WorkspaceTabs } from "@/components/workspace-tabs";
import { SkillQueryActivity } from "@/features/runs/skill-query-activity";
import { LoadingState } from "@/components/loading-indicator";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BookPlus, Check, History, LoaderCircle, Share2, SlidersHorizontal, X } from "lucide-react";

import { clean, MethodInputs } from "@/components/forms";
import { ArtifactView, ResultView } from "@/components/result";
import { RunGraph } from "@/features/runs/run-graph";
import { RunAnswer } from "@/features/runs/run-answer";
import { RunGoals, suggestedOutcomes } from "@/features/runs/run-goals";
import { RunRemediations } from "@/features/runs/run-remediation";
import { RunDelete } from "@/features/runs/run-delete";
import { RunProcedure } from "@/features/runs/run-procedure";
import { RunResultChart } from "@/features/runs/run-result-chart";
import { RunPeriodInput, periodLabel } from "@/features/runs/run-period-input";
import { AuthorInfo, RunQueries, RunSettings, RunSources, readableValue } from "@/features/runs/run-evidence";
import { api, MethodManifest, Recipe, Result, Run } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { methodName } from "@/lib/method-name";
import { runOriginLabel } from "@/lib/run-origin";
import { isSourcePurpose, stepFinding, stepPurpose } from "@/lib/run-story";
import styles from "../../library.module.css";

export default function RunPage() {
  const t = useT();
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: run, error, reload } = useApi<Run>(`/runs/${id}`);
  const { data: manifests } = useApi<MethodManifest[]>("/methods");
  const { objects, byRef, reload: reloadCatalog } = useCatalog();
  const { data: me } = useApi<{ subject: string }>("/me");
  const [open, setOpen] = useState<number | null>(null);
  const [tab, setTab] = useState<string>("result");
  const [snapshotOpen, setSnapshotOpen] = useState(false);
  const [referenceGuide, setReferenceGuide] = useState<number | null>(null);
  const [continueMode, setContinueMode] = useState<"step" | "conclusion" | null>(null);
  const [registering, setRegistering] = useState(false);
  const [registered, setRegistered] = useState<Recipe | null>(null);
  const [registerError, setRegisterError] = useState("");
  const shareDialog = useRef<HTMLDialogElement>(null);
  const mine = !!me && me.subject === run?.caller.subject;
  useEffect(() => {                                   // a background job is running: refresh until it ends
    if (!run?.running && !run?.active_skill_step) return;
    const t = setTimeout(reload, 2000);
    return () => clearTimeout(t);
  }, [run, reload]);

  if (error) return <div className={styles.page}><p className={styles.error} role="alert">{error.message}</p><Link className={styles.back} href="/runs"><ArrowLeft size={15} />{t("Runs")}</Link></div>;
  if (!run) return <div className={styles.page}><LoadingState /></div>;
  const recipe = run.recipe_snapshot;
  const current = open ?? run.steps.length - 1;
  const lastStatus = run.needs_input ? "needs_input" : run.steps.at(-1)?.result.status;
  const stopped = run.status === "open" && !run.running && (lastStatus === "refused" || lastStatus === "needs_input");
  const reusableSteps = run.steps.flatMap((step, index) => step.result.status === "success" ||
    step.result.status === "refused" && step.result.primary != null && step.result.validation.some(item => item.status === "fail") ? [index] : []);
  const rejectedCalculations = reusableSteps.filter(index => run.steps[index].result.status === "refused").length;
  const candidateParams = new URLSearchParams({ from_run: run.id });
  reusableSteps.forEach((index) => candidateParams.append("step", String(index)));
  const canRegister = run.status === "completed" && !run.running && reusableSteps.length === run.steps.length && reusableSteps.length > 0;
  const hasAdditionalAnalysis = !!run.recipe_invocation && run.steps.some(record => !record.invocation_id);
  const showRegistration = !run.plan.recipe || hasAdditionalAnalysis;
  async function registerRecipe() {
    setRegistering(true); setRegisterError("");
    try { setRegistered(await api<Recipe>(`/runs/${id}/recipe`, { body: {} })); }
    catch (cause) { setRegisterError(cause instanceof Error ? cause.message : t("Could not register the Recipe.")); }
    finally { setRegistering(false); }
  }

  const scope = run.plan.scope;
  const timeTitle = scope.time_dimension ? byRef.get(scope.time_dimension)?.title ?? t("Date dimension name needs checking") : null;
  const metricRefs = [...new Set(run.steps.flatMap((record) => {
    const metric = record.step.bindings.metric;
    return typeof metric === "string" && /^[a-z][a-z0-9_-]*:\/\//.test(metric) ? [metric] : [];
  }))];
  if (recipe?.semantic_scope.primary_metric && !metricRefs.includes(recipe.semantic_scope.primary_metric)) metricRefs.unshift(recipe.semantic_scope.primary_metric);
  const pendingMetric = run.pending_execution?.step?.bindings.metric;
  if (typeof pendingMetric === "string" && !pendingMetric.startsWith("$") && !metricRefs.includes(pendingMetric)) metricRefs.push(pendingMetric);
  const metricNames = metricRefs.map((ref) => byRef.get(ref)?.title ?? t("Metric name needs checking"));
  const canContinue = mine && !run.preview && !run.active_skill_step && !run.needs_input && run.status === "open" && !run.running && !!manifests && (recipe?.mode !== "pipeline" || !!run.recipe_invocation?.completed);
  const canConclude = mine && !run.preview && !run.active_skill_step && run.status === "open" && !run.running &&
    ((!run.needs_input && run.steps.length > 0) || (!!run.goals?.length && !run.steps.length));
  const canShare = mine && !run.preview && !run.caller.subject?.startsWith("service:");
  const selectedStep = run.steps[current];
  const additional = selectedStep?.result.artifacts.filter(artifact => !Array.isArray(artifact.data) || artifact.data.length > 0) ?? [];
  const warnings = [...new Map([...run.validation, ...run.steps.flatMap((step) => step.result.validation)]
    .filter((item) => item.status !== "pass").map((item) => [`${item.code}:${item.message}`, item])).values()];
  return <div className={`${styles.page} ${styles.runPage}`}>
    <Link className={styles.back} href="/runs"><ArrowLeft size={15} />{t("Runs")}</Link>
    <header className={styles.runOverview} aria-label={t("Question and run details")}>
    <div className={styles.heading}><div><p className={styles.eyebrow}>{run.preview ? t("Preview") : "RUN"} · {runOriginLabel(run.origin, t)} · {new Date(run.created_at).toLocaleString()}</p><h1>{run.plan.question || recipe?.description || recipe?.name || (metricNames[0] ? t("{metric} analysis", { metric: metricNames[0] }) : t("Analysis result"))}</h1></div><div className={styles.runHeaderActions}><span className={`${styles.badge} ${run.status === "failed" || (stopped && !run.active_skill_step) ? styles.badgeFailed : run.status === "open" ? styles.badgeOpen : ""}`}>{run.status === "completed" ? t("Done") : run.active_skill_step ? t("Waiting for AI") : run.status === "failed" ? t("Failed") : stopped ? lastStatus === "needs_input" ? t("Input needed") : t("Stopped") : run.running ? t("In progress") : run.steps.length ? t("Awaiting conclusion") : t("Waiting")}</span>{mine && <RunDelete run={run} onDeleted={() => router.push("/runs")} />}</div></div>
    <p className={styles.runScope}><strong>{metricNames.join(" · ") || t("No metric chosen yet")}</strong><span>{periodLabel(run, t)}</span>{timeTitle && <span>{timeTitle}  {t("Date basis")}</span>}{run.scope_resolution?.source && <span>{({ caller: t("Chosen by the caller"), conversation: t("Carried over from the conversation"), ai_proposal: t("Proposed by AI"), recipe_default: t("Recipe default period"), organization_default: t("Organization default period"), unspecified: t("Not chosen yet") } as Record<string, string>)[run.scope_resolution.source] || t("Choice origin unknown")}</span>}</p>
    <RunProcedure run={run} />
    </header>
    {!!run.method_guides?.length && <div className={styles.runReferenceLinks}>{run.method_guides.map((guide,index) => <button type="button" key={guide.name} className="ghost" onClick={() => setReferenceGuide(index)}>{t("Reference instructions /")} {guide.name}</button>)}</div>}
    <InspectorDialog title={t("Referenced Skill instructions")} open={referenceGuide !== null} onClose={() => setReferenceGuide(null)}>{referenceGuide !== null && run.method_guides?.[referenceGuide] && <><p>v{run.method_guides[referenceGuide].version}</p><MethodMarkdown content={run.method_guides[referenceGuide].markdown} /><p className={styles.contentHash}>SHA-256 {run.method_guides[referenceGuide].sha256}</p></>}</InspectorDialog>
    {mine && run.needs_input && <RunPeriodInput key={`${run.id}:${run.scope_revision}`} run={run} objects={objects} onDone={() => reload()} />}
    {run.active_skill_step && !run.running && <p className={styles.runNotice} role="status">{t("Waiting for AI. Continue this Run in Claude or Codex.")}</p>}
    {run.running && <p className={styles.runNotice} role="status">{t("Running /")} {run.running.method ? methodName(run.running.method, t) : run.running.kind} · {new Date(run.running.started_at).toLocaleTimeString()}  {t("Started")}</p>}
    {run.error && <p className={styles.error} role="alert">{run.error.message}  {t("/ Error code")} {run.error.code}</p>}
    {(!run.needs_input || run.steps.length > 0) && <><RunAnswer run={run} warnings={warnings} onSelect={index => { setOpen(index); setTab("result"); document.getElementById("run-step-detail")?.scrollIntoView({ behavior: "smooth", block: "start" }); }} />
    <RunRemediations run={run} mine={mine} objects={objects} onDone={() => { reload(); reloadCatalog(); }} />
    {run.steps.length > 1 && <RunGraph run={run} titles={byRef} selected={current} onSelect={index => { setOpen(index); setTab("result"); }} />}</>}
    {selectedStep ? <section id="run-step-detail" className={styles.runStepDetail}><span>{t("{current} / {total} steps", { current: current + 1, total: run.steps.length })}</span><h2>{methodName(selectedStep.step.method, t)}</h2><p className={styles.runPurpose}><span>{t("Analysis purpose")}</span>{stepPurpose(selectedStep.step, t, run)}</p>
      {isSourcePurpose(selectedStep.step, run) && selectedStep.step.purpose && <div className={styles.runPurposeContext}><p><strong>{t("Period for this run")}</strong> {periodLabel(run, t)}</p><p><strong>{t("Step description when registered")}</strong> {selectedStep.step.purpose}</p><span>{t("Original step description. See this Run's dates and settings for its actual scope.")}</span></div>}
      {selectedStep.skill && <div className={styles.executionStrip} aria-label={t("Skill execution status")}><span>{selectedStep.skill.status === "awaiting_agent" ? t("Waiting for AI") : selectedStep.skill.status === "refused" ? t("Analysis stopped") : t("Query step complete")}</span><span>{t("Recorded queries")} {selectedStep.skill.queries.length}</span>
        {selectedStep.skill.queries.some(query => query.error || query.status === "interrupted") && <button type="button" onClick={() => setTab("queries")}>{t("Inspect failed queries")}</button>}
      </div>}
      {selectedStep.skill && tab !== "queries" && selectedStep.skill.queries.some(query => query.error) && <p role="alert" className={styles.runQueryFailure}>{selectedStep.skill.queries.find(query => query.error)?.error?.message}</p>}
      <WorkspaceTabs id="run" label={t("Analysis step details")} value={tab} onChange={setTab} items={([
        ['result', t("Result")], ...(additional.length || selectedStep.result.validation.length || selectedStep.result.warnings.length ? [['additional', additional.length ? t("Checks and additional results ({count})", { count: additional.length }) : t("Run validation")]] : []),
        ['settings', t("Settings used")], ['queries', t("{n} queries", { n: selectedStep.skill ? selectedStep.skill.queries.length : selectedStep.result.provenance.queries.length })], ['sources', t("Sources")]
      ]).map(([value,label]) => ({value,label}))} />
      <div id={`run-panel-${tab}`} role="tabpanel" aria-labelledby={`run-tab-${tab}`} className={styles.runTabPanel}>
        {tab === "result" && <>{!selectedStep.result.primary?.title || selectedStep.result.primary.title !== stepFinding(selectedStep, t) ? <strong className={styles.runFinding}>{stepFinding(selectedStep, t)}</strong> : null}<RunResultChart artifact={selectedStep.result.primary} />
          <ResultView result={selectedStep.skill && selectedStep.result.primary ? { ...selectedStep.result, primary: { ...selectedStep.result.primary, title: t("Query results") } } : selectedStep.result} titles={byRef} showRunLink={false} showEvidence={false} expanded /></>}
        {tab === "settings" && <><RunSettings record={selectedStep} titles={byRef} manifest={manifests?.find(m => m.name === selectedStep.step.method)} /><div className={styles.runTechnical}><h3>{t("Shared analysis scope")}</h3><dl><div><dt>{t("Analysis period")}</dt><dd>{scope.date_range?.join(" ~ ") || t("All periods")}</dd></div><div><dt>{t("Date basis")}</dt><dd>{timeTitle || t("Not set")}</dd></div></dl></div>{scope.filters?.length ? <div className={styles.runFilterSummary}><strong>{t("Shared filters")}</strong><p>{readableValue(scope.filters, byRef, t)}</p></div> : null}</>}
        {tab === "queries" && (selectedStep.skill ? <SkillQueryActivity key={current} skill={selectedStep.skill} titles={byRef} /> : <RunQueries result={selectedStep.result} />)}
        {tab === "additional" && <><section className={styles.runChecks}><h3>{t("Run validation")}</h3>{selectedStep.result.validation.length ? <ul>{selectedStep.result.validation.map((item, index) => <li key={index}><span>{item.status === "pass" ? t("Passed") : item.status === "warning" ? t("Caution") : t("Not met")}</span><p>{item.message}</p></li>)}</ul> : <p>{t("No validation checks were recorded.")}</p>}</section>{selectedStep.result.warnings.length > 0 && <section className={styles.runChecks}><h3>{t("Notes for interpretation")}</h3><ul>{selectedStep.result.warnings.map((warning, index) => <li key={index}><p>{warning}</p></li>)}</ul></section>}{additional.map((artifact, index) => <ArtifactView key={index} artifact={artifact} titles={byRef} expanded />)}</>}
        {tab === "sources" && <><RunProcedure run={run} detailed /><div className={styles.runSourceActions}><button type="button" className="ghost" onClick={() => setSnapshotOpen(true)}>{selectedStep.skill ? t("View execution-time instructions") : t("Execution-time Python code")}</button></div><RunSources result={selectedStep.result} titles={byRef} author={selectedStep.author} />{run.author && JSON.stringify(run.author) !== JSON.stringify(selectedStep.author) && <AuthorInfo author={run.author} label={t("Product that started the analysis")} />}{run.conclusion_author && JSON.stringify(run.conclusion_author) !== JSON.stringify(selectedStep.author) && <AuthorInfo author={run.conclusion_author} label={t("Product and model that wrote the conclusion")} />}<div className={styles.runTechnical}><dl><div><dt>{t("Run ID")}</dt><dd>{run.id}</dd></div><div><dt>{t("Started at")}</dt><dd>{new Date(run.created_at).toLocaleString()}</dd></div></dl></div></>}
      </div>
    </section> : !run.needs_input && <div className={styles.placeholder}><History size={20} />{t("No analysis steps have run yet.")}</div>}
    <InspectorDialog title={selectedStep?.skill ? t("Execution-time Skill instructions") : t("Execution-time Python code")} open={snapshotOpen} onClose={() => setSnapshotOpen(false)}>
      {selectedStep?.skill ? <><p>v{selectedStep.skill.guide.version}  {t("/ instructions saved at execution")}</p><MethodMarkdown content={selectedStep.skill.guide.markdown} /><p className={styles.contentHash}>SHA-256 {selectedStep.skill.guide.sha256}</p></> : <SourceEvidence source={selectedStep?.code} historical />}
    </InspectorDialog>
    <RunGoals run={run} mine={mine} onSelect={index => { setOpen(index); setTab("result"); }} />
    {(canContinue || canConclude) && manifests && <section className={styles.continueActions} aria-label={t("Continue analysis")}><div><h3>{t("Next action")}</h3><p>{t("Continue the analysis or write a conclusion from the results.")}</p></div><div>
      {canContinue && <button type="button" className="ghost" onClick={() => setContinueMode("step")}>{t("Add analysis step")}</button>}
      {canConclude && <button type="button" onClick={() => setContinueMode("conclusion")}>{t("Write conclusion")}</button>}</div>
      <InspectorDialog title={continueMode === "step" ? t("Next analysis step") : t("Write an analysis conclusion")} open={continueMode !== null} onClose={() => setContinueMode(null)}><NextStep key={`${run.id}:${run.steps.length}`} run={run} allowSteps={canContinue} mode={continueMode ?? "step"} manifests={manifests} objects={objects} onDone={() => { setContinueMode(null); setOpen(null); reload(); }} /></InspectorDialog>
    </section>}
    {!run.preview && showRegistration && reusableSteps.length > 0 && <section className={styles.runRecipeDecision} aria-label={t("Register Recipe")}>
      <div><h2>{registered ? (registered.status === "published" ? t("This Recipe is already published") : t("Recipe draft saved")) : hasAdditionalAnalysis ? t("Save as a new Recipe including the additional analysis") : t("Save this analysis procedure as a Recipe")}</h2><p>{registered ? (registered.status === "published" ? t("Run the published procedure again for a new period.") : t("Review inputs and content, then publish to reuse.")) : hasAdditionalAnalysis ? t("Saves a separate Recipe; the original is kept.") : t("{count} steps · groups reselected from previous results on each run.", { count: run.steps.length })}</p></div>
      <div className={styles.runDraftActions}>{registered ? <Link className={styles.runPrimary} href={`/recipes/${encodeURIComponent(registered.name)}${registered.status === "published" ? "" : "/edit"}`}><Check size={16} />{registered.status === "published" ? t("View Recipe") : t("Review Recipe draft")}</Link>
        : <button type="button" className={styles.runPrimary} disabled={!canRegister || registering} onClick={registerRecipe}>{registering ? <LoaderCircle className={styles.spinning} size={16} /> : <BookPlus size={16} />}{registering ? t("Registering…") : t("Register as Recipe")}</button>}
        <Link className={styles.runEditLink} href={`/recipes/new?${candidateParams.toString()}`}><SlidersHorizontal size={14} />{t("Edit and save")}</Link></div>
      {rejectedCalculations > 0 && !registered && <p className={styles.runActionNote}>{t("Calculations that did not pass validation")} {rejectedCalculations}{t("are saved with their settings and checks. Failed checks stop a rerun; no fallback comparison is used.")}</p>}
      {!canRegister && !registered && <p className={styles.runActionNote}>{canConclude ? t("Save a conclusion first. Fix incomplete or refused steps with Edit and save.") : t("Register completed analyses. Edit to fix or exclude incomplete or refused steps.")}</p>}
      {registerError && <p className={styles.inlineError} role="alert">{registerError}</p>}
    </section>}
    {((recipe && !run.preview && !run.running) || canShare) && <footer className={styles.runFooterActions} aria-label={t("Run actions")}>
      {recipe && !run.preview && !run.running && <Link className={styles.secondaryLink} href={`/recipes/${encodeURIComponent(recipe.name)}`}>{stopped || run.status === "failed" ? t("Change Recipe conditions and run again") : t("View Recipe")}</Link>}
      {canShare && <button type="button" className={styles.secondaryLink} onClick={() => shareDialog.current?.showModal()}><Share2 size={15} />{t("Sharing settings")}</button>}
    </footer>}
    {canShare && <dialog ref={shareDialog} className={styles.runDialog} aria-label={t("Sharing settings")}><header><h2>{t("Share run")}</h2><button type="button" aria-label={t("Close")} title={t("Close")} onClick={() => shareDialog.current?.close()}><X size={18} /></button></header><Share run={run} onDone={() => { reload(); shareDialog.current?.close(); }} /></dialog>}
  </div>;
}

function Share({ run, onDone }: { run: Run; onDone: () => void }) {
  const t = useT();
  const [text, setText] = useState(run.shared_with.join(", "));
  const [err, setErr] = useState<string | null>(null);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api(`/runs/${run.id}:share`, { body: { subjects: text.split(",").map((x) => x.trim()).filter(Boolean) } });
      onDone();
    } catch (x) { setErr((x as Error).message); }
  }
  return (
    <form onSubmit={save} className={styles.shareForm}>
      <label htmlFor="run-share-subjects">{t("User IDs to share with")}</label>
      <input id="run-share-subjects" value={text} onChange={(e) => setText(e.target.value)} placeholder={t("e.g. {example}", { example: "analyst@company.com" })} />
      <button type="submit" className="ghost">{t("Save sharing settings")}</button>
      <span className="hint">{t("Only users with metric access can view this Run.")}</span>
      {err && <span className={styles.inlineError}>{err}</span>}
    </form>
  );
}

function NextStep({ run, allowSteps, mode, manifests, objects, onDone }: {
  run: Run; allowSteps: boolean; mode: "step" | "conclusion"; manifests: MethodManifest[]; objects: ReturnType<typeof useCatalog>["objects"]; onDone: () => void;
}) {
  const recipe = run.recipe_snapshot;
  const allowed = recipe && !run.recipe_invocation?.completed ? (recipe.mode === "investigation" ? recipe.allowed_methods : [...new Set(recipe.steps.map((s) => s.method))])
    : manifests.map((m) => m.name);
  const [method, setMethod] = useState(allowed[0] ?? "");
  const [bindings, setBindings] = useState<Record<string, string | string[] | undefined>>({});
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [summary, setSummary] = useState("");
  const [purpose, setPurpose] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [outcomes, setOutcomes] = useState(() => suggestedOutcomes(run));
  const [goalId, setGoalId] = useState(run.goals?.[0]?.id || "");
  const t = useT();
  const manifest = manifests.find((m) => m.name === method);
  const scopeMetrics = recipe ? [recipe.semantic_scope.primary_metric, ...recipe.semantic_scope.related_metrics] : undefined;

  async function step(e: React.FormEvent) {
    e.preventDefault();
    if (mode !== "step" || !allowSteps) return;
    setBusy(true);
    setErr(null);
    try {
      await api<Result>(`/runs/${run.id}/steps`, { body: { method, purpose, bindings: clean(bindings), params: clean(params), goal_ids: goalId ? [goalId] : [], exploration: !!run.recipe_invocation?.completed } });
      setBindings({});
      setParams({});
      setPurpose("");
      onDone();
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function complete() {
    if (busy) return;
    setBusy(true); setErr(null);
    try {
      await api(`/runs/${run.id}:complete`, { body: { author: { client_name: "Decision Layer Web", client_source: "client_reported" }, conclusion: { answer: summary,
        findings: run.steps.map((record, index) => ({ text: stepFinding(record, t), step_indices: [index] })), limitations: [], goal_outcomes: outcomes } } });
      onDone();
    } catch (x) {
      setErr((x as Error).message);
    } finally { setBusy(false); }
  }

  return (
    <form onSubmit={step} className={styles.nextStep}>
      {allowSteps && mode === "step" && <><h3>{t("Next analysis step")}</h3>
      {(run.goals?.length || 0) > 1 && <label className="field"><span className="label">{t("Question to address")}</span><select value={goalId} onChange={event => setGoalId(event.target.value)}>{run.goals?.map(goal => <option key={goal.id} value={goal.id}>{goal.description}</option>)}</select></label>}
      {recipe?.instructions && <p className="hint pre">{recipe.instructions}</p>}
      <label className="field"><span className="label">Method</span>
        <select value={method} onChange={(e) => { setMethod(e.target.value); setBindings({}); setParams({}); }}>
          {allowed.map((m) => <option key={m} value={m}>{methodName(m, t)}</option>)}
        </select>
      </label>
      {manifest && <MethodInputs manifest={manifest} objects={objects} bindings={bindings} params={params}
        onBindings={setBindings} onParams={setParams} restrictMeasures={scopeMetrics} />}
      <label className="field"><span className="label">{t("What this step checks")}</span><input value={purpose} onChange={event => setPurpose(event.target.value)} maxLength={240} required={run.origin === "mcp"} /></label>
      <button type="submit" disabled={busy || (run.origin === "mcp" && !purpose.trim())}>{busy ? t("Running…") : t("Run step")}</button></>}
      {mode === "conclusion" && <><label className="field"><span className="label">{t("Conclusion (when closing)")}</span>
        <textarea rows={2} value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
      {!!run.goals?.length && run.goals.map((goal, index) => <div key={goal.id}><label className="field"><span className="label">{goal.description}</span><select value={outcomes[index]?.status || "inconclusive"} onChange={event => setOutcomes(items => items.map((item, i) => i === index ? { ...item, status: event.target.value as typeof item.status } : item))}>{["supported", "needs_input", "unsupported", "blocked", "inconclusive"].map(status => <option key={status} value={status}>{t(({ supported: "Evidence recorded", needs_input: "Input needed", unsupported: "Not supported", blocked: "Execution blocked", inconclusive: "Unable to judge" } as Record<string, string>)[status])}</option>)}</select></label>{outcomes[index]?.status !== "supported" && <label className="field"><span className="label">{t("Reason this part is unresolved")}</span><input value={outcomes[index]?.reason || ""} onChange={event => setOutcomes(items => items.map((item, i) => i === index ? { ...item, reason: event.target.value } : item))} /></label>}</div>)}
      <button type="button" className={styles.closeButton} disabled={busy || !summary.trim() || (!run.steps.length && !run.goals?.length)} onClick={complete}>{t("Save conclusion and complete")}</button></>}
      {err && <p className={styles.inlineError} role="alert">{err}</p>}
    </form>
  );
}
