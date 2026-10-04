"use client";

import { useEffect, useRef, useState, type Ref } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Background, Controls, Handle, Position, ReactFlow, applyNodeChanges, useNodesInitialized, useReactFlow, type Node, type NodeProps } from "@xyflow/react";
import { ArrowLeft, ArrowRight, ArrowDown, ArrowUp, Check, GitBranch, Play, Plus, Save, Search, Trash2, Undo2, Workflow, X } from "lucide-react";
import "@xyflow/react/dist/style.css";
import { api, ApiError, type MethodManifest, type ParamSpec, type PlanStep, type Recipe, type RecipeCandidate, type RoleSpec, type Run, type SemanticObject, type SourceReadiness } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import { methodName } from "@/lib/method-name";
import { ResultView, ValidationList } from "@/components/result";
import { recipeChanges } from "@/lib/recipe-changes";
import s from "./analysis-canvas.module.css";

const blank = (): Recipe => ({ name: "", version: "1.0.0", description: "", status: "draft", mode: "pipeline", routing: { use_for: [], do_not_use_for: [] }, semantic_scope: { primary_metric: "", related_metrics: [], preferred_dimensions: [], required_filters: [] }, steps: [], allowed_methods: [], validators: [], limits: { max_steps: 12, max_queries: 30 } });
const bump = (version: string) => version.replace(/\d+$/, n => String(Number(n) + 1));
const refs = (value: unknown): string[] => Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
const newName = (metric: string) => `${metric.split("/").pop()?.replaceAll("_", "-") || "analysis"}-${crypto.randomUUID().slice(0, 6)}`;
const previewDates = (): [string, string] => {
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), 1);
  const date = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
  return [date(start), date(today)];
};
const explainError = (error: unknown) => {
  if (error instanceof ApiError && error.details && typeof error.details === "object" && "field" in error.details) {
    const field = (error.details as { field?: unknown }).field;
    if (typeof field === "string") return `${field}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Recipe를 저장하지 못했습니다.";
};
type FieldError = { field: string; message: string };
function validationField(error: unknown): FieldError | null {
  if (!(error instanceof ApiError)) return null;
  const details = error.details;
  if (details && typeof details === "object" && "field" in details && typeof details.field === "string")
    return { field: details.field, message: error.message };
  if (Array.isArray(details) && Array.isArray(details[0]?.loc)) {
    const path = details[0].loc.filter((part: unknown) => part !== "body").reduce((value: string, part: unknown) =>
      typeof part === "number" ? `${value}[${part}]` : value ? `${value}.${part}` : String(part), "");
    return path ? { field: path, message: String(details[0].msg || error.message) } : null;
  }
  return null;
}

function RecipeNode({ data, selected }: NodeProps) {
  return <div className={`${s.node} ${selected ? s.selected : ""}`}>
    <Handle type="target" position={Position.Top} />
    <span className={s.nodeKind}>{data.scope ? <GitBranch size={16} /> : <Workflow size={16} />}{String(data.kind)}</span>
    <strong>{String(data.label)}</strong><span className={s.nodeStatus}>{String(data.detail)}</span>
    <Handle type="source" position={Position.Bottom} />
  </div>;
}
const nodeTypes = { recipe: RecipeNode };

function FitRecipe({ count }: { count: number }) {
  const initialized = useNodesInitialized();
  const { fitView } = useReactFlow();
  useEffect(() => {
    if (initialized) void fitView({ padding: 0.18, duration: 200 });
  }, [initialized, count, fitView]);
  return null;
}

function RefField({ label, value, objects, multiple, onChange, inherited, selectRef, error, fieldPath }: {
  label: string; value: unknown; objects: SemanticObject[]; multiple?: boolean;
  onChange: (value: string | string[]) => void; inherited?: string; selectRef?: Ref<HTMLSelectElement>; error?: string; fieldPath?: string;
}) {
  const list = refs(value);
  const expression = typeof value === "string" && value.startsWith("$") ? value : null;
  return <div className={s.refField} data-recipe-field={fieldPath}><span>{label}</span>{expression ? <div className={s.inherited}><span>{inherited || expression}</span><button type="button" className={s.secondary} onClick={() => onChange(multiple ? [] : "")}>직접 선택</button></div> : multiple ? <>
    {list.map((ref, i) => <div className={s.refRow} key={`${ref}-${i}`}><span>{objects.find(o => o.ref === ref)?.title || ref}</span><button type="button" className={s.icon} title={`${label} 삭제`} aria-label={`${label} ${i + 1} 삭제`} onClick={() => onChange(list.filter((_, j) => i !== j))}><X size={14} /></button></div>)}
    <select aria-label={label} aria-invalid={!!error} value="" onChange={e => e.target.value && onChange([...list, e.target.value])}><option value="">선택해서 추가</option>{objects.filter(o => !list.includes(o.ref)).map(o => <option key={o.ref} value={o.ref}>{o.title}</option>)}</select>
  </> : <select ref={selectRef} aria-label={label} aria-invalid={!!error} value={list[0] || ""} onChange={e => onChange(e.target.value)}><option value="">선택하세요</option>{list[0] && !objects.some(o => o.ref === list[0]) && <option value={list[0]}>카탈로그에서 이름 확인 필요</option>}{objects.map(o => <option key={o.ref} value={o.ref}>{o.title}</option>)}</select>}{error && <small className={s.fieldError} role="alert">{error}</small>}</div>;
}

function roleObjects(role: RoleSpec, objects: SemanticObject[]) {
  if (role.kind === "measure") return objects.filter((object) => object.kind === "measure");
  if (role.kind === "dimension") return objects.filter((object) => object.kind === "dimension" || object.kind === "time_dimension");
  if (role.kind === "time_dimension") return objects.filter((object) => object.kind === "time_dimension");
  return objects.filter((object) => !!object.entity);
}

const roleLabels: Record<string, string> = {
  metric: "분석 지표", related: "함께 볼 지표", dimensions: "나눠 볼 순서", conditions: "비교 조건",
  treatment: "비교 대상", treatment_measure: "비교 기준 지표", entity: "분석 단위",
};
const parameterLabel = (name: string) => ({ granularity: "시간 단위", vs_previous: "직전 같은 길이와 비교", top_n: "표시할 그룹 수", min_count: "최소 그룹 건수", rank_by: "정렬 기준" } as Record<string, string>)[name] || name;

function ParameterField({ name, spec, value, onChange, disabled = false, error, fieldPath, objects = [] }: { name: string; spec: ParamSpec; value: unknown; onChange: (value: unknown) => void; disabled?: boolean; error?: string; fieldPath?: string; objects?: SemanticObject[] }) {
  const label = parameterLabel(name);
  const current = value ?? spec.default;
  if (spec.type === "drill_path" && ["subject", "peers"].includes(name)) {
    const items = Array.isArray(current) ? current as { member: string; value: unknown }[] : [];
    const change = (index: number, patch: Record<string, unknown>) => onChange(items.map((item, i) => i === index ? { ...item, ...patch } : item));
    return <fieldset disabled={disabled} data-recipe-field={fieldPath}><legend>{name === "subject" ? "비교할 대상" : "동료 집단 조건"}</legend>
      {items.map((item, index) => <div key={index} className={s.refField}>
        <select aria-label={`${name === "subject" ? "대상" : "동료"} 차원 ${index + 1}`} value={item.member} onChange={event => change(index, { member: event.target.value, value: "" })}><option value="">차원 선택</option>{objects.filter(object => object.kind === "dimension").map(object => <option key={object.ref} value={object.ref}>{object.title}</option>)}</select>
        <input aria-label={`${name === "subject" ? "대상" : "동료"} 값 ${index + 1}`} placeholder="값 입력" value={String(item.value ?? "")} onChange={event => change(index, { value: objects.find(object => object.ref === item.member)?.data_type === "number" && event.target.value !== "" ? Number(event.target.value) : event.target.value })} />
        <button type="button" className={s.secondary} onClick={() => onChange(items.filter((_, i) => i !== index))}><X size={13} />삭제</button>
      </div>)}
      {(name === "peers" || !items.length) && <button type="button" className={s.secondary} onClick={() => onChange([...items, { member: "", value: "" }])}><Plus size={13} />{name === "subject" ? "대상 선택" : "조건 추가"}</button>}
      {error && <small className={s.fieldError} role="alert">{error}</small>}
    </fieldset>;
  }
  const options: Record<string, string> = { day: "일별", week: "주별", month: "월별", quarter: "분기별", value: "지표 값", vs_rest: "나머지 그룹과의 차이", count: "건수", desc: "높은 값부터", asc: "낮은 값부터" };
  if (typeof current === "string" && current.startsWith("$")) return <div className={s.refField}><span>{label}</span><code className={s.expression}>{current}</code></div>;
  if (spec.type === "boolean") return <label className={s.check} data-recipe-field={fieldPath}><input type="checkbox" aria-invalid={!!error} disabled={disabled} checked={!!current} onChange={event => onChange(event.target.checked)} />{label}{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  if (spec.type === "enum") return <label data-recipe-field={fieldPath}>{label}<select aria-label={label} aria-invalid={!!error} disabled={disabled} value={String(current ?? "")} onChange={event => onChange(event.target.value)}>{(spec.enum || []).map(option => <option value={option} key={option}>{options[option] || option}</option>)}</select>{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  if (spec.type === "integer" || spec.type === "number") return <label data-recipe-field={fieldPath}>{label}<input type="number" aria-invalid={!!error} disabled={disabled} step={spec.type === "integer" ? 1 : "any"} min={spec.minimum ?? undefined} max={spec.maximum ?? undefined} value={current == null ? "" : Number(current)} onChange={event => onChange(event.target.value === "" ? null : Number(event.target.value))} /><small>{spec.description}</small>{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  if (spec.type === "string") return <label data-recipe-field={fieldPath}>{label}<input aria-invalid={!!error} disabled={disabled} value={String(current ?? "")} onChange={event => onChange(event.target.value)} /><small>{spec.description}</small>{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  return null;
}

function StepSettings({ step, manifest, onChange, objects, recipe, stepIndex, fieldError }: { step: PlanStep; manifest: MethodManifest; onChange: (s: PlanStep) => void; objects: SemanticObject[]; recipe: Recipe; stepIndex: number; fieldError: FieldError | null }) {
  const advancedRef = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (fieldError?.field.startsWith(`steps[${stepIndex}].`)) advancedRef.current?.setAttribute("open", "");
  }, [fieldError, stepIndex]);
  const bind = (key: string, value: unknown) => onChange({ ...step, bindings: { ...step.bindings, [key]: value } });
  const param = (key: string, value: unknown) => onChange({ ...step, params: { ...step.params, [key]: value } });
  const basicParameters = Object.entries(manifest.parameters).filter(([, spec]) => spec.ui_group === "basic");
  const advancedParameters = Object.entries(manifest.parameters).filter(([, spec]) => spec.ui_group !== "basic" && ["boolean", "enum", "integer", "number", "string"].includes(spec.type));
  const policy = recipe.method_parameters?.[step.method];
  const fixed = (name: string) => Object.hasOwn(policy?.fixed ?? {}, name);
  const parameterValue = (name: string) => fixed(name) ? policy!.fixed[name] : step.params[name];
  const metricBinding = step.bindings.metric;
  const usesRecipeMetric = metricBinding === "$scope.primary_metric";
  const metricRef = usesRecipeMetric ? recipe.semantic_scope.primary_metric : metricBinding;
  const metricTitle = typeof metricRef === "string" ? objects.find(o => o.ref === metricRef)?.title || metricRef || "지표 미설정" : "지표 미설정";
  const reset = (name: string) => { const params = { ...step.params }; delete params[name]; onChange({ ...step, params }); };
  const roleField = ([name, role]: [string, RoleSpec]) => {
    const inherited = name === "metric" ? objects.find(o => o.ref === recipe.semantic_scope.primary_metric)?.title || "미선택"
      : name === "dimensions" ? recipe.semantic_scope.preferred_dimensions.map(ref => objects.find(o => o.ref === ref)?.title || ref).join(" → ") || "미선택" : undefined;
    const path = `steps[${stepIndex}].bindings.${name}`;
    return <RefField key={name} label={roleLabels[name] || name} value={step.bindings[name]} objects={roleObjects(role, objects)} multiple={role.multiple} inherited={inherited} fieldPath={path} error={fieldError?.field === path ? fieldError.message : undefined} onChange={next => bind(name, next)} />;
  };
  return <>
    {manifest.roles.metric && <div className={s.refField}><span>분석 지표</span><div className={s.inherited}><span>{metricTitle}</span><small>{usesRecipeMetric ? "Recipe 지표 사용" : "이 단계에서만 사용"}</small></div></div>}
    {policy && <div className={s.policyNotice}><strong>Recipe 실행 정책</strong>{Object.keys(policy.fixed).length > 0 && <span>고정값: {Object.entries(policy.fixed).map(([name, value]) => `${name}=${JSON.stringify(value)}`).join(", ")}</span>}{policy.runtime_allowed && <span>실행 중 선택 가능: {policy.runtime_allowed.length ? policy.runtime_allowed.join(", ") : "없음"}</span>}</div>}
    {Object.entries(manifest.roles).filter(([name, role]) => name !== "metric" && role.required).map(roleField)}
    {basicParameters.map(([name, spec]) => { const path = `steps[${stepIndex}].params.${name}`; return <ParameterField key={name} objects={objects} name={name} spec={spec} value={parameterValue(name)} disabled={fixed(name)} fieldPath={path} error={fieldError?.field === path ? fieldError.message : undefined} onChange={value => param(name, value)} />; })}
    <details ref={advancedRef} className={s.advanced}><summary>고급 설정</summary><div className={s.fields}>
      {manifest.roles.metric && <><RefField label="이 단계에서 사용할 지표" value={metricBinding} objects={roleObjects(manifest.roles.metric, objects)} inherited={metricTitle} fieldPath={`steps[${stepIndex}].bindings.metric`} error={fieldError?.field === `steps[${stepIndex}].bindings.metric` ? fieldError.message : undefined} onChange={next => bind("metric", next)} />
        {!usesRecipeMetric && <button type="button" className={s.secondary} onClick={() => bind("metric", "$scope.primary_metric")}><Undo2 size={13} />Recipe 지표 사용</button>}</>}
      {Object.entries(manifest.roles).filter(([name, role]) => name !== "metric" && !role.required).map(roleField)}
      {advancedParameters.map(([name, spec]) => { const path = `steps[${stepIndex}].params.${name}`; return <div className={s.parameter} key={name}><ParameterField name={name} spec={spec} value={parameterValue(name)} disabled={fixed(name)} fieldPath={path} error={fieldError?.field === path ? fieldError.message : undefined} onChange={value => param(name, value)} />
        {Object.hasOwn(step.params, name) && !fixed(name) && <button type="button" className={s.secondary} onClick={() => reset(name)}><Undo2 size={13} />기본값 사용</button>}</div>; })}
    </div></details>
  </>;
}

function MethodPolicyEditor({ recipe, methods, onChange }: { recipe: Recipe; methods: MethodManifest[]; onChange: (recipe: Recipe) => void }) {
  const used = new Set(recipe.mode === "pipeline" ? recipe.steps.map(step => step.method) : recipe.allowed_methods);
  const scalar = (spec: ParamSpec) => ["boolean", "enum", "integer", "number", "string"].includes(spec.type);
  const update = (method: string, fixed: Record<string, unknown>, runtimeAllowed: string[] | null, removeStepParam?: string) => {
    const policies = { ...recipe.method_parameters };
    if (!Object.keys(fixed).length && runtimeAllowed === null) delete policies[method];
    else policies[method] = { fixed, runtime_allowed: runtimeAllowed };
    onChange({ ...recipe, method_parameters: policies,
      steps: removeStepParam ? recipe.steps.map(step => {
        if (step.method !== method) return step;
        const params = { ...step.params }; delete params[removeStepParam];
        return { ...step, params };
      }) : recipe.steps });
  };
  return <details className={s.advanced}><summary>실행 정책</summary><div className={s.fields}>
    <p className={s.nodeStatus}>고정값은 이 Method의 모든 단계에 적용됩니다. 고정하면 기존 단계별 값은 제거됩니다.</p>
    {methods.filter(method => used.has(method.name)).map(method => {
      const policy = recipe.method_parameters?.[method.name];
      const fixed = policy?.fixed ?? {};
      const runtimeAllowed = policy?.runtime_allowed ?? null;
      return <section key={method.name} className={s.policyEditor}><h3>{methodName(method.name)}</h3>
        {Object.entries(method.parameters).filter(([, spec]) => scalar(spec)).map(([name, spec]) => {
          const selected = Object.hasOwn(fixed, name);
          return <div key={name} className={s.policyRow}><label className={s.check}><input type="checkbox" aria-label={`${methodName(method.name)} ${name} 고정`} checked={selected} onChange={event => {
            const next = { ...fixed };
            if (event.target.checked) next[name] = recipe.steps.find(step => step.method === method.name && step.params[name] !== undefined)?.params[name] ?? spec.default ?? (spec.enum?.[0] ?? (spec.type === "boolean" ? false : spec.type === "string" ? "" : spec.minimum ?? 0));
            else delete next[name];
            update(method.name, next, runtimeAllowed?.filter(value => value !== name) ?? null, event.target.checked ? name : undefined);
          }} />{parameterLabel(name)} 고정</label>
            {selected && <ParameterField name={name} spec={spec} value={fixed[name]} onChange={value => update(method.name, { ...fixed, [name]: value }, runtimeAllowed)} />}
          </div>;
        })}
        <label className={s.check}><input type="checkbox" aria-label={`${methodName(method.name)} 실행 중 변경 제한`} checked={runtimeAllowed !== null} onChange={event => update(method.name, { ...fixed }, event.target.checked ? [] : null)} />실행 중 변경할 설정 제한</label>
        {runtimeAllowed !== null && <div className={s.policyAllowed}>{Object.entries(method.parameters).filter(([name, spec]) => scalar(spec) && !Object.hasOwn(fixed, name)).map(([name]) =>
          <label key={name} className={s.check}><input type="checkbox" aria-label={`${methodName(method.name)} ${name} 실행 중 허용`} checked={runtimeAllowed.includes(name)} onChange={event => update(method.name, { ...fixed }, event.target.checked ? [...runtimeAllowed, name] : runtimeAllowed.filter(value => value !== name))} />{parameterLabel(name)}</label>)}</div>}
      </section>;
    })}
  </div></details>;
}

export function RecipeEditor({ initial }: { initial?: Recipe }) {
  const router = useRouter();
  const { objects, byRef, error: catalogError } = useCatalog();
  const { data: methods, error: methodsError } = useApi<MethodManifest[]>("/methods");
  const { data: readiness } = useApi<SourceReadiness>("/sources/current/readiness");
  const [recipe, setRecipe] = useState<Recipe>(() => initial || blank());
  const [saved, setSaved] = useState<Recipe | undefined>(initial);
  const [selected, setSelected] = useState(-1);
  const [positions, setPositions] = useState<Node[]>([]);
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState<FieldError | null>(null);
  const [dialog, setDialog] = useState(false);
  const [publishDialog, setPublishDialog] = useState(false);
  const [yamlOpen, setYamlOpen] = useState(false);
  const [yamlText, setYamlText] = useState("");
  const [yamlBase, setYamlBase] = useState("");
  const [yamlDirty, setYamlDirty] = useState(false);
  const [yamlBusy, setYamlBusy] = useState(false);
  const [yamlError, setYamlError] = useState("");
  const [reviewNotes, setReviewNotes] = useState<string[]>([]);
  const [previewRange, setPreviewRange] = useState<[string, string]>(previewDates);
  const [previewTimeDimension, setPreviewTimeDimension] = useState("");
  const [previewRun, setPreviewRun] = useState<Run | null>(null);
  const [previewIndex, setPreviewIndex] = useState(-1);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [previewElapsed, setPreviewElapsed] = useState(0);
  const metricSelect = useRef<HTMLSelectElement>(null);
  const previewOutput = useRef<HTMLElement>(null);
  const inspector = useRef<HTMLElement>(null);
  const recipeAdvanced = useRef<HTMLDetailsElement>(null);
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
    : timeOptions.length === 1 ? timeOptions[0].ref : "";
  const previewNeedsTime = timeOptions.length > 0 || (pipeline && selected >= 0 && steps.slice(0, selected + 1).some(step => step.method === "query.trend"));
  const previewDatesInvalid = timeOptions.length > 0 && (!previewRange[0] || !previewRange[1] || previewRange[0] > previewRange[1]);
  const stoppedPreviewStep = previewRun && !previewRun.running && previewRun.steps.length < previewIndex + 1
    ? previewRun.steps.at(-1)?.result.status !== "success" && previewRun.steps.length ? previewRun.steps.length - 1
      : previewRun.error && previewRun.steps.length ? previewRun.steps.length : null
    : null;
  useEffect(() => {
    if (initial) return;
    const params = new URLSearchParams(window.location.search);
    const sourceRun = params.get("from_run");
    if (sourceRun) {
      const indices = params.getAll("step");
      const query = new URLSearchParams();
      for (const index of indices) query.append("indices", index);
      void api<RecipeCandidate>(`/runs/${encodeURIComponent(sourceRun)}/recipe-candidate?${query}`).then(candidate => {
        setRecipe(candidate.recipe); setReviewNotes(candidate.review_notes);
      }).catch(cause => setError(explainError(cause)));
      return;
    }
    const method = params.get("method");
    const metric = params.get("metric") || "";
    setRecipe(r => ({ ...r, name: metric ? newName(metric) : "", semantic_scope: { ...r.semantic_scope, primary_metric: metric }, steps: method ? [{ id: "step_1", method, bindings: { metric: "$scope.primary_metric" }, params: {} }] : [] }));
  }, [initial]);
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
    if (!fieldError.field.startsWith("steps[")) recipeAdvanced.current?.setAttribute("open", "");
    const timer = window.setTimeout(() => {
      const field = [...document.querySelectorAll<HTMLElement>("[data-recipe-field]")].find(element => element.dataset.recipeField === fieldError.field);
      const control = field?.querySelector<HTMLElement>("input, select, textarea");
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
        scope: { date_range: selectedTime && !previewDatesInvalid ? previewRange : null, time_dimension: selectedTime || null },
      } });
      setPreviewRun(run);
    } catch (cause) { setPreviewError(explainError(cause)); }
    finally { setPreviewBusy(false); }
  }
  function add(method: string) {
    if (pipeline) {
      let id = 1; while (recipe.steps.some(step => step.id === `step_${id}`)) id++;
      const manifest = methods?.find(item => item.name === method);
      const bindings: Record<string, unknown> = {};
      if (manifest?.roles.metric) bindings.metric = "$scope.primary_metric";
      if (manifest?.roles.dimensions && recipe.semantic_scope.preferred_dimensions.length) bindings.dimensions = "$scope.preferred_dimensions";
      change({ ...recipe, steps: [...recipe.steps, { id: `step_${id}`, method, bindings, params: {} }] });
    } else change({ ...recipe, allowed_methods: [...recipe.allowed_methods, method] });
    setSelected(steps.length); setAdding(false); setPositions([]);
  }
  function updateSteps(next: PlanStep[]) {
    const seen = new Set<string>();
    for (const step of next) {
      const expressions = JSON.stringify(step).match(/\$steps\.([^."\\]+)\./g) || [];
      if (expressions.some(expression => !seen.has(expression.split(".")[1]))) { setError("이전 결과를 사용하는 단계가 있습니다. 고급 설정에서 참조를 변경한 뒤 순서를 바꾸거나 삭제해 주세요."); return false; }
      if (step.id) seen.add(step.id);
    }
    change({ ...recipe, steps: next }); setPositions([]); return true;
  }
  function stepDetail(step: PlanStep): string {
    const dimensions = step.bindings.dimensions;
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
    ...steps.map((step, i) => ({ id: `step:${i}`, type: "recipe", position: { x: pipeline ? 200 : 40 + (i % 2) * 300, y: pipeline ? 200 + i * 180 : 220 + Math.floor(i / 2) * 180 }, data: { kind: pipeline ? `STEP ${i + 1} · ${step.id || ""}` : "사용 가능한 방법", label: methodName(step.method), detail: pipeline ? stepDetail(step) : step.method } })),
  ].map(n => ({ ...n, ...positions.find(p => p.id === n.id), data: n.data, selected: n.id === (selected < 0 ? "scope" : `step:${selected}`) }));
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
    <header className={s.header}><div><Link className={s.back} href="/recipes"><ArrowLeft size={14} />분석 라이브러리</Link><h1>{saved ? "분석 절차 편집" : "새 분석 절차"}</h1><span className={s.nodeStatus}>{dirty ? "저장되지 않은 변경" : `v${saved?.version} · ${saved?.status === "draft" ? "초안" : "발행됨"}`}</span></div><div className={s.actions}>
      {dirty && saved && <button className={s.secondary} title="저장된 버전으로 되돌리기" onClick={() => { setRecipe(saved); setSelected(-1); setPositions([]); setFieldError(null); }}><Undo2 size={16} />되돌리기</button>}
      {dirty && steps.length > 0 && <button disabled={busy || !recipe.semantic_scope.primary_metric} onClick={() => { setError(""); setDialog(true); }}><Save size={16} />초안 저장</button>}
      {!dirty && saved?.status === "draft" && <button disabled={busy} onClick={() => { setError(""); setPublishDialog(true); }}><Check size={16} />발행 검토</button>}
      {!dirty && saved?.status !== "draft" && saved && <button disabled={busy} onClick={() => router.push(`/recipes/${encodeURIComponent(recipe.name)}`)}><Play size={16} />분석 실행</button>}
    </div></header>
    {(catalogError || methodsError) && <p className={s.error} role="alert">{catalogError?.message || methodsError?.message} <Link href="/sources">연결 확인</Link></p>}
    {error && !dialog && <p className={s.error} role="alert">{error}</p>}
    {!!recipe.origin_runs?.length && <div className={s.reviewNotice}><strong>실행 기록에서 만든 초안</strong><Link href={`/runs/${recipe.origin_runs[0]}`}>원본 실행 보기 <ArrowRight size={14} /></Link><p>실행 당시 기간과 공통 필터는 복사하지 않았습니다. 발행 전에 단계별 고정값을 확인하세요.</p>{reviewNotes.filter(note => note.includes("drill path") || note.includes("드릴 경로")).map(note => <p key={note}>{note}</p>)}</div>}
    {fieldError && <p className={s.error} role="alert">저장 전 확인이 필요합니다: {fieldError.message}</p>}
    <div className={s.toolbar}><span className={s.recipeMode}>{pipeline ? `분석 절차 · ${steps.length}단계` : `탐색에 사용할 분석 · ${steps.length}개`}</span>{steps.length > 0 && <button disabled={!recipe.semantic_scope.primary_metric} onClick={() => { setAdding(true); setSearch(""); }}><Plus size={16} />{pipeline ? "분석 단계 추가" : "허용할 방법 추가"}</button>}</div>
    <div className={s.workspace}>
      <section className={s.canvas} aria-label="Recipe 그래프"><ReactFlow nodes={nodes} edges={steps.map((_, i) => ({ id: `edge:${i}`, source: pipeline && i > 0 ? `step:${i - 1}` : "scope", target: `step:${i}`, label: pipeline ? "다음 단계" : "허용", style: { stroke: "#8fa5a9", strokeWidth: 2 } }))} nodeTypes={nodeTypes} onNodesChange={changes => setPositions(applyNodeChanges(changes, nodes))} onNodeClick={(_, node) => { setSelected(node.id === "scope" ? -1 : Number(node.id.split(":")[1])); setAdding(false); }} nodesConnectable={false} deleteKeyCode={null} fitView minZoom={.25} maxZoom={1.1}><FitRecipe count={steps.length} /><Background color="#ced5d8" gap={20} /><Controls showInteractive={false} /></ReactFlow>
        {!steps.length && <div className={s.canvasEmpty}>{recipe.semantic_scope.primary_metric ? <button onClick={() => setAdding(true)}><Plus size={16} />첫 분석 추가</button> : <button onClick={() => metricSelect.current?.focus()}>지표 선택 <ArrowRight size={16} /></button>}</div>}
      </section>
      <aside ref={inspector} className={s.inspector}>
        {adding ? <><h2>분석 방법 선택</h2><label className={s.search}><Search size={16} /><input aria-label="분석 방법 검색" value={search} placeholder="추이, 항목별, 조건 맞춤" onChange={e => setSearch(e.target.value)} /></label><div className={s.choices}>{(methods || []).filter(m => (pipeline || !recipe.allowed_methods.includes(m.name)) && `${methodName(m.name)} ${m.name} ${m.description}`.toLowerCase().includes(search.toLowerCase())).map(m => <button key={m.name} onClick={() => add(m.name)}><span>{methodName(m.name)}</span><Plus size={16} /><small>{m.description}</small></button>)}</div><button className={s.secondary} onClick={() => setAdding(false)}>취소</button></> : !active ? <div className={s.fields}>
          <h2>분석 절차 정보</h2><label>어떤 분석인가요?<textarea rows={2} value={recipe.description} placeholder="예: 지급액 변화를 확인하고 지급 항목별로 살펴보기" onChange={e => change({ ...recipe, description: e.target.value })} /></label>
          <RefField label="분석할 지표" selectRef={metricSelect} value={recipe.semantic_scope.primary_metric} objects={objects.filter(o => o.kind === "measure")} fieldPath="semantic_scope.primary_metric" error={fieldError?.field === "semantic_scope.primary_metric" ? fieldError.message : undefined} onChange={v => change({ ...recipe, name: recipe.name || newName(String(v)), semantic_scope: { ...recipe.semantic_scope, primary_metric: String(v) } })} />
          <details ref={recipeAdvanced} className={s.advanced}><summary>고급 설정</summary><div className={s.fields}>
            <label data-recipe-field="name">Recipe ID<input aria-invalid={fieldError?.field === "name"} value={recipe.name} disabled={!!saved} onChange={e => change({ ...recipe, name: e.target.value })} />{fieldError?.field === "name" && <small className={s.fieldError} role="alert">{fieldError.message}</small>}</label>
            <RefField label="먼저 살펴볼 항목 (선택)" value={recipe.semantic_scope.preferred_dimensions} multiple objects={objects.filter(o => o.kind === "dimension")} onChange={v => change({ ...recipe, semantic_scope: { ...recipe.semantic_scope, preferred_dimensions: refs(v) } })} />
            <RefField label="함께 볼 지표" value={recipe.semantic_scope.related_metrics} multiple objects={objects.filter(o => o.kind === "measure")} onChange={v => change({ ...recipe, semantic_scope: { ...recipe.semantic_scope, related_metrics: refs(v) } })} />
            <span className={s.nodeStatus}>{pipeline ? "등록된 순서로 실행" : "실행 중 다음 분석 선택 · MCP"}</span>
            {methods && <MethodPolicyEditor recipe={recipe} methods={methods} onChange={change} />}
            <label>최대 단계<input type="number" min={1} value={recipe.limits.max_steps} onChange={e => change({ ...recipe, limits: { ...recipe.limits, max_steps: Number(e.target.value) } })} /></label><label>최대 쿼리<input type="number" min={1} value={recipe.limits.max_queries} onChange={e => change({ ...recipe, limits: { ...recipe.limits, max_queries: Number(e.target.value) } })} /></label>
          </div></details>
          <details className={s.advanced} open={yamlOpen} onToggle={event => setYamlOpen(event.currentTarget.open)}><summary>YAML 편집</summary><div className={s.fields}>
            <label>Recipe YAML<textarea aria-label="Recipe YAML" rows={18} spellCheck={false} value={yamlText} onChange={event => { setYamlText(event.target.value); setYamlDirty(true); setYamlError(""); }} /></label>
            {yamlDirty && <span className={s.nodeStatus}>YAML 변경 사항을 그래프에 적용해야 저장됩니다.</span>}
            {yamlError && <p className={s.error} role="alert">{yamlError}</p>}
            <div className={s.actions}><button type="button" disabled={!yamlDirty || yamlBusy} onClick={applyYaml}><Check size={14} />{yamlBusy ? "검증 중…" : "YAML 적용"}</button><button type="button" className={s.secondary} disabled={yamlBusy} onClick={() => { setYamlDirty(false); setYamlError(""); }}>그래프에서 다시 불러오기</button></div>
          </div></details>
        </div> : <div className={s.fields}>
          <button type="button" className={s.inspectorBack} onClick={() => { setSelected(-1); setAdding(false); }}><ArrowLeft size={14} />분석 절차 정보</button>
          <div className={s.inspectorHeading}><span className={s.eyebrow}>{pipeline ? `STEP ${selected + 1}` : "ALLOWED METHOD"}</span><div className={s.actions}>
            {pipeline && <><button className={s.icon} disabled={selected === 0} title="이전 순서로" aria-label="이전 순서로" onClick={() => { const next = [...recipe.steps]; [next[selected - 1], next[selected]] = [next[selected], next[selected - 1]]; if (updateSteps(next)) setSelected(selected - 1); }}><ArrowUp size={16} /></button><button className={s.icon} disabled={selected === steps.length - 1} title="다음 순서로" aria-label="다음 순서로" onClick={() => { const next = [...recipe.steps]; [next[selected + 1], next[selected]] = [next[selected], next[selected + 1]]; if (updateSteps(next)) setSelected(selected + 1); }}><ArrowDown size={16} /></button></>}
            <button className={s.icon} title="단계 삭제" aria-label="단계 삭제" onClick={() => pipeline ? updateSteps(recipe.steps.filter((_, i) => i !== selected)) : change({ ...recipe, allowed_methods: recipe.allowed_methods.filter((_, i) => i !== selected) })}><Trash2 size={16} /></button>
          </div></div>
          <h2>{methodName(active.method)}</h2><span className={s.nodeStatus}>{active.method}</span>
          {pipeline && <section className={s.previewSection} aria-label="단계 미리보기"><h3>단계 미리보기</h3>
            {timeOptions.length > 0 && <label>날짜 기준<select aria-label="미리보기 날짜 기준" value={selectedTime} onChange={event => setPreviewTimeDimension(event.target.value)}><option value="">선택하세요</option>{timeOptions.map(object => <option value={object.ref} key={object.ref}>{object.title}</option>)}</select></label>}
            {timeOptions.length > 0 && <div className={s.previewDates}><label>시작일<input type="date" aria-label="미리보기 시작일" value={previewRange[0]} onChange={event => setPreviewRange([event.target.value, previewRange[1]])} /></label><label>종료일<input type="date" aria-label="미리보기 종료일" value={previewRange[1]} onChange={event => setPreviewRange([previewRange[0], event.target.value])} /></label></div>}
            {previewDatesInvalid && <p className={s.error} role="alert">시작일과 종료일을 확인해 주세요.</p>}
            {previewNeedsTime && !selectedTime && <p className={s.nodeStatus}>미리보기에 사용할 날짜 기준을 선택해 주세요.</p>}
            <button type="button" disabled={previewBusy || !recipe.semantic_scope.primary_metric || previewDatesInvalid || (previewNeedsTime && !selectedTime)} onClick={startPreview}><Play size={15} />{previewBusy ? "시작 중…" : "이 단계까지 미리보기"}</button>
            {previewError && <p className={s.error} role="alert">{previewError} <Link href="/sources">연결 확인</Link></p>}
          </section>}
          {pipeline && methods?.find(method => method.name === active.method) ? <StepSettings key={`${selected}-${active.method}`} step={active} manifest={methods.find(method => method.name === active.method)!} objects={objects} recipe={recipe} stepIndex={selected} fieldError={fieldError} onChange={step => change({ ...recipe, steps: recipe.steps.map((s, i) => i === selected ? step : s) })} /> : !pipeline ? <p className={s.dependency}>MCP에서 이 Recipe를 선택하면 실행 결과에 따라 다음 분석과 입력을 정합니다.</p> : <p role="status">분석 설정을 불러오는 중…</p>}
        </div>}
      </aside>
    </div>
    {previewIndex === selected && previewRun && <section ref={previewOutput} className={s.previewOutput} aria-label="미리보기 결과" aria-live="polite">
      <div className={s.previewOutputHeading}><div><span className={s.eyebrow}>STEP {selected + 1}</span><h2>미리보기 결과</h2></div><Link href={`/runs/${previewRun.id}`}>실행 근거 보기 <ArrowRight size={14} /></Link></div>
      {previewRun.running && <p role="status">{previewRun.steps.length}/{selected + 1}단계 실행 중 · {previewElapsed}초</p>}
      {previewRun.error && <p className={s.error} role="alert">{previewRun.error.message}</p>}
      {stoppedPreviewStep !== null && <div className={s.previewStopped}><span>{stoppedPreviewStep + 1}단계에서 미리보기가 멈췄습니다.</span><button type="button" className={s.secondary} onClick={() => { setSelected(stoppedPreviewStep); inspector.current?.scrollTo({ top: 0, behavior: "smooth" }); }}>{stoppedPreviewStep + 1}단계 설정 확인 <ArrowRight size={14} /></button></div>}
      {!previewRun.running && <><ValidationList items={previewRun.validation} />{previewRun.steps.at(-1) && <ResultView result={previewRun.steps.at(-1)!.result} titles={byRef} />}</>}
    </section>}
    {dialog && <div className={s.overlay}><section className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="recipe-dialog-title"><div className={s.inspectorHeading}><h2 id="recipe-dialog-title">초안 저장</h2><button className={s.icon} disabled={busy} aria-label="닫기" onClick={() => setDialog(false)}><X size={18} /></button></div>
      <p>{recipe.description || recipe.name} · v{nextVersion} · {steps.length}단계</p><h3>변경 내용</h3><ul className={s.changeList}>{recipeChanges(saved, recipe, title).map((item, index) => <li key={`${index}:${item}`}>{item}</li>)}</ul><button className={s.run} disabled={busy || !recipe.name || !recipe.semantic_scope.primary_metric || !steps.length} onClick={save}><Save size={16} />{busy ? "저장 중…" : "초안 버전 저장"}</button>
      {error && <p className={s.error} role="alert">{error}</p>}
    </section></div>}
    {publishDialog && <div className={s.overlay}><section className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="publish-dialog-title"><div className={s.inspectorHeading}><h2 id="publish-dialog-title">분석 절차 발행</h2><button className={s.icon} disabled={busy} aria-label="닫기" onClick={() => setPublishDialog(false)}><X size={18} /></button></div>
      <p>{recipe.description || recipe.name} · 초안 v{saved?.version} · {steps.length}단계</p><p>발행하면 새 버전이 분석 라이브러리와 MCP에 표시되고 실행할 수 있습니다. 현재 초안은 그대로 보관됩니다.</p>
      <ul className={s.changeList}><li>분석 지표 · {title(recipe.semantic_scope.primary_metric)}</li>{steps.map((step, index) => <li key={step.id || index}>{index + 1}단계 · {methodName(step.method)}</li>)}</ul>
      <button className={s.run} disabled={busy} onClick={publish}><Check size={16} />{busy ? "검증 중…" : "검증하고 발행"}</button>{error && <p className={s.error} role="alert">{error}</p>}
    </section></div>}
  </div>;
}
