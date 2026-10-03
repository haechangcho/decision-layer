"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, History, Plus } from "lucide-react";

import { clean, MethodInputs } from "@/components/forms";
import { ResultView, ValidationList } from "@/components/result";
import { RunGraph } from "@/components/run-graph";
import { RunResultChart } from "@/components/run-result-chart";
import { api, MethodManifest, Result, Run } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { methodName } from "@/lib/method-name";
import { runOriginLabel } from "@/lib/run-origin";
import { stepFinding, stepPurpose } from "@/lib/run-story";
import styles from "../../library.module.css";

const parameterLabels: Record<string, string> = {
  granularity: "시간 단위", vs_previous: "직전 기간 비교", top_n: "표시할 그룹 수",
  min_count: "최소 그룹 건수", rank_by: "정렬 기준", drill_path: "드릴다운 경로",
};
const sourceLabels = { method_default: "Method 기본값", recipe: "Recipe 설정", recipe_fixed: "Recipe 고정값", request: "실행 요청" };
const parameterValue = (value: unknown) => typeof value === "boolean" ? value ? "예" : "아니요"
  : value === "month" ? "월" : value === "week" ? "주" : value === "day" ? "일"
    : typeof value === "string" ? value : JSON.stringify(value);

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const { data: run, error, reload } = useApi<Run>(`/runs/${id}`);
  const { data: manifests } = useApi<MethodManifest[]>("/methods");
  const { objects, byRef } = useCatalog();
  const { data: me } = useApi<{ subject: string }>("/me");
  const [open, setOpen] = useState<number | null>(null);
  const [draftMode, setDraftMode] = useState(false);
  const [draftSteps, setDraftSteps] = useState<number[]>([]);
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
  draftSteps.forEach((index) => candidateParams.append("step", String(index)));

  const scope = run.plan.scope;
  const timeTitle = scope.time_dimension ? byRef.get(scope.time_dimension)?.title ?? "날짜 기준 이름 확인 필요" : null;
  const metricRefs = [...new Set(run.steps.flatMap((record) => {
    const metric = record.step.bindings.metric;
    return typeof metric === "string" && metric.startsWith("cube://") ? [metric] : [];
  }))];
  if (recipe?.semantic_scope.primary_metric && !metricRefs.includes(recipe.semantic_scope.primary_metric)) metricRefs.unshift(recipe.semantic_scope.primary_metric);
  const metricNames = metricRefs.map((ref) => byRef.get(ref)?.title ?? "지표 이름 확인 필요");
  const methods = [...new Set(run.steps.map((record) => methodName(record.step.method)))];
  const canContinue = mine && !run.preview && run.status === "open" && !run.running && !!manifests && recipe?.mode !== "pipeline";
  const canShare = mine && !run.preview && !run.caller.subject?.startsWith("service:");
  const selectedStep = run.steps[current];
  const visibleParams = selectedStep ? Object.entries(selectedStep.step.params).filter(([, value]) => value != null && (!Array.isArray(value) || value.length > 0)) : [];
  const warnings = [...new Map([...run.validation, ...run.steps.flatMap((step) => step.result.validation)]
    .filter((item) => item.status !== "pass").map((item) => [`${item.code}:${item.message}`, item])).values()];
  return <div className={styles.page}>
    <Link className={styles.back} href="/runs"><ArrowLeft size={15} />실행 기록</Link>
    <div className={styles.heading}><div><p className={styles.eyebrow}>{run.preview ? "미리보기" : "RUN"} · {runOriginLabel(run.origin)} · {run.id.slice(-10)}</p><h1>{run.plan.question || recipe?.description || recipe?.name || (metricNames[0] ? `${metricNames[0]} 분석` : "분석 결과")}</h1></div><span className={`${styles.badge} ${run.status === "failed" || stopped ? styles.badgeFailed : run.status === "open" ? styles.badgeOpen : ""}`}>{run.status === "completed" ? "완료" : run.status === "failed" ? "실패" : stopped ? lastStatus === "needs_input" ? "입력 필요" : "중단" : "진행 중"}</span></div>
    <p className={styles.runScope}><strong>{metricNames.join(" · ") || "지표 선택 전"}</strong><span>{scope.date_range?.join(" ~ ") || "전체 기간"}</span>{timeTitle && <span>{timeTitle} 기준</span>}</p>
    {run.running && <p className={styles.runNotice} role="status">분석 중 · {run.running.method ? methodName(run.running.method) : run.running.kind} · {new Date(run.running.started_at).toLocaleTimeString()} 시작</p>}
    {run.error && <p className={styles.error} role="alert">{run.error.message} · 오류 코드 {run.error.code}</p>}
    <section className={styles.runAnswer} aria-label="분석 답변"><span>{run.summary ? "기록된 답" : "분석 상태"}</span><p>{run.summary || (run.running ? "분석이 진행 중입니다." : run.steps.length ? "결론이 아직 기록되지 않았습니다. 단계별 결과를 확인하세요." : "아직 실행된 분석 단계가 없습니다.")}</p>
      {warnings.length > 0 && <ValidationList items={warnings} />}</section>
    <RunGraph run={run} titles={byRef} selected={current} onSelect={setOpen} draftSelection={draftMode ? draftSteps : undefined}
      onToggleDraft={draftMode ? (index) => setDraftSteps((steps) => steps.includes(index) ? steps.filter((item) => item !== index) : [...steps, index].sort((a, b) => a - b)) : undefined} />
    {selectedStep ? <section className={styles.runStepDetail} aria-live="polite"><span>{current + 1}단계 · {methodName(selectedStep.step.method)}</span><h2>{stepPurpose(selectedStep.step)}</h2><strong>{stepFinding(selectedStep)}</strong>
      <RunResultChart artifact={selectedStep.result.primary} />
      <details className={styles.runEvidence}><summary>표와 실행 근거 보기</summary><ResultView result={selectedStep.result} titles={byRef} showRunLink={false} />
        {visibleParams.length > 0 && <details className={styles.appliedParameters}><summary>적용된 설정</summary><dl>{visibleParams.map(([name, value]) => <div className={styles.appliedParameter} key={name}><dt>{parameterLabels[name] || name.replaceAll("_", " ")}</dt><dd>{parameterValue(value)}</dd><small>{selectedStep.parameter_sources?.[name] ? sourceLabels[selectedStep.parameter_sources[name]] : "출처 기록 없음"}</small></div>)}</dl></details>}
      </details>
    </section> : <div className={styles.placeholder}><History size={20} />아직 실행된 분석 단계가 없습니다.</div>}
    {!run.preview && !recipe && successfulSteps.length > 0 && <section className={styles.runRecipeDecision}><div><h2>이 분석을 반복해서 쓸까요?</h2><p>필요한 단계만 골라 Recipe 초안으로 검토할 수 있습니다. 등록하지 않으면 이 실행 기록으로만 남습니다.</p></div>
      {!draftMode ? <button type="button" className={styles.secondaryLink} onClick={() => { setDraftSteps(successfulSteps); setDraftMode(true); }}><Plus size={15} />Recipe 초안 검토</button>
        : <div className={styles.runDraftActions}><span>그래프에서 포함할 단계를 선택하세요.</span>
          {draftSteps.length > 0 && <Link className={styles.secondaryLink} href={`/recipes/new?${candidateParams.toString()}`}>선택한 {draftSteps.length}단계 검토</Link>}
          <button type="button" className={styles.secondaryLink} onClick={() => setDraftMode(false)}>취소</button></div>}
    </section>}
    {recipe && !run.preview && !run.running && <Link className={styles.secondaryLink} href={`/recipes/${encodeURIComponent(recipe.name)}`}>{stopped || run.status === "failed" ? "Recipe 조건을 바꿔 다시 실행" : "Recipe 보기"}</Link>}
    <details className={styles.runTechnical}><summary>분석 범위와 실행 정보</summary><dl><div><dt>분석 기간</dt><dd>{scope.date_range?.join(" ~ ") || "전체 기간"}</dd></div><div><dt>날짜 기준</dt><dd>{timeTitle || "지정 안 함"}</dd></div><div><dt>사용한 방법</dt><dd>{methods.join(" → ") || "실행 전"}</dd></div><div><dt>시작</dt><dd>{new Date(run.created_at).toLocaleString()}</dd></div></dl></details>
    {canContinue && manifests && <details className={styles.runTechnical}><summary>분석 이어가기</summary><section className={styles.formPanel}><NextStep run={run} manifests={manifests} objects={objects} onDone={() => { setOpen(null); reload(); }} /></section></details>}
    {canShare && <details className={styles.runShare}><summary>공유 설정</summary><Share run={run} onDone={reload} /></details>}
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
