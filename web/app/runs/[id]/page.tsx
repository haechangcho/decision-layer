"use client";
import { LoadingState } from "@/components/loading-indicator";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BookPlus, Check, History, LoaderCircle, Share2, SlidersHorizontal, X } from "lucide-react";

import { clean, MethodInputs } from "@/components/forms";
import { ArtifactView, ResultView } from "@/components/result";
import { RunGraph } from "@/components/run-graph";
import { RunAnswer } from "@/components/run-answer";
import { RunGoals, suggestedOutcomes } from "@/components/run-goals";
import { RunRemediations } from "@/components/run-remediation";
import { RunDelete } from "@/components/run-delete";
import { RunProcedure } from "@/components/run-procedure";
import { RunResultChart } from "@/components/run-result-chart";
import { RunPeriodInput, periodLabel } from "@/components/run-period-input";
import { AuthorInfo, RunQueries, RunSettings, RunSources, readableValue } from "@/components/run-evidence";
import { api, MethodManifest, Recipe, Result, Run } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { methodName } from "@/lib/method-name";
import { runOriginLabel } from "@/lib/run-origin";
import { isSourcePurpose, stepFinding, stepPurpose } from "@/lib/run-story";
import styles from "../../library.module.css";

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: run, error, reload } = useApi<Run>(`/runs/${id}`);
  const { data: manifests } = useApi<MethodManifest[]>("/methods");
  const { objects, byRef, reload: reloadCatalog } = useCatalog();
  const { data: me } = useApi<{ subject: string }>("/me");
  const [open, setOpen] = useState<number | null>(null);
  const [tab, setTab] = useState<string>("result");
  const [registering, setRegistering] = useState(false);
  const [registered, setRegistered] = useState<Recipe | null>(null);
  const [registerError, setRegisterError] = useState("");
  const shareDialog = useRef<HTMLDialogElement>(null);
  const mine = !!me && me.subject === run?.caller.subject;
  useEffect(() => {                                   // a background job is running: refresh until it ends
    if (!run?.running) return;
    const t = setTimeout(reload, 2000);
    return () => clearTimeout(t);
  }, [run, reload]);

  if (error) return <div className={styles.page}><p className={styles.error} role="alert">{error.message}</p><Link className={styles.back} href="/runs"><ArrowLeft size={15} />실행 기록</Link></div>;
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
    catch (cause) { setRegisterError(cause instanceof Error ? cause.message : "Recipe를 등록하지 못했습니다."); }
    finally { setRegistering(false); }
  }

  const scope = run.plan.scope;
  const timeTitle = scope.time_dimension ? byRef.get(scope.time_dimension)?.title ?? "날짜 기준 이름 확인 필요" : null;
  const metricRefs = [...new Set(run.steps.flatMap((record) => {
    const metric = record.step.bindings.metric;
    return typeof metric === "string" && /^[a-z][a-z0-9_-]*:\/\//.test(metric) ? [metric] : [];
  }))];
  if (recipe?.semantic_scope.primary_metric && !metricRefs.includes(recipe.semantic_scope.primary_metric)) metricRefs.unshift(recipe.semantic_scope.primary_metric);
  const pendingMetric = run.pending_execution?.step?.bindings.metric;
  if (typeof pendingMetric === "string" && !pendingMetric.startsWith("$") && !metricRefs.includes(pendingMetric)) metricRefs.push(pendingMetric);
  const metricNames = metricRefs.map((ref) => byRef.get(ref)?.title ?? "지표 이름 확인 필요");
  const canContinue = mine && !run.preview && !run.needs_input && run.status === "open" && !run.running && !!manifests && (recipe?.mode !== "pipeline" || !!run.recipe_invocation?.completed);
  const canConclude = mine && !run.preview && run.status === "open" && !run.running &&
    ((!run.needs_input && run.steps.length > 0) || (!!run.goals?.length && !run.steps.length));
  const canShare = mine && !run.preview && !run.caller.subject?.startsWith("service:");
  const selectedStep = run.steps[current];
  const additional = selectedStep?.result.artifacts.filter(artifact => !Array.isArray(artifact.data) || artifact.data.length > 0) ?? [];
  const warnings = [...new Map([...run.validation, ...run.steps.flatMap((step) => step.result.validation)]
    .filter((item) => item.status !== "pass").map((item) => [`${item.code}:${item.message}`, item])).values()];
  return <div className={`${styles.page} ${styles.runPage}`}>
    <Link className={styles.back} href="/runs"><ArrowLeft size={15} />실행 기록</Link>
    <header className={styles.runOverview} aria-label="질문과 실행 정보">
    <div className={styles.heading}><div><p className={styles.eyebrow}>{run.preview ? "미리보기" : "RUN"} · {runOriginLabel(run.origin)} · {new Date(run.created_at).toLocaleString()}</p><h1>{run.plan.question || recipe?.description || recipe?.name || (metricNames[0] ? `${metricNames[0]} 분석` : "분석 결과")}</h1></div><div className={styles.runHeaderActions}><span className={`${styles.badge} ${run.status === "failed" || stopped ? styles.badgeFailed : run.status === "open" ? styles.badgeOpen : ""}`}>{run.status === "completed" ? "완료" : run.status === "failed" ? "실패" : stopped ? lastStatus === "needs_input" ? "입력 필요" : "중단" : run.running ? "진행 중" : run.steps.length ? "결론 대기" : "대기 중"}</span>{mine && <RunDelete run={run} onDeleted={() => router.push("/runs")} />}</div></div>
    <p className={styles.runScope}><strong>{metricNames.join(" · ") || "지표 선택 전"}</strong><span>{periodLabel(run)}</span>{timeTitle && <span>{timeTitle} 기준</span>}{run.scope_resolution?.source && <span>{({ caller: "호출자 선택", conversation: "대화에서 이어받음", ai_proposal: "AI 제안", recipe_default: "Recipe 기본 기간", organization_default: "조직 기본 기간", unspecified: "아직 선택하지 않음" } as Record<string, string>)[run.scope_resolution.source] || "선택 출처 미확인"}</span>}</p>
    <RunProcedure run={run} detailed />
    </header>
    {mine && run.needs_input && <RunPeriodInput key={`${run.id}:${run.scope_revision}`} run={run} objects={objects} onDone={() => reload()} />}
    {!run.preview && showRegistration && reusableSteps.length > 0 && <section className={styles.runRecipeDecision} aria-label="Recipe 등록">
      <div><h2>{registered ? "Recipe로 등록했습니다" : hasAdditionalAnalysis ? "추가 분석을 포함해 새 Recipe로 저장" : "이 분석 절차를 Recipe로 저장"}</h2><p>{registered ? "레시피 목록과 MCP에서 바로 실행할 수 있습니다." : hasAdditionalAnalysis ? "기존 Recipe는 유지하고, 이번 분석 절차를 별도로 저장합니다." : `${run.steps.length}단계 · 분석 대상은 실행할 때마다 앞 단계 결과에서 다시 선택합니다.`}</p></div>
      <div className={styles.runDraftActions}>{registered ? <Link className={styles.runPrimary} href={`/recipes/${encodeURIComponent(registered.name)}`}><Check size={16} />Recipe 보기</Link>
        : <button type="button" className={styles.runPrimary} disabled={!canRegister || registering} onClick={registerRecipe}>{registering ? <LoaderCircle className={styles.spinning} size={16} /> : <BookPlus size={16} />}{registering ? "등록 중…" : "Recipe로 등록"}</button>}
        <Link className={styles.runEditLink} href={`/recipes/new?${candidateParams.toString()}`}><SlidersHorizontal size={14} />편집해서 저장</Link></div>
      {rejectedCalculations > 0 && !registered && <p className={styles.runActionNote}>검증을 통과하지 못한 계산 {rejectedCalculations}개도 절차로 저장합니다. 설정과 검증 기준은 유지되며, 재실행에서 기준을 충족하지 못하면 중단합니다. 보조 비교로 자동 전환하지 않습니다.</p>}
      {!canRegister && !registered && <p className={styles.runActionNote}>{canConclude ? "분석 결론을 저장하면 등록할 수 있습니다. 입력 부족이나 계산 전 거부 단계가 있다면 편집해서 저장하세요." : "완료된 분석은 바로 등록할 수 있습니다. 입력 부족이나 계산 전 거부 단계는 편집해서 저장에서 제외하거나 수정하세요."}</p>}
      {registerError && <p className={styles.inlineError} role="alert">{registerError}</p>}
    </section>}
    {run.running && <p className={styles.runNotice} role="status">분석 중 · {run.running.method ? methodName(run.running.method) : run.running.kind} · {new Date(run.running.started_at).toLocaleTimeString()} 시작</p>}
    {run.error && <p className={styles.error} role="alert">{run.error.message} · 오류 코드 {run.error.code}</p>}
    {(!run.needs_input || run.steps.length > 0) && <><RunAnswer run={run} warnings={warnings} onSelect={index => { setOpen(index); setTab("result"); document.getElementById("run-step-detail")?.scrollIntoView({ behavior: "smooth", block: "start" }); }} />
    <RunGoals run={run} mine={mine} onSelect={index => { setOpen(index); setTab("result"); }} />
    <RunRemediations run={run} mine={mine} objects={objects} onDone={() => { reload(); reloadCatalog(); }} />
    <RunGraph run={run} titles={byRef} selected={current} onSelect={index => { setOpen(index); setTab("result"); }} /></>}
    {selectedStep ? <section id="run-step-detail" className={styles.runStepDetail}><span>{current + 1} / {run.steps.length}단계</span><h2>{methodName(selectedStep.step.method)}</h2><p className={styles.runPurpose}><span>분석 목적</span>{stepPurpose(selectedStep.step, run)}</p>
      {isSourcePurpose(selectedStep.step, run) && selectedStep.step.purpose && <div className={styles.runPurposeContext}><p><strong>이번 실행 기간</strong> {periodLabel(run)}</p><p><strong>등록 당시 단계 설명</strong> {selectedStep.step.purpose}</p><span>이 설명은 원래 분석에서 가져왔습니다. 실제 적용 범위는 이번 실행 기간과 사용한 설정에서 확인하세요.</span></div>}
      <div className={styles.runTabs} role="tablist" aria-label="분석 단계 정보" onKeyDown={event => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault(); const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>("[role=tab]")];
        const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
        const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
        buttons[next].focus(); buttons[next].click();
      }}>{([['result', '결과'], ...(additional.length || selectedStep.result.validation.length || selectedStep.result.warnings.length ? [['additional', additional.length ? `검증·추가 결과 ${additional.length}개` : '실행 검증']] : []), ['settings', '사용한 설정'], ['queries', `쿼리 ${selectedStep.result.provenance.queries.length}개`], ['sources', '출처']]).map(([value, label]) =>
        <button key={value} id={`run-tab-${value}`} type="button" role="tab" aria-selected={tab === value} aria-controls="run-step-panel" tabIndex={tab === value ? 0 : -1} onClick={() => setTab(value)}>{label}</button>)}</div>
      <div id="run-step-panel" role="tabpanel" aria-labelledby={`run-tab-${tab}`} className={styles.runTabPanel}>
        {tab === "result" && <><strong className={styles.runFinding}>{stepFinding(selectedStep)}</strong><RunResultChart artifact={selectedStep.result.primary} />
          <ResultView result={selectedStep.result} titles={byRef} showRunLink={false} showEvidence={false} expanded /></>}
        {tab === "settings" && <><RunSettings record={selectedStep} titles={byRef} manifest={manifests?.find(m => m.name === selectedStep.step.method)} /><div className={styles.runTechnical}><h3>공통 분석 범위</h3><dl><div><dt>분석 기간</dt><dd>{scope.date_range?.join(" ~ ") || "전체 기간"}</dd></div><div><dt>날짜 기준</dt><dd>{timeTitle || "지정 안 함"}</dd></div></dl></div>{scope.filters?.length ? <div className={styles.runFilterSummary}><strong>공통 필터</strong><p>{readableValue(scope.filters, byRef)}</p></div> : null}</>}
        {tab === "queries" && <RunQueries result={selectedStep.result} />}
        {tab === "additional" && <><section className={styles.runChecks}><h3>실행 검증</h3>{selectedStep.result.validation.length ? <ul>{selectedStep.result.validation.map((item, index) => <li key={index}><span>{item.status === "pass" ? "통과" : item.status === "warning" ? "주의" : "미충족"}</span><p>{item.message}</p></li>)}</ul> : <p>기록된 검증 항목이 없습니다.</p>}</section>{selectedStep.result.warnings.length > 0 && <section className={styles.runChecks}><h3>해석 시 참고</h3><ul>{selectedStep.result.warnings.map((warning, index) => <li key={index}><p>{warning}</p></li>)}</ul></section>}{additional.map((artifact, index) => <ArtifactView key={index} artifact={artifact} titles={byRef} expanded />)}</>}
        {tab === "sources" && <><RunSources result={selectedStep.result} titles={byRef} author={selectedStep.author} />{run.author && JSON.stringify(run.author) !== JSON.stringify(selectedStep.author) && <AuthorInfo author={run.author} label="분석을 시작한 제품" />}{run.conclusion_author && JSON.stringify(run.conclusion_author) !== JSON.stringify(selectedStep.author) && <AuthorInfo author={run.conclusion_author} label="결론 작성 제품·모델" />}<div className={styles.runTechnical}><dl><div><dt>실행 ID</dt><dd>{run.id}</dd></div><div><dt>시작 시각</dt><dd>{new Date(run.created_at).toLocaleString()}</dd></div></dl></div></>}
      </div>
    </section> : !run.needs_input && <div className={styles.placeholder}><History size={20} />아직 실행된 분석 단계가 없습니다.</div>}
    {(canContinue || canConclude) && manifests && <section className={styles.formPanel}><NextStep key={`${run.id}:${run.steps.length}`} run={run} allowSteps={canContinue} manifests={manifests} objects={objects} onDone={() => { setOpen(null); reload(); }} /></section>}
    {((recipe && !run.preview && !run.running) || canShare) && <footer className={styles.runFooterActions} aria-label="실행 기록 작업">
      {recipe && !run.preview && !run.running && <Link className={styles.secondaryLink} href={`/recipes/${encodeURIComponent(recipe.name)}`}>{stopped || run.status === "failed" ? "Recipe 조건을 바꿔 다시 실행" : "Recipe 보기"}</Link>}
      {canShare && <button type="button" className={styles.secondaryLink} onClick={() => shareDialog.current?.showModal()}><Share2 size={15} />공유 설정</button>}
    </footer>}
    {canShare && <dialog ref={shareDialog} className={styles.runDialog} aria-label="공유 설정"><header><h2>실행 기록 공유</h2><button type="button" aria-label="닫기" title="닫기" onClick={() => shareDialog.current?.close()}><X size={18} /></button></header><Share run={run} onDone={() => { reload(); shareDialog.current?.close(); }} /></dialog>}
  </div>;
}

function Share({ run, onDone }: { run: Run; onDone: () => void }) {
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
      <label htmlFor="run-share-subjects">공유할 사용자 ID</label>
      <input id="run-share-subjects" value={text} onChange={(e) => setText(e.target.value)} placeholder="예: analyst@company.com" />
      <button type="submit" className="ghost">공유 설정 저장</button>
      <span className="hint">연결된 지표에 접근 권한이 있는 사용자만 이 기록을 열 수 있습니다.</span>
      {err && <span className={styles.inlineError}>{err}</span>}
    </form>
  );
}

function NextStep({ run, allowSteps, manifests, objects, onDone }: {
  run: Run; allowSteps: boolean; manifests: MethodManifest[]; objects: ReturnType<typeof useCatalog>["objects"]; onDone: () => void;
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
    try {
      await api(`/runs/${run.id}:complete`, { body: { author: { client_name: "Decision Layer Web", client_source: "client_reported" }, conclusion: { answer: summary,
        findings: run.steps.map((record, index) => ({ text: stepFinding(record), step_indices: [index] })), limitations: [], goal_outcomes: outcomes } } });
      onDone();
    } catch (x) {
      setErr((x as Error).message);
    }
  }

  return (
    <form onSubmit={step} className={styles.nextStep}>
      {allowSteps && <><h3>다음 분석 단계</h3>
      {(run.goals?.length || 0) > 1 && <label className="field"><span className="label">{t("Question to address")}</span><select value={goalId} onChange={event => setGoalId(event.target.value)}>{run.goals?.map(goal => <option key={goal.id} value={goal.id}>{goal.description}</option>)}</select></label>}
      {recipe?.instructions && <p className="hint pre">{recipe.instructions}</p>}
      <label className="field"><span className="label">Method</span>
        <select value={method} onChange={(e) => { setMethod(e.target.value); setBindings({}); setParams({}); }}>
          {allowed.map((m) => <option key={m} value={m}>{methodName(m)}</option>)}
        </select>
      </label>
      {manifest && <MethodInputs manifest={manifest} objects={objects} bindings={bindings} params={params}
        onBindings={setBindings} onParams={setParams} restrictMeasures={scopeMetrics} />}
      <label className="field"><span className="label">이 단계로 확인할 내용</span><input value={purpose} onChange={event => setPurpose(event.target.value)} maxLength={240} required={run.origin === "mcp"} /></label>
      <button type="submit" disabled={busy || (run.origin === "mcp" && !purpose.trim())}>{busy ? t("Running…") : t("Run step")}</button></>}
      <label className="field"><span className="label">{t("Conclusion (when closing)")}</span>
        <textarea rows={2} value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
      {!!run.goals?.length && run.goals.map((goal, index) => <div key={goal.id}><label className="field"><span className="label">{goal.description}</span><select value={outcomes[index]?.status || "inconclusive"} onChange={event => setOutcomes(items => items.map((item, i) => i === index ? { ...item, status: event.target.value as typeof item.status } : item))}>{["supported", "needs_input", "unsupported", "blocked", "inconclusive"].map(status => <option key={status} value={status}>{t(({ supported: "Evidence recorded", needs_input: "Input needed", unsupported: "Not supported", blocked: "Execution blocked", inconclusive: "Unable to judge" } as Record<string, string>)[status])}</option>)}</select></label>{outcomes[index]?.status !== "supported" && <label className="field"><span className="label">{t("Reason this part is unresolved")}</span><input value={outcomes[index]?.reason || ""} onChange={event => setOutcomes(items => items.map((item, i) => i === index ? { ...item, reason: event.target.value } : item))} /></label>}</div>)}
      <button type="button" className={styles.closeButton} disabled={busy || !summary.trim() || (!run.steps.length && !run.goals?.length)} onClick={complete}>결론 저장하고 완료</button>
      {err && <p className={styles.inlineError} role="alert">{err}</p>}
    </form>
  );
}
