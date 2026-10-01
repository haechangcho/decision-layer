"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CircleCheck, History } from "lucide-react";

import { clean, MethodInputs } from "@/components/forms";
import { ResultView, ValidationList } from "@/components/result";
import { api, MethodManifest, Result, Run } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import styles from "../../library.module.css";

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const { data: run, error, reload } = useApi<Run>(`/runs/${id}`);
  const { data: manifests } = useApi<MethodManifest[]>("/methods");
  const { objects, byRef } = useCatalog();
  const { data: me } = useApi<{ subject: string }>("/me");
  const [open, setOpen] = useState<number | null>(null);
  const t = useT();
  const mine = !!me && me.subject === run?.caller.subject;
  useEffect(() => {                                   // a background job is running: refresh until it ends
    if (!run?.running) return;
    const t = setTimeout(reload, 2000);
    return () => clearTimeout(t);
  }, [run, reload]);

  if (error) return <div className={styles.page}><p className={styles.error} role="alert">{error.message}</p><Link className={styles.back} href="/runs"><ArrowLeft size={15} />실행 기록</Link></div>;
  if (!run) return <div className={styles.page}><div className={styles.skeleton} /></div>;
  const recipe = run.recipe_snapshot;
  const queries = run.steps.reduce((n, s) => n + s.result.provenance.queries.length, 0);
  const current = open ?? run.steps.length - 1;

  const scope = run.plan.scope;
  const timeTitle = scope.time_dimension ? byRef.get(scope.time_dimension)?.title ?? scope.time_dimension : null;
  return <div className={styles.page}>
    <Link className={styles.back} href="/runs"><ArrowLeft size={15} />실행 기록</Link>
    <div className={styles.heading}><div><p className={styles.eyebrow}>RUN · {run.id.slice(-10)}</p><h1>{run.plan.question || recipe?.name || "분석 실행"}</h1><p className={styles.intro}>{recipe?.name ?? run.steps[0]?.step.method ?? "단일 분석"}</p></div><span className={`${styles.badge} ${run.status === "failed" ? styles.badgeFailed : run.status === "open" ? styles.badgeOpen : ""}`}>{run.status === "completed" ? "완료" : run.status === "failed" ? "실패" : "진행 중"}</span></div>
    <dl className={styles.runMeta}>
      <div><dt>시작</dt><dd>{new Date(run.created_at).toLocaleString()}</dd></div><div><dt>분석 단계</dt><dd>{run.steps.length}{recipe ? ` / ${recipe.limits.max_steps}` : ""}</dd></div><div><dt>조회 횟수</dt><dd>{queries}{recipe ? ` / ${recipe.limits.max_queries}` : ""}</dd></div><div><dt>기간</dt><dd>{scope.date_range?.join(" ~ ") || "전체 기간"}</dd></div>
    </dl>
    {run.running && <p className={styles.runNotice} role="status">분석 중 · {run.running.method ?? run.running.kind} · {new Date(run.running.started_at).toLocaleTimeString()} 시작</p>}
    {run.error && <p className={styles.error} role="alert">{run.error.message} · 오류 코드 {run.error.code}</p>}
    <div className={styles.runGrid}>
      <div className={styles.runLeft}>
        <section className={styles.formPanel}>
          <h2 className={styles.panelTitle}>실행 정보</h2>
          {run.summary && <><h3 className={styles.sectionTitle}>결론</h3><p className={styles.description}>{run.summary}</p></>}
          {timeTitle && <dl className={styles.meta}><div className={styles.metaRow}><dt>날짜 기준</dt><dd>{timeTitle}</dd></div></dl>}
          <ValidationList items={run.validation} />
          <h3 className={styles.sectionTitle}>공유</h3>{mine ? <Share run={run} onDone={reload} /> : <p className={styles.description}>{t("Read-only (owner {owner})", { owner: run.caller.subject ?? "—" })}</p>}
        </section>
        <section className={styles.formPanel}>
          <h2 className={styles.panelTitle}>분석 단계</h2>
          {run.steps.length ? <ol className={styles.stepList}>{run.steps.map((step, index) => <li key={index}><button className={`${styles.stepButton} ${index === current ? styles.active : ""}`} aria-pressed={index === current} onClick={() => setOpen(index)}><span className={styles.stepNumber}>{index + 1}</span><span className={styles.stepName}>{step.step.method}</span><span className={styles.badge}>{step.result.status === "success" ? "완료" : step.result.status === "failed" ? "실패" : step.result.status === "refused" ? "중단" : "입력 필요"}</span></button></li>)}</ol> : <p className={styles.description}>아직 완료된 분석 단계가 없습니다.</p>}
          {mine && run.status === "open" && !run.running && manifests && <NextStep run={run} manifests={manifests} objects={objects} onDone={() => { setOpen(null); reload(); }} />}
        </section>
      </div>
      <section className={styles.resultPanel} aria-live="polite"><h2 className={styles.panelTitle}>{run.steps[current] ? run.steps[current].step.method : "결과"}</h2>{run.steps[current] ? <ResultView result={run.steps[current].result} titles={byRef} /> : <div className={styles.placeholder}><History size={20} />실행된 단계의 결과와 근거가 여기에 표시됩니다.</div>}</section>
    </div>
  </div>;
}

function Share({ run, onDone }: { run: Run; onDone: () => void }) {
  const [text, setText] = useState(run.shared_with.join(", "));
  const t = useT();
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
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t("User identifiers, comma separated (* = everyone)")} />
      <button type="submit" className="ghost">{t("Save")}</button>
      <span className="hint">{t("It won't open for recipients who lack access to its metrics")}</span>
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
          {allowed.map((m) => <option key={m}>{m}</option>)}
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
