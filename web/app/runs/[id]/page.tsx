"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BookPlus, Check, History, LoaderCircle, Share2, SlidersHorizontal, X } from "lucide-react";

import { clean, MethodInputs } from "@/components/forms";
import { ArtifactView, ResultView, ValidationList } from "@/components/result";
import { RunGraph } from "@/components/run-graph";
import { RunDelete } from "@/components/run-delete";
import { RunResultChart } from "@/components/run-result-chart";
import { RunQueries, RunSettings, RunSources, readableValue } from "@/components/run-evidence";
import { api, MethodManifest, Recipe, Result, Run } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { methodName } from "@/lib/method-name";
import { runOriginLabel } from "@/lib/run-origin";
import { stepFinding, stepPurpose } from "@/lib/run-story";
import styles from "../../library.module.css";

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: run, error, reload } = useApi<Run>(`/runs/${id}`);
  const { data: manifests } = useApi<MethodManifest[]>("/methods");
  const { objects, byRef } = useCatalog();
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
  if (!run) return <div className={styles.page}><div className={styles.skeleton} /></div>;
  const recipe = run.recipe_snapshot;
  const current = open ?? run.steps.length - 1;
  const lastStatus = run.steps.at(-1)?.result.status;
  const stopped = run.status === "open" && !run.running && (lastStatus === "refused" || lastStatus === "needs_input");
  const successfulSteps = run.steps.flatMap((step, index) => step.result.status === "success" ? [index] : []);
  const candidateParams = new URLSearchParams({ from_run: run.id });
  successfulSteps.forEach((index) => candidateParams.append("step", String(index)));
  const canRegister = run.status === "completed" && !run.running && successfulSteps.length === run.steps.length && successfulSteps.length > 0;
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
    return typeof metric === "string" && metric.startsWith("cube://") ? [metric] : [];
  }))];
  if (recipe?.semantic_scope.primary_metric && !metricRefs.includes(recipe.semantic_scope.primary_metric)) metricRefs.unshift(recipe.semantic_scope.primary_metric);
  const metricNames = metricRefs.map((ref) => byRef.get(ref)?.title ?? "지표 이름 확인 필요");
  const canContinue = mine && !run.preview && run.status === "open" && !run.running && !!manifests && recipe?.mode !== "pipeline";
  const canShare = mine && !run.preview && !run.caller.subject?.startsWith("service:");
  const selectedStep = run.steps[current];
  const additional = selectedStep?.result.artifacts.filter(artifact => !Array.isArray(artifact.data) || artifact.data.length > 0) ?? [];
  const warnings = [...new Map([...run.validation, ...run.steps.flatMap((step) => step.result.validation)]
    .filter((item) => item.status !== "pass").map((item) => [`${item.code}:${item.message}`, item])).values()];
  return <div className={`${styles.page} ${styles.runPage}`}>
    <Link className={styles.back} href="/runs"><ArrowLeft size={15} />실행 기록</Link>
    <div className={styles.heading}><div><p className={styles.eyebrow}>{run.preview ? "미리보기" : "RUN"} · {runOriginLabel(run.origin)} · {new Date(run.created_at).toLocaleString()}</p><h1>{run.plan.question || recipe?.description || recipe?.name || (metricNames[0] ? `${metricNames[0]} 분석` : "분석 결과")}</h1></div><div className={styles.runHeaderActions}><span className={`${styles.badge} ${run.status === "failed" || stopped ? styles.badgeFailed : run.status === "open" ? styles.badgeOpen : ""}`}>{run.status === "completed" ? "완료" : run.status === "failed" ? "실패" : stopped ? lastStatus === "needs_input" ? "입력 필요" : "중단" : "진행 중"}</span>{mine && <RunDelete run={run} onDeleted={() => router.push("/runs")} />}</div></div>
    <p className={styles.runScope}><strong>{metricNames.join(" · ") || "지표 선택 전"}</strong><span>{scope.date_range?.join(" ~ ") || "전체 기간"}</span>{timeTitle && <span>{timeTitle} 기준</span>}</p>
    {!run.preview && successfulSteps.length > 0 && <section className={styles.runRecipeDecision} aria-label="Recipe 등록">
      <div><h2>{registered ? "Recipe로 등록했습니다" : "이 분석 절차를 Recipe로 저장"}</h2><p>{registered ? "분석 라이브러리와 MCP에서 바로 실행할 수 있습니다." : `${run.steps.length}단계 · 사용한 지표, 설정, 기간과 필터를 그대로 가져옵니다.`}</p></div>
      <div className={styles.runDraftActions}>{registered ? <Link className={styles.runPrimary} href={`/recipes/${encodeURIComponent(registered.name)}`}><Check size={16} />Recipe 보기</Link>
        : <button type="button" className={styles.runPrimary} disabled={!canRegister || registering} onClick={registerRecipe}>{registering ? <LoaderCircle className={styles.spinning} size={16} /> : <BookPlus size={16} />}{registering ? "등록 중…" : "Recipe로 등록"}</button>}
        <Link className={styles.runEditLink} href={`/recipes/new?${candidateParams.toString()}`}><SlidersHorizontal size={14} />편집해서 저장</Link></div>
      {!canRegister && !registered && <p className={styles.runActionNote}>완료된 분석은 바로 등록할 수 있습니다. 성공한 단계만 저장하려면 편집해서 저장하세요.</p>}
      {registerError && <p className={styles.inlineError} role="alert">{registerError}</p>}
    </section>}
    {run.running && <p className={styles.runNotice} role="status">분석 중 · {run.running.method ? methodName(run.running.method) : run.running.kind} · {new Date(run.running.started_at).toLocaleTimeString()} 시작</p>}
    {run.error && <p className={styles.error} role="alert">{run.error.message} · 오류 코드 {run.error.code}</p>}
    <section className={styles.runAnswer} aria-label="분석 답변"><span>{run.summary ? "분석 결론" : "분석 상태"}</span><p>{run.summary || (run.running ? "분석이 진행 중입니다." : run.steps.length ? "결론이 아직 기록되지 않았습니다. 단계별 결과를 확인하세요." : "아직 실행된 분석 단계가 없습니다.")}</p>
      {warnings.length > 0 && <ValidationList items={warnings} />}</section>
    <RunGraph run={run} titles={byRef} selected={current} onSelect={index => { setOpen(index); setTab("result"); }} />
    {selectedStep ? <section className={styles.runStepDetail}><span>{current + 1} / {run.steps.length}단계</span><h2>{methodName(selectedStep.step.method)}</h2><p className={styles.runPurpose}><span>분석 목적</span>{stepPurpose(selectedStep.step)}</p>
      <div className={styles.runTabs} role="tablist" aria-label="분석 단계 정보" onKeyDown={event => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault(); const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>("[role=tab]")];
        const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
        const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
        buttons[next].focus(); buttons[next].click();
      }}>{([['result', '결과'], ...(additional.length ? [['additional', `추가 결과 ${additional.length}개`]] : []), ['settings', '사용한 설정'], ['queries', `쿼리 ${selectedStep.result.provenance.queries.length}개`], ['sources', '출처']]).map(([value, label]) =>
        <button key={value} id={`run-tab-${value}`} type="button" role="tab" aria-selected={tab === value} aria-controls="run-step-panel" tabIndex={tab === value ? 0 : -1} onClick={() => setTab(value)}>{label}</button>)}</div>
      <div id="run-step-panel" role="tabpanel" aria-labelledby={`run-tab-${tab}`} className={styles.runTabPanel}>
        {tab === "result" && <><strong className={styles.runFinding}>{stepFinding(selectedStep)}</strong><RunResultChart artifact={selectedStep.result.primary} />
          <ResultView result={selectedStep.result} titles={byRef} showRunLink={false} showEvidence={false} expanded /></>}
        {tab === "settings" && <><div className={styles.runTechnical}><dl><div><dt>분석 기간</dt><dd>{scope.date_range?.join(" ~ ") || "전체 기간"}</dd></div><div><dt>날짜 기준</dt><dd>{timeTitle || "지정 안 함"}</dd></div></dl></div><RunSettings record={selectedStep} titles={byRef} />{scope.filters?.length ? <div className={styles.runFilterSummary}><strong>공통 필터</strong><p>{readableValue(scope.filters, byRef)}</p></div> : null}</>}
        {tab === "queries" && <RunQueries result={selectedStep.result} />}
        {tab === "additional" && additional.map((artifact, index) => <ArtifactView key={index} artifact={artifact} titles={byRef} expanded />)}
        {tab === "sources" && <><RunSources result={selectedStep.result} titles={byRef} /><div className={styles.runTechnical}><dl><div><dt>실행 ID</dt><dd>{run.id}</dd></div><div><dt>시작 시각</dt><dd>{new Date(run.created_at).toLocaleString()}</dd></div></dl></div></>}
      </div>
    </section> : <div className={styles.placeholder}><History size={20} />아직 실행된 분석 단계가 없습니다.</div>}
    {recipe && !run.preview && !run.running && <Link className={styles.secondaryLink} href={`/recipes/${encodeURIComponent(recipe.name)}`}>{stopped || run.status === "failed" ? "Recipe 조건을 바꿔 다시 실행" : "Recipe 보기"}</Link>}
    {canContinue && manifests && <section className={styles.formPanel}><NextStep run={run} manifests={manifests} objects={objects} onDone={() => { setOpen(null); reload(); }} /></section>}
    {canShare && <><button type="button" className={styles.secondaryLink} onClick={() => shareDialog.current?.showModal()}><Share2 size={15} />공유 설정</button><dialog ref={shareDialog} className={styles.runDialog} aria-label="공유 설정"><header><h2>실행 기록 공유</h2><button type="button" aria-label="닫기" title="닫기" onClick={() => shareDialog.current?.close()}><X size={18} /></button></header><Share run={run} onDone={() => { reload(); shareDialog.current?.close(); }} /></dialog></>}
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
      <span className="hint">Cube에서 지표 접근 권한이 있는 사용자만 이 기록을 열 수 있습니다.</span>
      {err && <span className={styles.inlineError}>{err}</span>}
    </form>
  );
}

function NextStep({ run, manifests, objects, onDone }: {
  run: Run; manifests: MethodManifest[]; objects: ReturnType<typeof useCatalog>["objects"]; onDone: () => void;
}) {
  const recipe = run.recipe_snapshot;
  const allowed = recipe ? (recipe.mode === "investigation" ? recipe.allowed_methods : [...new Set(recipe.steps.map((s) => s.method))])
    : manifests.map((m) => m.name);
  const [method, setMethod] = useState(allowed[0] ?? "");
  const [bindings, setBindings] = useState<Record<string, string | string[] | undefined>>({});
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [summary, setSummary] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const t = useT();
  const manifest = manifests.find((m) => m.name === method);
  const scopeMetrics = recipe ? [recipe.semantic_scope.primary_metric, ...recipe.semantic_scope.related_metrics] : undefined;

  async function step(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api<Result>(`/runs/${run.id}/steps`, { body: { method, bindings: clean(bindings), params: clean(params) } });
      setBindings({});
      setParams({});
      onDone();
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function complete() {
    try {
      await api(`/runs/${run.id}:complete`, { body: { summary: summary || null } });
      onDone();
    } catch (x) {
      setErr((x as Error).message);
    }
  }

  return (
    <form onSubmit={step} className={styles.nextStep}>
      <h3>다음 분석 단계</h3>
      {recipe?.instructions && <p className="hint pre">{recipe.instructions}</p>}
      <label className="field"><span className="label">Method</span>
        <select value={method} onChange={(e) => { setMethod(e.target.value); setBindings({}); setParams({}); }}>
          {allowed.map((m) => <option key={m} value={m}>{methodName(m)}</option>)}
        </select>
      </label>
      {manifest && <MethodInputs manifest={manifest} objects={objects} bindings={bindings} params={params}
        onBindings={setBindings} onParams={setParams} restrictMeasures={scopeMetrics} />}
      <button type="submit" disabled={busy}>{busy ? t("Running…") : t("Run step")}</button>
      <label className="field"><span className="label">{t("Conclusion (when closing)")}</span>
        <textarea rows={2} value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
      <button type="button" className={styles.closeButton} onClick={complete}>{t("Close investigation")}</button>
      {err && <p className={styles.inlineError} role="alert">{err}</p>}
    </form>
  );
}
