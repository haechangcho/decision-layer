"use client";

import { useMemo, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Background, Controls, ReactFlow, applyNodeChanges, type Edge, type Node } from "@xyflow/react";
import { ArrowLeft, ArrowRight, ArrowDown, ArrowUp, Check, Code2, Play, Plus, Save, Search, Trash2, Undo2, X } from "lucide-react";
import "@xyflow/react/dist/style.css";
import { api, type MethodManifest, type PlanStep, type Recipe, type RecipeCandidate, type Run, type SourceReadiness } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import { methodName } from "@/lib/method-name";
import { ResultView, ValidationList } from "@/components/result";
import { recipeChanges } from "@/lib/recipe-changes";
import { RecipeDelete } from "./recipe-delete";
import { sourceLabel } from "@/features/recipes/step-input-source";
import { RecipeRuntimeInputs } from "./recipe-runtime-inputs";
import { RunPeriodInput } from "@/features/runs/run-period-input";
import { suggestedDateRange, suggestedTimeDimension } from "@/lib/semantic-dates";
import s from "@/components/analysis-canvas.module.css";

import { blank, bump, refs, newName, previewDates, explainError, validationField, roleLabels, type FieldError } from "./editor-model";
import { nodeTypes, FitRecipe } from "./recipe-nodes";
import { RefField } from "./recipe-fields";
import { StepSettings } from "./step-settings";

export function RecipeEditor({ initial }: { initial?: Recipe }) {
  const router = useRouter();
  const { objects, byRef, error: catalogError } = useCatalog();
  const { data: allMethods, error: methodsError } = useApi<MethodManifest[]>("/methods");
  const methods = useMemo(() => allMethods?.filter(method => method.implementation !== "skill" || method.agent_executable), [allMethods]);
  const { data: readiness } = useApi<SourceReadiness>("/sources/current/readiness");
  const [recipe, setRecipe] = useState<Recipe>(() => initial || blank());
  const [saved, setSaved] = useState<Recipe | undefined>(initial);
  const [selected, setSelected] = useState(-1);
  const [positions, setPositions] = useState<Node[]>([]);
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reviewNotes, setReviewNotes] = useState<string[]>([]);
  const [previewInputs, setPreviewInputs] = useState<Record<string, unknown>>({});
  const [fieldError, setFieldError] = useState<FieldError | null>(null);
  const [dialog, setDialog] = useState(false);
  const [publishDialog, setPublishDialog] = useState(false);
  const [yamlOpen, setYamlOpen] = useState(false);
  const [yamlText, setYamlText] = useState("");
  const [yamlBase, setYamlBase] = useState("");
  const [yamlDirty, setYamlDirty] = useState(false);
  const [yamlBusy, setYamlBusy] = useState(false);
  const [yamlError, setYamlError] = useState("");
  const [previewRange, setPreviewRange] = useState<[string, string]>(() => initial?.default_scope?.date_range ?? previewDates());
  const previewDatesTouched = useRef(false);
  function choosePreviewDates(value: [string, string]) { previewDatesTouched.current = true; setPreviewRange(value); }
  const [previewTimeDimension, setPreviewTimeDimension] = useState(initial?.default_scope?.time_dimension ?? "");
  const [previewLimited, setPreviewLimited] = useState(!!initial?.default_scope?.date_range);
  const [previewRun, setPreviewRun] = useState<Run | null>(null);
  const [previewIndex, setPreviewIndex] = useState(-1);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewFormOpen, setPreviewFormOpen] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [previewElapsed, setPreviewElapsed] = useState(0);
  const metricSelect = useRef<HTMLSelectElement>(null);
  const previewOutput = useRef<HTMLElement>(null);
  const inspector = useRef<HTMLElement>(null);
  const initializedFromLink = useRef(false);
  const latestRecipe = useRef(recipe);
  latestRecipe.current = recipe;
  const dirty = !saved || JSON.stringify(recipe) !== JSON.stringify(saved);
  const pipeline = recipe.mode === "pipeline";
  const steps: PlanStep[] = pipeline ? recipe.steps : recipe.allowed_methods.map(method => ({ method, bindings: {}, params: {} }));
  const active = steps[selected];
  const title = (ref: string) => byRef.get(ref)?.title || "이름 확인 필요";
  const preparedTime = readiness?.metrics.find(item => item.metric.ref === recipe.semantic_scope.primary_metric)?.checks.time.dimensions;
  const metricEntity = byRef.get(recipe.semantic_scope.primary_metric)?.entity;
  const allTimes = objects.filter(object => object.kind === "time_dimension");
  const relatedTimes = preparedTime?.length ? allTimes.filter(object => preparedTime.includes(object.ref))
    : allTimes.filter(object => !!metricEntity && object.entity === metricEntity);
  const timeOptions = relatedTimes.length ? relatedTimes : allTimes;
  const selectedTime = timeOptions.some(object => object.ref === previewTimeDimension) ? previewTimeDimension
    : timeOptions.length === 1 ? timeOptions[0].ref : suggestedTimeDimension(objects, recipe.semantic_scope.primary_metric)?.ref ?? "";
  const recommendedPeriod = suggestedDateRange(byRef.get(selectedTime));
  const recommendedPeriodKey = recommendedPeriod?.join("/");
  useEffect(() => {
    if (recipe.default_scope != null || previewDatesTouched.current || !recommendedPeriod) return;
    setPreviewRange(recommendedPeriod);
  }, [selectedTime, recommendedPeriodKey]);
  const previewRequiresPeriod = pipeline && selected >= 0 && steps.slice(0, selected + 1).some(step => {
    const manifest = methods?.find(method => method.name === step.method);
    return manifest?.requires_period || Object.entries(manifest?.parameters ?? {}).some(([name, spec]) => spec.meaning === "period" && spec.type === "boolean" && (recipe.method_parameters?.[step.method]?.fixed[name] ?? step.params[name] ?? spec.default) === true);
  });
  const previewPeriodRule = !previewDatesTouched.current && recipe.default_scope?.period?.mode === "relative";
  const previewWithPeriod = !previewPeriodRule && (previewLimited || previewRequiresPeriod);
  const previewDatesInvalid = previewWithPeriod && (!previewRange[0] || !previewRange[1] || previewRange[0] > previewRange[1]);
  const latestManifest = methods?.find(method => method.name === active?.method);
  const needsPinnedManifest = !!active && (!latestManifest || !!active.method_version && latestManifest.version !== active.method_version);
  const { data: pinnedManifest, error: pinnedError } = useApi<MethodManifest>(needsPinnedManifest ? `/methods/${encodeURIComponent(active.method)}${active.method_version ? `?version=${encodeURIComponent(active.method_version)}` : ""}` : null);
  const activeManifest = needsPinnedManifest ? pinnedManifest : latestManifest;
  useEffect(() => { setPreviewFormOpen(false); }, [selected]);
  const displayMethod = (name: string) => methods?.find(method => method.name === name)?.label || methodName(name);
  const missingRoles = activeManifest ? Object.entries(activeManifest.roles).filter(([name, role]) => {
    if (role.exclusive_group) {
      const alternatives = Object.entries(activeManifest.roles).filter(([, item]) => item.exclusive_group === role.exclusive_group);
      return alternatives[0][0] === name && alternatives.filter(([key]) => active.bindings[key]).length !== 1;
    }
    return role.required && (!active.bindings[name] || Array.isArray(active.bindings[name]) && !(active.bindings[name] as unknown[]).length);
  }) : [];
  const stoppedPreviewStep = previewRun && !previewRun.running && previewRun.steps.length < previewIndex + 1
    ? previewRun.steps.at(-1)?.result.status !== "success" && previewRun.steps.length ? previewRun.steps.length - 1
      : previewRun.error && previewRun.steps.length ? previewRun.steps.length : null
    : null;
  useEffect(() => {
    if (initial || initializedFromLink.current) return;
    const params = new URLSearchParams(window.location.search);
    const sourceRun = params.get("from_run");
    if (sourceRun) {
      initializedFromLink.current = true;
      const indices = params.getAll("step");
      const query = new URLSearchParams();
      for (const index of indices) query.append("indices", index);
      void api<RecipeCandidate>(`/runs/${encodeURIComponent(sourceRun)}/recipe-candidate?${query}`).then(candidate => {
        setRecipe(candidate.recipe);
        setReviewNotes(candidate.review_notes);
        if (candidate.recipe.default_scope?.date_range) { setPreviewRange(candidate.recipe.default_scope.date_range); setPreviewLimited(true); }
        setPreviewTimeDimension(candidate.recipe.default_scope?.time_dimension ?? "");
      }).catch(cause => setError(explainError(cause)));
      return;
    }
    const method = params.get("method");
    if (method && !methods) return;
    initializedFromLink.current = true;
    const manifest = methods?.find(item => item.name === method);
    if (method && !manifest) { setError("선택한 분석 방법을 사용할 수 없습니다. 분석 방법 목록에서 다시 선택하세요."); return; }
    setRecipe(current => {
      const metric = current.semantic_scope.primary_metric || params.get("metric") || "";
      return {
        ...current,
        name: current.name || (metric ? newName(metric) : ""),
        semantic_scope: { ...current.semantic_scope, primary_metric: metric },
        steps: method && manifest ? [{ id: "step_1", method, method_version: manifest.version, bindings: manifest.roles.metric ? { metric: "$scope.primary_metric" } : {}, params: {} }] : [],
      };
    });
  }, [initial, methods]);
  useEffect(() => { if (!dirty) return; const warn = (e: BeforeUnloadEvent) => e.preventDefault(); window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, [dirty]);
  useEffect(() => {
    if (!previewRun?.running) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const next = await api<Run>(`/runs/${previewRun.id}`);
        if (!cancelled) { setPreviewRun(next); setPreviewElapsed(Math.round((Date.now() - new Date(next.created_at).getTime()) / 1000)); }
      } catch (cause) {
        if (!cancelled) setPreviewError(explainError(cause));
      }
    }, 1500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [previewRun?.id, !!previewRun?.running]);
  useEffect(() => {
    if (previewRun?.id) previewOutput.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [previewRun?.id]);
  useEffect(() => {
    if (!fieldError) return;
    const input = fieldError.field.match(/^steps\[\d+\]\.params\.(.+)$/)?.[1];
    const role = Object.entries(activeManifest?.roles ?? {}).find(([, role]) => input && role.editor_parameter === input)?.[0];
    const fieldPath = role ? `steps[${selected}].bindings.${role}` : fieldError.field;
    if ((!fieldError.field.startsWith("steps[") && fieldError.field !== "semantic_scope.primary_metric") || input && !role && activeManifest?.parameters[input]?.ui_group !== "basic") setYamlOpen(true);
    const timer = window.setTimeout(() => {
      const field = [...document.querySelectorAll<HTMLElement>("[data-recipe-field]")].find(element => element.dataset.recipeField === fieldPath);
      const control = field?.querySelector<HTMLElement>("input, select, textarea") ?? document.querySelector<HTMLElement>('[aria-label="Recipe YAML"]');
      if (control) { control.scrollIntoView({ block: "center" }); control.focus(); }
      else inspector.current?.scrollTo({ top: 0, behavior: "smooth" });
    }, 50);
    return () => window.clearTimeout(timer);
  }, [fieldError]);
  useEffect(() => {
    if (!yamlOpen || yamlDirty || !steps.length) return;
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const result = await api<{ yaml: string }>("/recipes:format", { body: recipe });
        if (!cancelled) { setYamlText(result.yaml); setYamlBase(JSON.stringify(recipe)); setYamlError(""); }
      } catch (cause) { if (!cancelled) setYamlError(explainError(cause)); }
    }, 200);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [yamlOpen, yamlDirty, recipe, steps.length]);
  function change(next: Recipe) { setRecipe(next); setError(""); setFieldError(null); setPreviewRun(null); setPreviewError(""); }
  async function applyYaml() {
    if (yamlBase !== JSON.stringify(recipe)) { setYamlError("그래프가 변경되었습니다. YAML을 새로고침한 뒤 다시 편집해 주세요."); return; }
    setYamlBusy(true); setYamlError("");
    try {
      const parsed = await api<Recipe>("/recipes:parse", { body: { yaml: yamlText } });
      if (saved && parsed.name !== saved.name) { setYamlError("저장된 Recipe의 ID는 변경할 수 없습니다."); return; }
      change(parsed); setYamlDirty(false);
    } catch (cause) { setYamlError(explainError(cause)); }
    finally { setYamlBusy(false); }
  }
  async function startPreview() {
    if (selected < 0 || !pipeline) return;
    setPreviewBusy(true); setPreviewError(""); setPreviewRun(null); setPreviewIndex(selected); setPreviewElapsed(0);
    try {
      const run = await api<Run>("/recipes:preview", { body: {
        recipe, step_index: selected,
        scope: { ...(previewPeriodRule ? { period: recipe.default_scope?.period } : { date_range: previewWithPeriod && selectedTime && !previewDatesInvalid ? previewRange : null }), time_dimension: selectedTime || null, inputs: previewInputs },
      } });
      setPreviewRun(run);
    } catch (cause) { setPreviewError(explainError(cause)); }
    finally { setPreviewBusy(false); }
  }
  async function configure(next: Recipe, stepIndex: number, reset: string[] = []) {
    if (busy) return;
    const base = recipe;
    setBusy(true); setError("");
    try {
      const configured = await api<Recipe>("/recipes:configure-step", { body: { recipe: next, step_index: stepIndex, reset_parameters: reset } });
      if (latestRecipe.current !== base) { setError("설정이 변경되었습니다. 자동 연결을 다시 실행해 주세요."); return; }
      change(configured);
    }
    catch (cause) { setError(explainError(cause)); }
    finally { setBusy(false); }
  }
  async function add(method: string) {
    if (pipeline) {
      let id = 1; while (recipe.steps.some(step => step.id === `step_${id}`)) id++;
      await configure({ ...recipe, steps: [...recipe.steps, { id: `step_${id}`, method, bindings: {}, params: {} }] }, recipe.steps.length);
    } else change({ ...recipe, allowed_methods: [...recipe.allowed_methods, method] });
    setSelected(steps.length); setAdding(false); setPositions([]);
  }
  function updateSteps(next: PlanStep[]) {
    const seen = new Set<string>();
    for (const step of next) {
      const expressions = JSON.stringify(step).match(/\$steps\.([^."\\]+)\./g) || [];
      const sources = Object.values(step.params).filter(value => value && typeof value === "object" && !Array.isArray(value) && (value as Record<string, unknown>).source === "step") as { step_id: string }[];
      if (expressions.some(expression => !seen.has(expression.split(".")[1])) || sources.some(source => !seen.has(source.step_id))) { setError("이전 결과를 사용하는 단계가 있습니다. 참조를 변경한 뒤 순서를 바꾸거나 삭제해 주세요."); return false; }
      if (step.id) seen.add(step.id);
    }
    change({ ...recipe, steps: next }); setPositions([]); return true;
  }
  function stepDetail(step: PlanStep): string {
    const dimensions = step.bindings.dimensions;
    const source = sourceLabel(step.params.drill_path ?? step.params.subject, recipe.steps);
    if (source) return source;
    if (dimensions) return refs(dimensions).map(ref => ref.startsWith("$") ? "공통 분류 기준" : title(ref)).join(" → ");
    const granularity = step.params.granularity ?? methods?.find(method => method.name === step.method)?.parameters.granularity?.default;
    if (typeof granularity === "string") {
      const period: Record<string, string> = { day: "일별", week: "주별", month: "월별", quarter: "분기별" };
      return `${period[granularity] || granularity} 추이${step.params.vs_previous ? " · 직전 기간 비교" : ""}`;
    }
    return "";
  }
  const nodes: Node[] = [
    { id: "scope", type: "recipe", position: { x: 200, y: 20 }, data: { scope: true, kind: "분석 대상", label: recipe.semantic_scope.primary_metric ? title(recipe.semantic_scope.primary_metric) : "지표 선택", detail: recipe.description || "분석 목적 입력" } },
    ...steps.map((step, i) => ({ id: `step:${i}`, type: "recipe", position: { x: pipeline ? 200 : 40 + (i % 2) * 300, y: pipeline ? 200 + i * 180 : 220 + Math.floor(i / 2) * 180 }, data: { kind: pipeline ? `STEP ${i + 1} · ${step.id || ""}` : "사용 가능한 방법", label: displayMethod(step.method), detail: pipeline ? stepDetail(step) : step.method } })),
  ].map(n => ({ ...n, ...positions.find(p => p.id === n.id), data: n.data, selected: n.id === (selected < 0 ? "scope" : `step:${selected}`) }));
  const edges: Edge[] = steps.map((step, i) => {
    const fromPrevious = i > 0 && Object.values(step.params).some(value => value && typeof value === "object" && !Array.isArray(value) && (value as Record<string, unknown>).source === "step" && (value as Record<string, unknown>).step_id === steps[i - 1].id);
    return { id: `edge:${i}`, source: pipeline && i > 0 ? `step:${i - 1}` : "scope", target: `step:${i}`,
      label: pipeline ? fromPrevious ? "이전 결과에서 선택" : "다음 단계" : "허용", style: { stroke: "var(--dl-border-strong)", strokeWidth: 2 } };
  });
  if (pipeline) steps.forEach((step, i) => {
    const sourceIds = new Set(Object.values(step.params).flatMap(value => value && typeof value === "object" && !Array.isArray(value) && (value as Record<string, unknown>).source === "step" ? [String((value as Record<string, unknown>).step_id)] : []));
    sourceIds.forEach(id => {
      const from = steps.findIndex(item => item.id === id);
      if (from < 0 || from === i - 1) return;
      edges.push({ id: `selection:${from}:${i}`, source: `step:${from}`, target: `step:${i}`, sourceHandle: "selection-out", targetHandle: "selection-in", type: "smoothstep", label: `${from + 1}단계 결과 사용`, style: { stroke: "var(--accent)", strokeDasharray: "4 4" } });
    });
  });
  const nextVersion = saved ? bump(saved.version) : recipe.version;
  function writeError(cause: unknown) {
    const field = validationField(cause);
    if (field) {
      setFieldError(field); setDialog(false); setPublishDialog(false); setAdding(false);
      const match = /^steps\[(\d+)\]/.exec(field.field);
      setSelected(match ? Number(match[1]) : -1);
    } else setError(explainError(cause));
  }
  async function save() {
    setBusy(true); setError(""); setFieldError(null);
    try {
      const candidate = { ...recipe, version: nextVersion, status: "draft" as const };
      await api<{ valid: boolean; semantic_checked: boolean }>("/recipes:validate?live=true", { body: candidate });
      const value = await api<Recipe>(`/recipes/${encodeURIComponent(recipe.name)}`, { method: "PUT", body: { recipe: candidate, base_version: saved?.version || null } });
      setDialog(false);
      if (!initial) {
        router.replace(`/recipes/${encodeURIComponent(value.name)}/edit`);
      } else { setRecipe(value); setSaved(value); }
    } catch (e) { writeError(e); } finally { setBusy(false); }
  }
  async function publish() {
    if (!saved || saved.status !== "draft" || dirty) return;
    setBusy(true); setError(""); setFieldError(null);
    try {
      const value = await api<Recipe>(`/recipes/${encodeURIComponent(saved.name)}/publish`, { body: { base_version: saved.version } });
      setRecipe(value); setSaved(value); setPublishDialog(false);
      router.push(`/recipes/${encodeURIComponent(value.name)}`);
    } catch (e) { writeError(e); } finally { setBusy(false); }
  }
  return <div className={s.page}>
    <header className={s.header}><div><Link className={s.back} href="/recipes"><ArrowLeft size={14} />레시피</Link><h1>{saved ? "분석 절차 편집" : "새 분석 절차"}</h1><span className={s.nodeStatus}>{dirty ? "저장되지 않은 변경" : `v${saved?.version} · ${saved?.status === "draft" ? "초안" : "발행됨"}`}</span></div><div className={s.actions}>
      <button type="button" className={s.secondary} aria-pressed={yamlOpen} onClick={() => setYamlOpen(!yamlOpen)}><Code2 size={16} />{yamlOpen ? "코드 닫기" : "코드 보기"}</button>
      {dirty && saved && <button className={s.secondary} title="저장된 버전으로 되돌리기" onClick={() => { setRecipe(saved); setSelected(-1); setPositions([]); setFieldError(null); }}><Undo2 size={16} />되돌리기</button>}
      {dirty && steps.length > 0 && <button disabled={busy || !recipe.semantic_scope.primary_metric} onClick={() => { setError(""); setDialog(true); }}><Save size={16} />초안 저장</button>}
      {!dirty && saved?.status === "draft" && <button disabled={busy} onClick={() => { setError(""); setPublishDialog(true); }}><Check size={16} />발행 검토</button>}
      {!dirty && saved?.status !== "draft" && saved && <button disabled={busy} onClick={() => router.push(`/recipes/${encodeURIComponent(recipe.name)}`)}><Play size={16} />분석 실행</button>}
      {saved && !busy && <RecipeDelete recipe={saved} onDeleted={() => { setSaved(undefined); setRecipe(blank()); router.push("/recipes"); }} />}
    </div></header>
    {(catalogError || methodsError) && <p className={s.error} role="alert">{catalogError?.message || methodsError?.message} <Link href="/sources">연결 확인</Link></p>}
    {error && !dialog && <p className={s.error} role="alert">{error}</p>}
    {!!recipe.origin_runs?.length && <div className={s.reviewNotice}><strong>실행 기록에서 가져온 분석 절차</strong><Link href={`/runs/${recipe.origin_runs[0]}`}>원본 실행 보기 <ArrowRight size={14} /></Link><p>{recipe.steps.length}단계 · 기간은 실행할 때 선택</p>{!!reviewNotes.length && <p>직접 지정된 그룹과 기간을 확인하세요. 매번 데이터를 기준으로 선택하려면 단계 설정에서 이전 결과를 지정하세요.</p>}</div>}
    {fieldError && <p className={s.error} role="alert">저장 전 확인이 필요합니다: {fieldError.message}</p>}
    <div className={s.toolbar}><span className={s.recipeMode}>{pipeline ? `분석 절차 · ${steps.length}단계` : `탐색에 사용할 분석 · ${steps.length}개`}</span>{steps.length > 0 && <button disabled={!recipe.semantic_scope.primary_metric} onClick={() => { setAdding(true); setSearch(""); }}><Plus size={16} />{pipeline ? "분석 단계 추가" : "허용할 방법 추가"}</button>}</div>
    <div className={s.workspace}>
      <section className={s.canvas} aria-label="Recipe 그래프"><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={changes => setPositions(applyNodeChanges(changes, nodes))} onNodeClick={(_, node) => { setSelected(node.id === "scope" ? -1 : Number(node.id.split(":")[1])); setAdding(false); }} nodesConnectable={false} deleteKeyCode={null} fitView minZoom={.25} maxZoom={1.1}><FitRecipe count={steps.length} /><Background color="var(--dl-border-strong)" gap={20} /><Controls showInteractive={false} /></ReactFlow>
        {!steps.length && <div className={s.canvasEmpty}>{recipe.semantic_scope.primary_metric ? <button onClick={() => setAdding(true)}><Plus size={16} />첫 분석 추가</button> : <button onClick={() => metricSelect.current?.focus()}>지표 선택 <ArrowRight size={16} /></button>}</div>}
      </section>
      <aside ref={inspector} className={s.inspector}>
        {adding ? <><h2>분석 방법 선택</h2><label className={s.search}><Search size={16} /><input aria-label="분석 방법 검색" value={search} placeholder="추이, 항목별, 조건 맞춤" onChange={e => setSearch(e.target.value)} /></label><div className={s.choices}>{(methods || []).filter(m => (pipeline || !recipe.allowed_methods.includes(m.name)) && `${displayMethod(m.name)} ${m.name} ${m.description}`.toLowerCase().includes(search.toLowerCase())).map(m => <button key={m.name} onClick={() => add(m.name)}><span>{displayMethod(m.name)}</span><Plus size={16} /><small>{m.description}</small></button>)}</div><button className={s.secondary} onClick={() => setAdding(false)}>취소</button></> : !active ? <div className={s.fields}>
          <h2>분석 절차 정보</h2><label>어떤 질문에 사용하는 분석인가요?<textarea rows={2} value={recipe.routing.objective || recipe.description} placeholder="예: 지표의 변화를 확인하고 영향이 큰 항목 찾기" onChange={e => change({ ...recipe, description: e.target.value, routing: { ...recipe.routing, objective: e.target.value } })} /></label>
          <RefField label="분석할 지표" selectRef={metricSelect} value={recipe.semantic_scope.primary_metric} objects={objects.filter(o => o.kind === "measure")} fieldPath="semantic_scope.primary_metric" error={fieldError?.field === "semantic_scope.primary_metric" ? fieldError.message : undefined} onChange={v => change({ ...recipe, name: recipe.name || newName(String(v)), semantic_scope: { ...recipe.semantic_scope, primary_metric: String(v) } })} />
        </div> : <div className={s.fields}>
          <button type="button" className={s.inspectorBack} onClick={() => { setSelected(-1); setAdding(false); }}><ArrowLeft size={14} />분석 절차 정보</button>
          <div className={s.inspectorHeading}><span className={s.eyebrow}>{pipeline ? `STEP ${selected + 1}` : "ALLOWED METHOD"}</span><div className={s.actions}>
            {pipeline && <><button className={s.icon} disabled={selected === 0} title="이전 순서로" aria-label="이전 순서로" onClick={() => { const next = [...recipe.steps]; [next[selected - 1], next[selected]] = [next[selected], next[selected - 1]]; if (updateSteps(next)) setSelected(selected - 1); }}><ArrowUp size={16} /></button><button className={s.icon} disabled={selected === steps.length - 1} title="다음 순서로" aria-label="다음 순서로" onClick={() => { const next = [...recipe.steps]; [next[selected + 1], next[selected]] = [next[selected], next[selected + 1]]; if (updateSteps(next)) setSelected(selected + 1); }}><ArrowDown size={16} /></button></>}
            <button className={s.icon} title="단계 삭제" aria-label="단계 삭제" onClick={() => pipeline ? updateSteps(recipe.steps.filter((_, i) => i !== selected)) : change({ ...recipe, allowed_methods: recipe.allowed_methods.filter((_, i) => i !== selected) })}><Trash2 size={16} /></button>
          </div></div>
          <h2>{displayMethod(active.method)}</h2>
          {active.method_version && <p className={s.dependency}>이 단계의 고정 버전 · v{active.method_version}</p>}
          {pinnedError && <p className={s.error} role="alert">{pinnedError.message}</p>}
          {pipeline && active.method_version && latestManifest && active.method_version !== latestManifest.version && <button type="button" className={s.secondary} disabled={busy} onClick={() => configure({ ...recipe, steps:recipe.steps.map((step,index) => index===selected ? { ...step, method_version:latestManifest.version, bindings:{}, params:{} } : step) },selected)}>v{latestManifest.version} 적용 · 입력 설정 다시 선택</button>}
          {pipeline && activeManifest ? <StepSettings key={`${selected}-${active.method}-${active.method_version || "latest"}`} step={active} manifest={activeManifest} methods={methods ?? []} objects={objects} recipe={recipe} stepIndex={selected} fieldError={fieldError} onChange={step => change({ ...recipe, steps: recipe.steps.map((s, i) => i === selected ? step : s) })} /> : !pipeline ? <p className={s.dependency}>MCP에서 이 Recipe를 선택하면 실행 결과에 따라 다음 분석과 입력을 정합니다.</p> : <p role="status">분석 설정을 불러오는 중…</p>}
          {pipeline && <section className={s.previewSection} aria-label="결과 확인">
            {previewFormOpen && <>
              <RecipeRuntimeInputs specs={recipe.inputs ?? {}} values={previewInputs} onChange={setPreviewInputs} objects={objects} />
              {previewWithPeriod && (timeOptions.length > 1 || !selectedTime) && <label>날짜 기준<select aria-label="미리보기 날짜 기준" value={selectedTime} onChange={event => setPreviewTimeDimension(event.target.value)}><option value="">선택하세요</option>{timeOptions.map(object => <option value={object.ref} key={object.ref}>{object.title}</option>)}</select></label>}
              {previewWithPeriod && <div className={s.previewDates}><label>시작일<input type="date" aria-label="미리보기 시작일" value={previewRange[0]} onChange={event => choosePreviewDates([event.target.value, previewRange[1]])} /></label><label>종료일<input type="date" aria-label="미리보기 종료일" value={previewRange[1]} onChange={event => choosePreviewDates([previewRange[0], event.target.value])} /></label></div>}
              {previewDatesInvalid && <p className={s.error} role="alert">시작일과 종료일을 확인해 주세요.</p>}
              {previewWithPeriod && !selectedTime && <p className={s.nodeStatus}>날짜 기준을 선택해 주세요.</p>}
            </>}
            {missingRoles.length > 0 && <p className={s.nodeStatus}>{missingRoles.map(([name, role]) => role.label || roleLabels[name] || name).join(", ")}을 선택해 주세요.</p>}
            <button type="button" disabled={previewBusy || !activeManifest || missingRoles.length > 0 || !recipe.semantic_scope.primary_metric || previewFormOpen && (previewDatesInvalid || previewWithPeriod && !selectedTime)} onClick={() => { if (!previewFormOpen && (previewWithPeriod || Object.keys(recipe.inputs ?? {}).length)) setPreviewFormOpen(true); else void startPreview(); }}><Play size={15} />{previewBusy ? "확인 중…" : previewFormOpen ? "이 조건으로 확인" : "결과 확인"}</button>
            {previewError && <p className={s.error} role="alert">{previewError} <Link href="/sources">연결 확인</Link></p>}
          </section>}
        </div>}
      </aside>
    </div>
    {yamlOpen && <section className={s.previewOutput} aria-label="Recipe 코드"><h2>Recipe 코드</h2><div className={s.fields}>
            <label data-recipe-field="name">Recipe ID<input value={recipe.name} disabled={!!saved} onChange={event => change({ ...recipe, name: event.target.value })} /></label>
            <label>Recipe YAML<textarea aria-label="Recipe YAML" rows={18} spellCheck={false} value={yamlText} onChange={event => { setYamlText(event.target.value); setYamlDirty(true); setYamlError(""); }} /></label>
            {yamlDirty && <span className={s.nodeStatus}>YAML 변경 사항을 그래프에 적용해야 저장됩니다.</span>}
            {yamlError && <p className={s.error} role="alert">{yamlError}</p>}
            <div className={s.actions}><button type="button" disabled={!yamlDirty || yamlBusy} onClick={applyYaml}><Check size={14} />{yamlBusy ? "검증 중…" : "YAML 적용"}</button><button type="button" className={s.secondary} disabled={yamlBusy} onClick={() => { setYamlDirty(false); setYamlError(""); }}>그래프에서 다시 불러오기</button></div>
          </div></section>}
    {previewIndex === selected && previewRun && <section ref={previewOutput} className={s.previewOutput} aria-label="미리보기 결과" aria-live="polite">
      <div className={s.previewOutputHeading}><div><span className={s.eyebrow}>STEP {selected + 1}</span><h2>미리보기 결과</h2></div><Link href={`/runs/${previewRun.id}`}>실행 근거 보기 <ArrowRight size={14} /></Link></div>
      {previewRun.running && <p role="status">{previewRun.steps.length}/{selected + 1}단계 실행 중 · {previewElapsed}초</p>}
      {previewRun.needs_input && <RunPeriodInput key={`${previewRun.id}:${previewRun.scope_revision}`} run={previewRun} objects={objects} onDone={setPreviewRun} />}
      {previewRun.error && <p className={s.error} role="alert">{previewRun.error.message}</p>}
      {stoppedPreviewStep !== null && <div className={s.previewStopped}><span>{stoppedPreviewStep + 1}단계에서 미리보기가 멈췄습니다.</span><button type="button" className={s.secondary} onClick={() => { setSelected(stoppedPreviewStep); inspector.current?.scrollTo({ top: 0, behavior: "smooth" }); }}>{stoppedPreviewStep + 1}단계 설정 확인 <ArrowRight size={14} /></button></div>}
      {!previewRun.running && <><ValidationList items={previewRun.validation} />{previewRun.steps.at(-1) && <ResultView result={previewRun.steps.at(-1)!.result} titles={byRef} />}</>}
    </section>}
    {dialog && <div className={s.overlay}><section className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="recipe-dialog-title"><div className={s.inspectorHeading}><h2 id="recipe-dialog-title">초안 저장</h2><button className={s.icon} disabled={busy} aria-label="닫기" onClick={() => setDialog(false)}><X size={18} /></button></div>
      <p>{recipe.description || recipe.name} · v{nextVersion} · {steps.length}단계</p><h3>변경 내용</h3><ul className={s.changeList}>{recipeChanges(saved, recipe, title).map((item, index) => <li key={`${index}:${item}`}>{item}</li>)}</ul><button className={s.run} disabled={busy || !recipe.name || !recipe.semantic_scope.primary_metric || !steps.length} onClick={save}><Save size={16} />{busy ? "저장 중…" : "초안 버전 저장"}</button>
      {error && <p className={s.error} role="alert">{error}</p>}
    </section></div>}
    {publishDialog && <div className={s.overlay}><section className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="publish-dialog-title"><div className={s.inspectorHeading}><h2 id="publish-dialog-title">분석 절차 발행</h2><button className={s.icon} disabled={busy} aria-label="닫기" onClick={() => setPublishDialog(false)}><X size={18} /></button></div>
      <p>{recipe.description || recipe.name} · 초안 v{saved?.version} · {steps.length}단계</p><p>발행하면 새 버전이 레시피 목록과 MCP에 표시되고 실행할 수 있습니다. 현재 초안은 그대로 보관됩니다.</p>
      <ul className={s.changeList}><li>분석 지표 · {title(recipe.semantic_scope.primary_metric)}</li>{steps.map((step, index) => <li key={step.id || index}>{index + 1}단계 · {displayMethod(step.method)}</li>)}</ul>
      <button className={s.run} disabled={busy} onClick={publish}><Check size={16} />{busy ? "검증 중…" : "검증하고 발행"}</button>{error && <p className={s.error} role="alert">{error}</p>}
    </section></div>}
  </div>;
}
