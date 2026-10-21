"use client";
import { useT } from "@/lib/i18n";

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
  const t = useT();
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
  const title = (ref: string) => byRef.get(ref)?.title || t("Name needs checking");
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
  const displayMethod = (name: string) => methods?.find(method => method.name === name)?.label || methodName(name, t);
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
      }).catch(cause => setError(explainError(cause, t)));
      return;
    }
    const method = params.get("method");
    if (method && !methods) return;
    initializedFromLink.current = true;
    const manifest = methods?.find(item => item.name === method);
    if (method && !manifest) { setError(t("The selected Method is unavailable. Choose another from the Method list.")); return; }
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
        if (!cancelled) setPreviewError(explainError(cause, t));
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
      } catch (cause) { if (!cancelled) setYamlError(explainError(cause, t)); }
    }, 200);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [yamlOpen, yamlDirty, recipe, steps.length]);
  function change(next: Recipe) { setRecipe(next); setError(""); setFieldError(null); setPreviewRun(null); setPreviewError(""); }
  async function applyYaml() {
    if (yamlBase !== JSON.stringify(recipe)) { setYamlError(t("The graph changed. Reload the YAML and edit it again.")); return; }
    setYamlBusy(true); setYamlError("");
    try {
      const parsed = await api<Recipe>("/recipes:parse", { body: { yaml: yamlText } });
      if (saved && parsed.name !== saved.name) { setYamlError(t("A saved Recipe's ID cannot be changed.")); return; }
      change(parsed); setYamlDirty(false);
    } catch (cause) { setYamlError(explainError(cause, t)); }
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
    } catch (cause) { setPreviewError(explainError(cause, t)); }
    finally { setPreviewBusy(false); }
  }
  async function configure(next: Recipe, stepIndex: number, reset: string[] = []) {
    if (busy) return;
    const base = recipe;
    setBusy(true); setError("");
    try {
      const configured = await api<Recipe>("/recipes:configure-step", { body: { recipe: next, step_index: stepIndex, reset_parameters: reset } });
      if (latestRecipe.current !== base) { setError(t("The settings changed. Run the automatic linking again.")); return; }
      change(configured);
    }
    catch (cause) { setError(explainError(cause, t)); }
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
      if (expressions.some(expression => !seen.has(expression.split(".")[1])) || sources.some(source => !seen.has(source.step_id))) { setError(t("A step uses a previous result. Change the reference before reordering or deleting.")); return false; }
      if (step.id) seen.add(step.id);
    }
    change({ ...recipe, steps: next }); setPositions([]); return true;
  }
  function stepDetail(step: PlanStep): string {
    const dimensions = step.bindings.dimensions;
    const source = sourceLabel(step.params.drill_path ?? step.params.subject, t, recipe.steps);
    if (source) return source;
    if (dimensions) return refs(dimensions).map(ref => ref.startsWith("$") ? t("Shared breakdown dimensions") : title(ref)).join(" → ");
    const granularity = step.params.granularity ?? methods?.find(method => method.name === step.method)?.parameters.granularity?.default;
    if (typeof granularity === "string") {
      const period: Record<string, string> = { day: "Daily", week: "Weekly", month: "Monthly", quarter: "Quarterly" };
      return `${t("{unit} trend", { unit: period[granularity] ? t(period[granularity]) : granularity })}${step.params.vs_previous ? ` · ${t("Compare with previous period")}` : ""}`;
    }
    return "";
  }
  const nodes: Node[] = [
    { id: "scope", type: "recipe", position: { x: 200, y: 20 }, data: { scope: true, kind: t("Analysis subject"), label: recipe.semantic_scope.primary_metric ? title(recipe.semantic_scope.primary_metric) : t("Choose a metric"), detail: recipe.description || t("Enter the analysis purpose") } },
    ...steps.map((step, i) => ({ id: `step:${i}`, type: "recipe", position: { x: pipeline ? 200 : 40 + (i % 2) * 300, y: pipeline ? 200 + i * 180 : 220 + Math.floor(i / 2) * 180 }, data: { kind: pipeline ? `STEP ${i + 1} · ${step.id || ""}` : t("Available Method"), label: displayMethod(step.method), detail: pipeline ? stepDetail(step) : step.method } })),
  ].map(n => ({ ...n, ...positions.find(p => p.id === n.id), data: n.data, selected: n.id === (selected < 0 ? "scope" : `step:${selected}`) }));
  const edges: Edge[] = steps.map((step, i) => {
    const fromPrevious = i > 0 && Object.values(step.params).some(value => value && typeof value === "object" && !Array.isArray(value) && (value as Record<string, unknown>).source === "step" && (value as Record<string, unknown>).step_id === steps[i - 1].id);
    return { id: `edge:${i}`, source: pipeline && i > 0 ? `step:${i - 1}` : "scope", target: `step:${i}`,
      label: t(pipeline ? fromPrevious ? "Selected from the previous result" : "Next step" : "Allowed"), style: { stroke: "var(--dl-border-strong)", strokeWidth: 2 } };
  });
  if (pipeline) steps.forEach((step, i) => {
    const sourceIds = new Set(Object.values(step.params).flatMap(value => value && typeof value === "object" && !Array.isArray(value) && (value as Record<string, unknown>).source === "step" ? [String((value as Record<string, unknown>).step_id)] : []));
    sourceIds.forEach(id => {
      const from = steps.findIndex(item => item.id === id);
      if (from < 0 || from === i - 1) return;
      edges.push({ id: `selection:${from}:${i}`, source: `step:${from}`, target: `step:${i}`, sourceHandle: "selection-out", targetHandle: "selection-in", type: "smoothstep", label: t("Uses step {number} result", { number: from + 1 }), style: { stroke: "var(--accent)", strokeDasharray: "4 4" } });
    });
  });
  const nextVersion = saved ? bump(saved.version) : recipe.version;
  function writeError(cause: unknown) {
    const field = validationField(cause);
    if (field) {
      setFieldError(field); setDialog(false); setPublishDialog(false); setAdding(false);
      const match = /^steps\[(\d+)\]/.exec(field.field);
      setSelected(match ? Number(match[1]) : -1);
    } else setError(explainError(cause, t));
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
    <header className={s.header}><div><Link className={s.back} href="/recipes"><ArrowLeft size={14} />{t("Recipes")}</Link><h1>{saved ? t("Edit analysis procedure") : t("New analysis procedure")}</h1><span className={s.nodeStatus}>{dirty ? t("Unsaved changes") : t("v{version} · {status}", { version: saved?.version, status: saved?.status === "draft" ? t("Draft") : t("Published") })}</span></div><div className={s.actions}>
      <button type="button" className={s.secondary} aria-pressed={yamlOpen} onClick={() => setYamlOpen(!yamlOpen)}><Code2 size={16} />{yamlOpen ? t("Close code") : t("View code")}</button>
      {dirty && saved && <button className={s.secondary} title={t("Revert to the saved version")} onClick={() => { setRecipe(saved); setSelected(-1); setPositions([]); setFieldError(null); }}><Undo2 size={16} />{t("Revert")}</button>}
      {dirty && steps.length > 0 && <button disabled={busy || !recipe.semantic_scope.primary_metric} onClick={() => { setError(""); setDialog(true); }}><Save size={16} />{t("Save draft")}</button>}
      {!dirty && saved?.status === "draft" && <button disabled={busy} onClick={() => { setError(""); setPublishDialog(true); }}><Check size={16} />{t("Review for publishing")}</button>}
      {!dirty && saved?.status !== "draft" && saved && <button disabled={busy} onClick={() => router.push(`/recipes/${encodeURIComponent(recipe.name)}`)}><Play size={16} />{t("Run analysis")}</button>}
      {saved && !busy && <RecipeDelete recipe={saved} onDeleted={() => { setSaved(undefined); setRecipe(blank()); router.push("/recipes"); }} />}
    </div></header>
    {(catalogError || methodsError) && <p className={s.error} role="alert">{catalogError?.message || methodsError?.message} <Link href="/sources">{t("Check connection")}</Link></p>}
    {error && !dialog && <p className={s.error} role="alert">{error}</p>}
    {!!recipe.origin_runs?.length && <div className={s.reviewNotice}><strong>{t("Analysis procedure taken from a run")}</strong><Link href={`/runs/${recipe.origin_runs[0]}`}>{t("View original run")} <ArrowRight size={14} /></Link><p>{recipe.steps.length}{t("steps / dates are chosen at execution")}</p>{!!reviewNotes.length && <p>{t("Check the groups and periods that were set directly. To select from the data on every run, set a previous result in the step settings.")}</p>}</div>}
    {fieldError && <p className={s.error} role="alert">{t("Check before saving:")} {fieldError.message}</p>}
    <div className={s.toolbar}><span className={s.recipeMode}>{pipeline ? t("Analysis procedure · {count} steps", { count: steps.length }) : t("Analyses for exploration · {count}", { count: steps.length })}</span>{steps.length > 0 && <button disabled={!recipe.semantic_scope.primary_metric} onClick={() => { setAdding(true); setSearch(""); }}><Plus size={16} />{pipeline ? t("Add analysis step") : t("Add allowed Method")}</button>}</div>
    <div className={s.workspace}>
      <section className={s.canvas} aria-label={t("Recipe graph")}><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={changes => setPositions(applyNodeChanges(changes, nodes))} onNodeClick={(_, node) => { setSelected(node.id === "scope" ? -1 : Number(node.id.split(":")[1])); setAdding(false); }} nodesConnectable={false} deleteKeyCode={null} fitView minZoom={.25} maxZoom={1.1}><FitRecipe count={steps.length} /><Background color="var(--dl-border-strong)" gap={20} /><Controls showInteractive={false} /></ReactFlow>
        {!steps.length && <div className={s.canvasEmpty}>{recipe.semantic_scope.primary_metric ? <button onClick={() => setAdding(true)}><Plus size={16} />{t("Add the first analysis")}</button> : <button onClick={() => metricSelect.current?.focus()}>{t("Choose a metric")} <ArrowRight size={16} /></button>}</div>}
      </section>
      <aside ref={inspector} className={s.inspector}>
        {adding ? <><h2>{t("Choose a Method")}</h2><label className={s.search}><Search size={16} /><input aria-label={t("Search Methods")} value={search} placeholder={t("trend, by group, matched")} onChange={e => setSearch(e.target.value)} /></label><div className={s.choices}>{(methods || []).filter(m => (pipeline || !recipe.allowed_methods.includes(m.name)) && `${displayMethod(m.name)} ${m.name} ${m.description}`.toLowerCase().includes(search.toLowerCase())).map(m => <button key={m.name} onClick={() => add(m.name)}><span>{displayMethod(m.name)}</span><Plus size={16} /><small>{m.description}</small></button>)}</div><button className={s.secondary} onClick={() => setAdding(false)}>{t("Cancel")}</button></> : !active ? <div className={s.fields}>
          <h2>{t("Analysis procedure details")}</h2><label>{t("Which question is this analysis for?")}<textarea rows={2} value={recipe.routing.objective || recipe.description} placeholder={t("e.g. check changes in the metric and find the largest contributors")} onChange={e => change({ ...recipe, description: e.target.value, routing: { ...recipe.routing, objective: e.target.value } })} /></label>
          <RefField label={t("Metric to analyze")} selectRef={metricSelect} value={recipe.semantic_scope.primary_metric} objects={objects.filter(o => o.kind === "measure")} fieldPath="semantic_scope.primary_metric" error={fieldError?.field === "semantic_scope.primary_metric" ? fieldError.message : undefined} onChange={v => change({ ...recipe, name: recipe.name || newName(String(v)), semantic_scope: { ...recipe.semantic_scope, primary_metric: String(v) } })} />
        </div> : <div className={s.fields}>
          <button type="button" className={s.inspectorBack} onClick={() => { setSelected(-1); setAdding(false); }}><ArrowLeft size={14} />{t("Analysis procedure details")}</button>
          <div className={s.inspectorHeading}><span className={s.eyebrow}>{pipeline ? `STEP ${selected + 1}` : "ALLOWED METHOD"}</span><div className={s.actions}>
            {pipeline && <><button className={s.icon} disabled={selected === 0} title={t("Move up")} aria-label={t("Move up")} onClick={() => { const next = [...recipe.steps]; [next[selected - 1], next[selected]] = [next[selected], next[selected - 1]]; if (updateSteps(next)) setSelected(selected - 1); }}><ArrowUp size={16} /></button><button className={s.icon} disabled={selected === steps.length - 1} title={t("Move down")} aria-label={t("Move down")} onClick={() => { const next = [...recipe.steps]; [next[selected + 1], next[selected]] = [next[selected], next[selected + 1]]; if (updateSteps(next)) setSelected(selected + 1); }}><ArrowDown size={16} /></button></>}
            <button className={s.icon} title={t("Delete step")} aria-label={t("Delete step")} onClick={() => pipeline ? updateSteps(recipe.steps.filter((_, i) => i !== selected)) : change({ ...recipe, allowed_methods: recipe.allowed_methods.filter((_, i) => i !== selected) })}><Trash2 size={16} /></button>
          </div></div>
          <h2>{displayMethod(active.method)}</h2>
          {active.method_version && <p className={s.dependency}>{t("Pinned version for this step / v")}{active.method_version}</p>}
          {pinnedError && <p className={s.error} role="alert">{pinnedError.message}</p>}
          {pipeline && active.method_version && latestManifest && active.method_version !== latestManifest.version && <button type="button" className={s.secondary} disabled={busy} onClick={() => configure({ ...recipe, steps:recipe.steps.map((step,index) => index===selected ? { ...step, method_version:latestManifest.version, bindings:{}, params:{} } : step) },selected)}>v{latestManifest.version}  {t("Apply and reset input settings")}</button>}
          {pipeline && activeManifest ? <StepSettings key={`${selected}-${active.method}-${active.method_version || "latest"}`} step={active} manifest={activeManifest} methods={methods ?? []} objects={objects} recipe={recipe} stepIndex={selected} fieldError={fieldError} onChange={step => change({ ...recipe, steps: recipe.steps.map((s, i) => i === selected ? step : s) })} /> : !pipeline ? <p className={s.dependency}>{t("When this Recipe is chosen from MCP, the next analysis and inputs are decided from each result.")}</p> : <p role="status">{t("Loading analysis settings…")}</p>}
          {pipeline && <section className={s.previewSection} aria-label={t("Check result")}>
            {previewFormOpen && <>
              <RecipeRuntimeInputs specs={recipe.inputs ?? {}} values={previewInputs} onChange={setPreviewInputs} objects={objects} />
              {previewWithPeriod && (timeOptions.length > 1 || !selectedTime) && <label>{t("Date basis")}<select aria-label={t("Preview date dimension")} value={selectedTime} onChange={event => setPreviewTimeDimension(event.target.value)}><option value="">{t("Choose…")}</option>{timeOptions.map(object => <option value={object.ref} key={object.ref}>{object.title}</option>)}</select></label>}
              {previewWithPeriod && <div className={s.previewDates}><label>{t("Start date")}<input type="date" aria-label={t("Preview start date")} value={previewRange[0]} onChange={event => choosePreviewDates([event.target.value, previewRange[1]])} /></label><label>{t("End date")}<input type="date" aria-label={t("Preview end date")} value={previewRange[1]} onChange={event => choosePreviewDates([previewRange[0], event.target.value])} /></label></div>}
              {previewDatesInvalid && <p className={s.error} role="alert">{t("Check the start and end dates.")}</p>}
              {previewWithPeriod && !selectedTime && <p className={s.nodeStatus}>{t("Choose a date dimension.")}</p>}
            </>}
            {missingRoles.length > 0 && <p className={s.nodeStatus}>{t("Choose {fields}.", { fields: missingRoles.map(([name, role]) => role.label || (roleLabels[name] ? t(roleLabels[name]) : name)).join(", ") })}</p>}
            <button type="button" disabled={previewBusy || !activeManifest || missingRoles.length > 0 || !recipe.semantic_scope.primary_metric || previewFormOpen && (previewDatesInvalid || previewWithPeriod && !selectedTime)} onClick={() => { if (!previewFormOpen && (previewWithPeriod || Object.keys(recipe.inputs ?? {}).length)) setPreviewFormOpen(true); else void startPreview(); }}><Play size={15} />{previewBusy ? t("Checking…") : previewFormOpen ? t("Check with these conditions") : t("Check result")}</button>
            {previewError && <p className={s.error} role="alert">{previewError} <Link href="/sources">{t("Check connection")}</Link></p>}
          </section>}
        </div>}
      </aside>
    </div>
    {yamlOpen && <section className={s.previewOutput} aria-label={t("Recipe code")}><h2>{t("Recipe code")}</h2><div className={s.fields}>
            <label data-recipe-field="name">Recipe ID<input value={recipe.name} disabled={!!saved} onChange={event => change({ ...recipe, name: event.target.value })} /></label>
            <label>Recipe YAML<textarea aria-label="Recipe YAML" rows={18} spellCheck={false} value={yamlText} onChange={event => { setYamlText(event.target.value); setYamlDirty(true); setYamlError(""); }} /></label>
            {yamlDirty && <span className={s.nodeStatus}>{t("Apply the YAML changes to the graph to save them.")}</span>}
            {yamlError && <p className={s.error} role="alert">{yamlError}</p>}
            <div className={s.actions}><button type="button" disabled={!yamlDirty || yamlBusy} onClick={applyYaml}><Check size={14} />{yamlBusy ? t("Validating…") : t("Apply YAML")}</button><button type="button" className={s.secondary} disabled={yamlBusy} onClick={() => { setYamlDirty(false); setYamlError(""); }}>{t("Reload from the graph")}</button></div>
          </div></section>}
    {previewIndex === selected && previewRun && <section ref={previewOutput} className={s.previewOutput} aria-label={t("Preview result")} aria-live="polite">
      <div className={s.previewOutputHeading}><div><span className={s.eyebrow}>STEP {selected + 1}</span><h2>{t("Preview result")}</h2></div><Link href={`/runs/${previewRun.id}`}>{t("View execution evidence")} <ArrowRight size={14} /></Link></div>
      {previewRun.running && <p role="status">{previewRun.steps.length}/{selected + 1}{t("Running step /")} {previewElapsed}{t("s")}</p>}
      {previewRun.needs_input && <RunPeriodInput key={`${previewRun.id}:${previewRun.scope_revision}`} run={previewRun} objects={objects} onDone={setPreviewRun} />}
      {previewRun.error && <p className={s.error} role="alert">{previewRun.error.message}</p>}
      {stoppedPreviewStep !== null && <div className={s.previewStopped}><span>{stoppedPreviewStep + 1}{t("preview stopped at this step.")}</span><button type="button" className={s.secondary} onClick={() => { setSelected(stoppedPreviewStep); inspector.current?.scrollTo({ top: 0, behavior: "smooth" }); }}>{stoppedPreviewStep + 1}{t("Check step settings")} <ArrowRight size={14} /></button></div>}
      {!previewRun.running && <><ValidationList items={previewRun.validation} />{previewRun.steps.at(-1) && <ResultView result={previewRun.steps.at(-1)!.result} titles={byRef} />}</>}
    </section>}
    {dialog && <div className={s.overlay}><section className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="recipe-dialog-title"><div className={s.inspectorHeading}><h2 id="recipe-dialog-title">{t("Save draft")}</h2><button className={s.icon} disabled={busy} aria-label={t("Close")} onClick={() => setDialog(false)}><X size={18} /></button></div>
      <p>{recipe.description || recipe.name} · v{nextVersion} · {t("{count} steps", { count: steps.length })}</p><h3>{t("Changes")}</h3><ul className={s.changeList}>{recipeChanges(saved, recipe, title, t).map((item, index) => <li key={`${index}:${item}`}>{item}</li>)}</ul><button className={s.run} disabled={busy || !recipe.name || !recipe.semantic_scope.primary_metric || !steps.length} onClick={save}><Save size={16} />{busy ? t("Saving…") : t("Save draft version")}</button>
      {error && <p className={s.error} role="alert">{error}</p>}
    </section></div>}
    {publishDialog && <div className={s.overlay}><section className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="publish-dialog-title"><div className={s.inspectorHeading}><h2 id="publish-dialog-title">{t("Publish analysis procedure")}</h2><button className={s.icon} disabled={busy} aria-label={t("Close")} onClick={() => setPublishDialog(false)}><X size={18} /></button></div>
      <p>{recipe.description || recipe.name}  {t("/ Draft v")}{saved?.version} · {t("{count} steps", { count: steps.length })}</p><p>{t("Publishing shows the new version in the Recipe list and MCP so it can run. The current draft is kept.")}</p>
      <ul className={s.changeList}><li>{t("Analysis metric /")} {title(recipe.semantic_scope.primary_metric)}</li>{steps.map((step, index) => <li key={step.id || index}>{index + 1}{t("Step /")} {displayMethod(step.method)}</li>)}</ul>
      <button className={s.run} disabled={busy} onClick={publish}><Check size={16} />{busy ? t("Validating…") : t("Validate and publish")}</button>{error && <p className={s.error} role="alert">{error}</p>}
    </section></div>}
  </div>;
}
