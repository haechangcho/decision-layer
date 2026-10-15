"use client";

import { useEffect, useRef, useState, type Ref } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Background, Controls, Handle, Position, ReactFlow, applyNodeChanges, useNodesInitialized, useReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { ArrowLeft, ArrowRight, ArrowDown, ArrowUp, Check, Code2, GitBranch, Play, Plus, Save, Search, Trash2, Undo2, Workflow, X } from "lucide-react";
import "@xyflow/react/dist/style.css";
import { api, ApiError, type MethodManifest, type ParamSpec, type PlanStep, type Recipe, type RecipeCandidate, type RoleSpec, type Run, type SemanticObject, type SourceReadiness } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import { type Translate, useT } from "@/lib/i18n";
import { methodName } from "@/lib/method-name";
import { ResultView, ValidationList } from "@/components/result";
import { recipeChanges } from "@/lib/recipe-changes";
import { RecipeDelete } from "./recipe-delete";
import { declaredPath, selectionLabel, sourceLabel } from "@/features/recipes/step-input-source";
import { RecipeRuntimeInputs } from "./recipe-runtime-inputs";
import { RunPeriodInput } from "@/features/runs/run-period-input";
import { ParamInput } from "@/components/forms";
import { GroupInput } from "@/components/group-input";
import groupsStyle from "@/components/group-input.module.css";
import { suggestedDateRange, suggestedTimeDimension } from "@/lib/semantic-dates";
import s from "@/components/analysis-canvas.module.css";

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
const explainError = (error: unknown, t: Translate) => {
  if (error instanceof ApiError && error.details && typeof error.details === "object" && "field" in error.details) {
    const field = (error.details as { field?: unknown }).field;
    if (typeof field === "string") return `${field}: ${error.message}`;
  }
  return error instanceof Error ? error.message : t("Could not save the Recipe.");
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
    <Handle type="source" id="selection-out" position={Position.Right} />
    <Handle type="target" id="selection-in" position={Position.Right} />
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
  const t = useT();
  const list = refs(value);
  const expression = typeof value === "string" && value.startsWith("$") ? value : null;
  return <div className={s.refField} data-recipe-field={fieldPath}><span>{label}</span>{expression ? <div className={s.inherited}><span>{inherited || expression}</span><button type="button" className={s.secondary} onClick={() => onChange(multiple ? [] : "")}>{t("Choose directly")}</button></div> : multiple ? <>
    {list.map((ref, i) => <div className={s.refRow} key={`${ref}-${i}`}><span>{objects.find(o => o.ref === ref)?.title || ref}</span><button type="button" className={s.icon} title={t("Remove {label}", { label })} aria-label={t("Remove {label} {number}", { label, number: i + 1 })} onClick={() => onChange(list.filter((_, j) => i !== j))}><X size={14} /></button></div>)}
    <select aria-label={label} aria-invalid={!!error} value="" onChange={e => e.target.value && onChange([...list, e.target.value])}><option value="">{t("Choose to add")}</option>{objects.filter(o => !list.includes(o.ref)).map(o => <option key={o.ref} value={o.ref}>{o.title}</option>)}</select>
  </> : <select ref={selectRef} aria-label={label} aria-invalid={!!error} value={list[0] || ""} onChange={e => onChange(e.target.value)}><option value="">{t("Choose…")}</option>{list[0] && !objects.some(o => o.ref === list[0]) && <option value={list[0]}>{t("Name needs checking in the catalog")}</option>}{objects.map(o => <option key={o.ref} value={o.ref}>{o.title}</option>)}</select>}{error && <small className={s.fieldError} role="alert">{error}</small>}</div>;
}

function roleObjects(role: RoleSpec, objects: SemanticObject[]) {
  if (role.accepted_kinds) return objects.filter(object => role.accepted_kinds!.includes(object.kind));
  if (role.kind === "measure") return objects.filter((object) => object.kind === "measure" && (!role.metric_kinds || role.metric_kinds.includes(object.metric_kind ?? "")));
  if (role.kind === "dimension") return objects.filter((object) => object.kind === "dimension" || object.kind === "time_dimension");
  if (role.kind === "time_dimension") return objects.filter((object) => object.kind === "time_dimension");
  if (role.kind === "entity") return objects.filter(object => object.kind === "dimension" && objects.some(member => member.entity === object.ref));
  return objects.filter((object) => !!object.entity);
}

const roleLabels: Record<string, string> = {
  metric: "Analysis metric", related: "Related metrics", dimensions: "Breakdown order", conditions: "Comparison conditions",
  treatment: "Comparison subject", treatment_measure: "Comparison basis metric", entity: "Analysis unit",
};
const roleLabel = (name: string, role: RoleSpec, t: Translate) => role.label || (roleLabels[name] ? t(roleLabels[name]) : name);
const parameterLabels: Record<string, string> = { subject: "Comparison subject", peers: "Peer group conditions", drill_path: "Analysis scope", granularity: "Time unit", vs_previous: "Compare with the previous period of equal length", top_n: "Groups to show", min_count: "Minimum group count", rank_by: "Ranked by" };
const parameterLabel = (name: string, t: Translate) => parameterLabels[name] ? t(parameterLabels[name]) : name;

function ParameterField({ name, spec, value, onChange, disabled = false, error, fieldPath, objects = [], dataType, oppositeValue }: { name: string; spec: ParamSpec; value: unknown; onChange: (value: unknown) => void; disabled?: boolean; error?: string; fieldPath?: string; objects?: SemanticObject[]; dataType?: string; oppositeValue?: unknown }) {
  const t = useT();
  const label = spec.label || parameterLabel(name, t);
  const current = value ?? spec.default;
  const source = sourceLabel(current, t);
  if (source) return <p>{source}</p>;
  if (typeof current === "string" && current.startsWith("$")) return <div className={s.refField}><span>{label}</span><code className={s.expression}>{current}</code></div>;
  if (spec.type === "group") return <fieldset className={s.fields} disabled={disabled} data-recipe-field={fieldPath}><GroupInput label={label} spec={spec} value={current} dataType={dataType} oppositeValue={oppositeValue} onChange={onChange} />{error && <small className={s.fieldError} role="alert">{error}</small>}</fieldset>;
  if (spec.type === "drill_path") {
    const items = Array.isArray(current) ? current as { member: string; value: unknown }[] : [];
    const change = (index: number, patch: Record<string, unknown>) => onChange(items.map((item, i) => i === index ? { ...item, ...patch } : item));
    return <fieldset disabled={disabled} data-recipe-field={fieldPath}><legend>{label}</legend>
      {items.map((item, index) => <div key={index} className={s.refField}>
        <select aria-label={t(name === "subject" ? "Subject dimension {number}" : "Peer dimension {number}", { number: index + 1 })} value={item.member} onChange={event => change(index, { member: event.target.value, value: "" })}><option value="">{t("Choose a dimension")}</option>{objects.filter(object => object.kind === "dimension").map(object => <option key={object.ref} value={object.ref}>{object.title}</option>)}</select>
        <input aria-label={t(name === "subject" ? "Subject value {number}" : "Peer value {number}", { number: index + 1 })} placeholder={t("Enter a value")} value={String(item.value ?? "")} onChange={event => change(index, { value: objects.find(object => object.ref === item.member)?.data_type === "number" && event.target.value !== "" ? Number(event.target.value) : event.target.value })} />
        <button type="button" className={s.secondary} onClick={() => onChange(items.filter((_, i) => i !== index))}><X size={13} />{t("Delete")}</button>
      </div>)}
      {(spec.meaning !== "comparison_subject" || !items.length) && <button type="button" className={s.secondary} onClick={() => onChange([...items, { member: "", value: "" }])}><Plus size={13} />{t("Add condition")}</button>}
      {error && <small className={s.fieldError} role="alert">{error}</small>}
    </fieldset>;
  }
  const options: Record<string, string> = { day: "Daily", week: "Weekly", month: "Monthly", quarter: "Quarterly", value: "Metric value", vs_rest: "Difference from the other groups", count: "Count", desc: "Highest values first", asc: "Lowest values first" };
  if (typeof current === "string" && current.startsWith("$")) return <div className={s.refField}><span>{label}</span><code className={s.expression}>{current}</code></div>;
  if (spec.type === "boolean") return <label className={s.check} data-recipe-field={fieldPath}><input type="checkbox" aria-invalid={!!error} disabled={disabled} checked={!!current} onChange={event => onChange(event.target.checked)} />{label}{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  if (spec.type === "enum") return <label data-recipe-field={fieldPath}>{label}<select aria-label={label} aria-invalid={!!error} disabled={disabled} value={String(current ?? "")} onChange={event => onChange(event.target.value)}>{(spec.enum || []).map(option => <option value={option} key={option}>{options[option] ? t(options[option]) : option}</option>)}</select>{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  if (spec.type === "integer" || spec.type === "number") return <label data-recipe-field={fieldPath}>{label}<input type="number" aria-invalid={!!error} disabled={disabled} step={spec.type === "integer" ? 1 : "any"} min={spec.minimum ?? undefined} max={spec.maximum ?? undefined} value={current == null ? "" : Number(current)} onChange={event => onChange(event.target.value === "" ? null : Number(event.target.value))} /><small>{spec.description}</small>{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  if (spec.semantic_kind) return <fieldset disabled={disabled}><RefField label={label} value={current} objects={objects.filter(object => object.kind === spec.semantic_kind || spec.semantic_kind === "dimension" && object.kind === "time_dimension")} multiple={spec.type === "ref_list"} onChange={onChange} error={error} fieldPath={fieldPath} /></fieldset>;
  if (spec.type === "string") return <label data-recipe-field={fieldPath}>{label}<input aria-invalid={!!error} disabled={disabled} value={String(current ?? "")} onChange={event => onChange(event.target.value)} /><small>{spec.description}</small>{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  return <fieldset disabled={disabled} data-recipe-field={fieldPath}><ParamInput name={label} spec={spec} value={current} onChange={onChange} />{error && <small className={s.fieldError} role="alert">{error}</small>}</fieldset>;
}

function StepSettings({ step, manifest, onChange, objects, recipe, stepIndex, fieldError, methods }: { step: PlanStep; manifest: MethodManifest; onChange: (s: PlanStep) => void; objects: SemanticObject[]; recipe: Recipe; stepIndex: number; fieldError: FieldError | null; methods: MethodManifest[] }) {
  const t = useT();
  const [editingMetric, setEditingMetric] = useState(false);
  const bind = (key: string, value: unknown) => onChange({ ...step, bindings: { ...step.bindings, [key]: value } });
  const param = (key: string, value: unknown) => onChange({ ...step, params: { ...step.params, [key]: value } });
  const policy = recipe.method_parameters?.[step.method];
  const fixed = (name: string) => Object.hasOwn(policy?.fixed ?? {}, name);
  const parameterValue = (name: string) => fixed(name) ? policy!.fixed[name] : step.params[name];
  const visible = (spec: ParamSpec) => !spec.visible_when || (parameterValue(spec.visible_when.parameter) ?? manifest.parameters[spec.visible_when.parameter]?.default) === spec.visible_when.equals;
  const basicParameters = Object.entries(manifest.parameters).filter(([, spec]) => visible(spec) && (spec.ui_group === "basic" || spec.required && spec.ui_group !== "hidden") && spec.meaning !== "analysis_scope");
  const describeSource = (value: unknown, spec: ParamSpec) => {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const ref = value as { source?: string; step_id?: string; project?: string; name?: string };
      if (ref.source === "step") {
        const index = recipe.steps.findIndex(item => item.id === ref.step_id);
        if (index >= 0) {
          const upstream = recipe.steps[index];
          const resolved = { ...upstream, bindings: { ...upstream.bindings, metric: upstream.bindings.metric === "$scope.primary_metric" ? recipe.semantic_scope.primary_metric : upstream.bindings.metric } };
          return t("From step {number}: {selection} · selected again on every run", { number: index + 1, selection: selectionLabel(resolved, ref.project || "path", methods, t, { titles: new Map(objects.map(object => [object.ref, object])), steps: recipe.steps.map(item => ({ ...item, bindings: { ...item.bindings, dimensions: item.bindings.dimensions === "$scope.preferred_dimensions" ? recipe.semantic_scope.preferred_dimensions : item.bindings.dimensions } })) }) });
        }
      }
      if (ref.source === "input") return `${t("Choose at run time")} · ${recipe.inputs?.[ref.name || ""]?.label || spec.label || t("Analysis subject")}`;
    }
    if (Array.isArray(value) && value.length) return value.map(item => `${objects.find(object => object.ref === item.member)?.title || t("item")}: ${String(item.value)}`).join(" · ");
    return t(spec.meaning === "comparison_population" ? "Compare with the other subjects in the whole analysis scope" : "Whole analysis scope");
  };
  const metricBinding = step.bindings.metric;
  const usesRecipeMetric = metricBinding === "$scope.primary_metric";
  const metricRef = usesRecipeMetric ? recipe.semantic_scope.primary_metric : metricBinding;
  const metricTitle = typeof metricRef === "string" ? objects.find(o => o.ref === metricRef)?.title || metricRef || t("No metric set") : t("No metric set");
  const metricObject = objects.find(object => object.ref === metricRef);
  const countRoles = Object.entries(manifest.roles).filter(([, role]) => role.default_binding === "unit_count");
  const [countBusy, setCountBusy] = useState(false);
  const [countError, setCountError] = useState("");
  const [countRetry, setCountRetry] = useState(0);
  const latestStep = useRef(step); latestStep.current = step;
  const latestChange = useRef(onChange); latestChange.current = onChange;
  const missingCount = metricObject?.metric_kind === "average" && countRoles.some(([key]) => !step.bindings[key]);
  useEffect(() => {
    if (!missingCount) { setCountBusy(false); return; }
    let cancelled = false;
    setCountBusy(true); setCountError("");
    api<Recipe>("/recipes:configure-step", { body: { recipe, step_index: stepIndex } }).then(configured => {
      if (cancelled) return;
      const bindings = { ...latestStep.current.bindings };
      let changed = false;
      for (const [key] of countRoles) if (!bindings[key] && configured.steps[stepIndex].bindings[key]) { bindings[key] = configured.steps[stepIndex].bindings[key]; changed = true; }
      if (changed) latestChange.current({ ...latestStep.current, bindings });
    }).catch(error => { if (!cancelled) setCountError(explainError(error, t)); }).finally(() => { if (!cancelled) setCountBusy(false); });
    return () => { cancelled = true; };
  }, [metricRef, missingCount, manifest.name, stepIndex, countRetry]);
  const roleAlternatives = (name: string) => {
    const group = manifest.roles[name]?.exclusive_group;
    return Object.entries(manifest.roles).filter(([key, role]) => group ? role.exclusive_group === group : key === name);
  };
  const parameterField = ([name, spec]: [string, ParamSpec]) => {
    const path = `steps[${stepIndex}].params.${name}`;
    const value = parameterValue(name);
    const boundRole = spec.semantic_role ? roleAlternatives(spec.semantic_role).find(([key]) => step.bindings[key])?.[0] : undefined;
    const reference = boundRole ? step.bindings[boundRole] : undefined;
    const subject = Object.entries(manifest.parameters).find(([, item]) => item.type === "group" && item.semantic_role === spec.semantic_role && item.meaning === "comparison_subject");
    return <ParameterField key={`${name}:${reference}`} objects={objects} name={name} spec={spec} value={value} disabled={fixed(name)} fieldPath={path} dataType={objects.find(object => object.ref === reference)?.data_type} oppositeValue={subject ? parameterValue(subject[0]) : undefined} error={fieldError?.field === path ? fieldError.message : undefined} onChange={value => param(name, value)} />;
  };
  const roleField = ([name, role]: [string, RoleSpec]) => {
    const inherited = name === "metric" ? objects.find(o => o.ref === recipe.semantic_scope.primary_metric)?.title || t("Not selected")
      : name === "dimensions" ? recipe.semantic_scope.preferred_dimensions.map(ref => objects.find(o => o.ref === ref)?.title || ref).join(" → ") || t("Not selected") : undefined;
    const path = `steps[${stepIndex}].bindings.${name}`;
    if (role.default_binding === "unit_count") {
      if (metricObject?.metric_kind !== "average") return step.bindings[name] ? <div key={name} className={groupsStyle.countIssue}><p>{t("The previous count link cannot be used with the changed metric.")}</p><button type="button" className={s.secondary} onClick={() => { const bindings = { ...step.bindings }; delete bindings[name]; onChange({ ...step, bindings }); }}>{t("Remove previous count link")}</button></div> : null;
      const current = objects.find(object => object.ref === step.bindings[name]);
      if (current && metricObject.entity && current.count_measure === current.ref && current.entity === metricObject.entity && current.metric_kind === "count") return null;
      const candidates = roleObjects(role, objects).filter(object => !!metricObject.entity && object.entity === metricObject.entity && object.count_measure === object.ref);
      return <div key={name} className={groupsStyle.countIssue}>
        <p>{t(countBusy ? "Checking the analysis unit to compare…" : "Comparing averages requires the count for the same analysis unit. It could not be found automatically, so link it.")}</p>
        {countError && <><p role="alert">{countError}</p><button type="button" className={s.secondary} onClick={() => setCountRetry(value => value + 1)}>{t("Check again")}</button></>}
        {!countBusy && (candidates.length ? <RefField label={t("Count for the analysis unit")} value={step.bindings[name]} objects={candidates} onChange={next => { const bindings = { ...step.bindings }; if (next) bindings[name] = next; else delete bindings[name]; onChange({ ...step, bindings }); }} fieldPath={path} error={fieldError?.field === path ? fieldError.message : undefined} /> : <p>{t("The connected semantic layer must provide a row count at the same unit as the base analysis unit. Check with the model owner.")} <Link href="/sources">{t("Check connection status")}</Link></p>)}
      </div>;
    }
    if (role.exclusive_group) {
      const alternatives = roleAlternatives(name);
      if (alternatives[0][0] !== name) return null;
      const keys = alternatives.map(([key]) => key);
      const value = alternatives.map(([key]) => step.bindings[key]).find(Boolean);
      const parameters = basicParameters.filter(([, spec]) => spec.semantic_role && keys.includes(spec.semantic_role));
      const candidates = objects.filter(object => alternatives.some(([, alternative]) => roleObjects(alternative, [object]).length));
      return <div key={name} className={s.fields}>
        <h3 className={groupsStyle.heading}>{t("Two groups to compare")}</h3>
        <fieldset className={s.fields} disabled={parameters.some(([key]) => fixed(key))}><RefField label={roleLabel(name, role, t)} value={value} objects={candidates} fieldPath={path} error={fieldError && keys.some(key => fieldError.field === `steps[${stepIndex}].bindings.${key}`) ? fieldError.message : undefined} onChange={next => {
          const bindings = { ...step.bindings }; keys.forEach(key => delete bindings[key]);
          const chosen = objects.find(object => object.ref === next);
          const selectedRole = alternatives.find(([, alternative]) => chosen && roleObjects(alternative, [chosen]).length);
          if (selectedRole) bindings[selectedRole[0]] = next;
          const params = { ...step.params }; parameters.forEach(([key]) => { if (!fixed(key)) delete params[key]; });
          onChange({ ...step, bindings, params });
        }} /></fieldset>
        {!!value && <div className={`${groupsStyle.pair} ${s.comparisonPair}`}>{parameters.map(parameterField)}</div>}
      </div>;
    }
    const selector = Object.entries(manifest.parameters).find(([parameter, spec]) => role.editor_parameter === parameter && spec.type === "string" && spec.semantic_role === name && spec.semantic_kind === role.kind);
    if (selector) {
      const [parameter] = selector;
      const resolvedSteps: PlanStep[] = recipe.steps.map(item => ({ ...item, bindings: { ...item.bindings, dimensions: item.bindings.dimensions === "$scope.preferred_dimensions" ? recipe.semantic_scope.preferred_dimensions : item.bindings.dimensions } }));
      const resolved = resolvedSteps[stepIndex];
      const value = parameterValue(parameter) ?? declaredPath(resolved, resolvedSteps).at(-1);
      const candidates = roleObjects(role, objects);
      const parameterPath = `steps[${stepIndex}].params.${parameter}`;
      return <fieldset key={name} disabled={fixed(parameter)}><RefField label={roleLabel(name, role, t)} value={value} objects={candidates} fieldPath={path} error={fieldError?.field === path || fieldError?.field === parameterPath ? fieldError.message : undefined} onChange={next => {
        if (!next) {
          const params = { ...step.params }; delete params[parameter];
          onChange({ ...step, bindings: { ...step.bindings, [name]: [] }, params });
          return;
        }
        const dimensions = refs(resolved.bindings[name]);
        onChange({ ...step, bindings: { ...step.bindings, [name]: dimensions.includes(String(next)) ? dimensions : [...dimensions, String(next)] }, params: { ...step.params, [parameter]: next } });
      }} /></fieldset>;
    }
    return <RefField key={name} label={roleLabel(name, role, t)} value={step.bindings[name]} objects={roleObjects(role, objects)} multiple={role.multiple} inherited={inherited} fieldPath={path} error={fieldError?.field === path ? fieldError.message : undefined} onChange={next => bind(name, next)} />;
  };
  const context = Object.entries(manifest.parameters).filter(([, spec]) => spec.meaning === "analysis_scope").map(([name, spec]) => {
    const value = parameterValue(name);
    return sourceLabel(value, t) || Array.isArray(value) && value.length ? describeSource(value, spec) : null;
  }).filter(Boolean);
  return <>
    {manifest.roles.metric && <div><p className={s.nodeStatus}>{t(Object.values(manifest.roles).some(role => role.exclusive_group) ? "Metric to compare" : "Analysis metric")}</p><div className={s.inherited}><strong>{metricTitle}</strong><button type="button" className={s.secondary} onClick={() => setEditingMetric(!editingMetric)}>{t(editingMetric ? "Done" : "Change metric")}</button></div></div>}
    {editingMetric && manifest.roles.metric && <>
      <RefField label={t("Metric for this step")} value={metricBinding} objects={roleObjects(manifest.roles.metric, objects)} inherited={metricTitle} fieldPath={`steps[${stepIndex}].bindings.metric`} error={fieldError?.field === `steps[${stepIndex}].bindings.metric` ? fieldError.message : undefined} onChange={next => bind("metric", next)} />
      {!usesRecipeMetric && <button type="button" className={s.secondary} onClick={() => { bind("metric", "$scope.primary_metric"); setEditingMetric(false); }}><Undo2 size={13} />{t("Use the Recipe metric")}</button>}
    </>}
    {context.map((text, index) => <p key={index} className={s.nodeStatus}>{text}</p>)}
    {policy && <p className={s.nodeStatus}>{t("The run constraints set for this procedure are kept. Change them in the code view.")}</p>}
    {Object.entries(manifest.roles).filter(([name, role]) => name !== "metric" && (role.required || role.exclusive_group || step.bindings[name] || role.default_binding === "unit_count" && metricObject?.metric_kind === "average")).map(roleField)}
    {basicParameters.filter(([, spec]) => !spec.semantic_role || !manifest.roles[spec.semantic_role]?.exclusive_group).map(([name, spec]) => {
      const path = `steps[${stepIndex}].params.${name}`;
      const value = parameterValue(name);
      return spec.type === "drill_path" && sourceLabel(value, t) ? <div className={s.refField} key={name}><strong>{spec.label || parameterLabel(name, t)}</strong><span className={s.nodeStatus}>{describeSource(value, spec)}</span></div>
        : parameterField([name, spec]);
    })}
    <label>{t(step.purpose_context === "source_run" ? "Step description from the original analysis (edit it for reuse)" : "What to check in this step")}<textarea rows={2} maxLength={240} value={step.purpose ?? ""} onChange={event => onChange({ ...step, purpose: event.target.value || null, purpose_context: "procedure" })} /></label>
  </>;
}


export function RecipeEditor({ initial }: { initial?: Recipe }) {
  const t = useT();
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
  const activeManifest = methods?.find(method => method.name === active?.method);
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
    if (initial) return;
    const params = new URLSearchParams(window.location.search);
    const sourceRun = params.get("from_run");
    if (sourceRun) {
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
    <header className={s.header}><div><Link className={s.back} href="/recipes"><ArrowLeft size={14} />{t("Recipes")}</Link><h1>{t(saved ? "Edit analysis procedure" : "New analysis procedure")}</h1><span className={s.nodeStatus}>{dirty ? t("Unsaved changes") : `v${saved?.version} · ${t(saved?.status === "draft" ? "Draft" : "Published")}`}</span></div><div className={s.actions}>
      <button type="button" className={s.secondary} aria-pressed={yamlOpen} onClick={() => setYamlOpen(!yamlOpen)}><Code2 size={16} />{t(yamlOpen ? "Close code" : "View code")}</button>
      {dirty && saved && <button className={s.secondary} title={t("Revert to the saved version")} onClick={() => { setRecipe(saved); setSelected(-1); setPositions([]); setFieldError(null); }}><Undo2 size={16} />{t("Revert")}</button>}
      {dirty && steps.length > 0 && <button disabled={busy || !recipe.semantic_scope.primary_metric} onClick={() => { setError(""); setDialog(true); }}><Save size={16} />{t("Save draft")}</button>}
      {!dirty && saved?.status === "draft" && <button disabled={busy} onClick={() => { setError(""); setPublishDialog(true); }}><Check size={16} />{t("Review for publishing")}</button>}
      {!dirty && saved?.status !== "draft" && saved && <button disabled={busy} onClick={() => router.push(`/recipes/${encodeURIComponent(recipe.name)}`)}><Play size={16} />{t("Run analysis")}</button>}
      {saved && !busy && <RecipeDelete recipe={saved} onDeleted={() => { setSaved(undefined); setRecipe(blank()); router.push("/recipes"); }} />}
    </div></header>
    {(catalogError || methodsError) && <p className={s.error} role="alert">{catalogError?.message || methodsError?.message} <Link href="/sources">{t("Check connection")}</Link></p>}
    {error && !dialog && <p className={s.error} role="alert">{error}</p>}
    {!!recipe.origin_runs?.length && <div className={s.reviewNotice}><strong>{t("Analysis procedure taken from a run")}</strong><Link href={`/runs/${recipe.origin_runs[0]}`}>{t("View original run")} <ArrowRight size={14} /></Link><p>{t("{count} steps · the period is chosen at run time", { count: recipe.steps.length })}</p>{!!reviewNotes.length && <p>{t("Check the groups and periods that were set directly. To select from the data on every run, set a previous result in the step settings.")}</p>}</div>}
    {fieldError && <p className={s.error} role="alert">{t("Check before saving: {message}", { message: fieldError.message })}</p>}
    <div className={s.toolbar}><span className={s.recipeMode}>{pipeline ? `${t("Analysis procedure")} · ${t("{count} steps", { count: steps.length })}` : t("Analyses for exploration · {count}", { count: steps.length })}</span>{steps.length > 0 && <button disabled={!recipe.semantic_scope.primary_metric} onClick={() => { setAdding(true); setSearch(""); }}><Plus size={16} />{t(pipeline ? "Add analysis step" : "Add allowed Method")}</button>}</div>
    <div className={s.workspace}>
      <section className={s.canvas} aria-label={t("Recipe graph")}><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={changes => setPositions(applyNodeChanges(changes, nodes))} onNodeClick={(_, node) => { setSelected(node.id === "scope" ? -1 : Number(node.id.split(":")[1])); setAdding(false); }} nodesConnectable={false} deleteKeyCode={null} fitView minZoom={.25} maxZoom={1.1}><FitRecipe count={steps.length} /><Background color="var(--dl-border-strong)" gap={20} /><Controls showInteractive={false} /></ReactFlow>
        {!steps.length && <div className={s.canvasEmpty}>{recipe.semantic_scope.primary_metric ? <button onClick={() => setAdding(true)}><Plus size={16} />{t("Add the first analysis")}</button> : <button onClick={() => metricSelect.current?.focus()}>{t("Choose a metric")} <ArrowRight size={16} /></button>}</div>}
      </section>
      <aside ref={inspector} className={s.inspector}>
        {adding ? <><h2>{t("Choose a Method")}</h2><label className={s.search}><Search size={16} /><input aria-label={t("Search Methods")} value={search} placeholder={t("trend, by group, matched")} onChange={e => setSearch(e.target.value)} /></label><div className={s.choices}>{(methods || []).filter(m => (pipeline || !recipe.allowed_methods.includes(m.name)) && `${displayMethod(m.name)} ${m.name} ${m.description}`.toLowerCase().includes(search.toLowerCase())).map(m => <button key={m.name} onClick={() => add(m.name)}><span>{displayMethod(m.name)}</span><Plus size={16} /><small>{m.description}</small></button>)}</div><button className={s.secondary} onClick={() => setAdding(false)}>{t("Cancel")}</button></> : !active ? <div className={s.fields}>
          <h2>{t("Analysis procedure details")}</h2><label>{t("Which question is this analysis for?")}<textarea rows={2} value={recipe.routing.objective || recipe.description} placeholder={t("e.g. {example}", { example: t("check how the metric changed and find the items with the biggest impact") })} onChange={e => change({ ...recipe, description: e.target.value, routing: { ...recipe.routing, objective: e.target.value } })} /></label>
          <RefField label={t("Metric to analyze")} selectRef={metricSelect} value={recipe.semantic_scope.primary_metric} objects={objects.filter(o => o.kind === "measure")} fieldPath="semantic_scope.primary_metric" error={fieldError?.field === "semantic_scope.primary_metric" ? fieldError.message : undefined} onChange={v => change({ ...recipe, name: recipe.name || newName(String(v)), semantic_scope: { ...recipe.semantic_scope, primary_metric: String(v) } })} />
        </div> : <div className={s.fields}>
          <button type="button" className={s.inspectorBack} onClick={() => { setSelected(-1); setAdding(false); }}><ArrowLeft size={14} />{t("Analysis procedure details")}</button>
          <div className={s.inspectorHeading}><span className={s.eyebrow}>{pipeline ? `STEP ${selected + 1}` : "ALLOWED METHOD"}</span><div className={s.actions}>
            {pipeline && <><button className={s.icon} disabled={selected === 0} title={t("Move up")} aria-label={t("Move up")} onClick={() => { const next = [...recipe.steps]; [next[selected - 1], next[selected]] = [next[selected], next[selected - 1]]; if (updateSteps(next)) setSelected(selected - 1); }}><ArrowUp size={16} /></button><button className={s.icon} disabled={selected === steps.length - 1} title={t("Move down")} aria-label={t("Move down")} onClick={() => { const next = [...recipe.steps]; [next[selected + 1], next[selected]] = [next[selected], next[selected + 1]]; if (updateSteps(next)) setSelected(selected + 1); }}><ArrowDown size={16} /></button></>}
            <button className={s.icon} title={t("Delete step")} aria-label={t("Delete step")} onClick={() => pipeline ? updateSteps(recipe.steps.filter((_, i) => i !== selected)) : change({ ...recipe, allowed_methods: recipe.allowed_methods.filter((_, i) => i !== selected) })}><Trash2 size={16} /></button>
          </div></div>
          <h2>{displayMethod(active.method)}</h2>
          {pipeline && activeManifest ? <StepSettings key={`${selected}-${active.method}`} step={active} manifest={activeManifest} methods={methods ?? []} objects={objects} recipe={recipe} stepIndex={selected} fieldError={fieldError} onChange={step => change({ ...recipe, steps: recipe.steps.map((s, i) => i === selected ? step : s) })} /> : !pipeline ? <p className={s.dependency}>{t("When this Recipe is chosen from MCP, the next analysis and inputs are decided from each result.")}</p> : <p role="status">{t("Loading analysis settings…")}</p>}
          {pipeline && <section className={s.previewSection} aria-label={t("Check result")}>
            {previewFormOpen && <>
              <RecipeRuntimeInputs specs={recipe.inputs ?? {}} values={previewInputs} onChange={setPreviewInputs} objects={objects} />
              {previewWithPeriod && (timeOptions.length > 1 || !selectedTime) && <label>{t("Date dimension")}<select aria-label={t("Preview date dimension")} value={selectedTime} onChange={event => setPreviewTimeDimension(event.target.value)}><option value="">{t("Choose…")}</option>{timeOptions.map(object => <option value={object.ref} key={object.ref}>{object.title}</option>)}</select></label>}
              {previewWithPeriod && <div className={s.previewDates}><label>{t("Start date")}<input type="date" aria-label={t("Preview start date")} value={previewRange[0]} onChange={event => choosePreviewDates([event.target.value, previewRange[1]])} /></label><label>{t("End date")}<input type="date" aria-label={t("Preview end date")} value={previewRange[1]} onChange={event => choosePreviewDates([previewRange[0], event.target.value])} /></label></div>}
              {previewDatesInvalid && <p className={s.error} role="alert">{t("Check the start and end dates.")}</p>}
              {previewWithPeriod && !selectedTime && <p className={s.nodeStatus}>{t("Choose a date dimension.")}</p>}
            </>}
            {missingRoles.length > 0 && <p className={s.nodeStatus}>{t("Choose {fields}.", { fields: missingRoles.map(([name, role]) => roleLabel(name, role, t)).join(", ") })}</p>}
            <button type="button" disabled={previewBusy || !activeManifest || missingRoles.length > 0 || !recipe.semantic_scope.primary_metric || previewFormOpen && (previewDatesInvalid || previewWithPeriod && !selectedTime)} onClick={() => { if (!previewFormOpen && (previewWithPeriod || Object.keys(recipe.inputs ?? {}).length)) setPreviewFormOpen(true); else void startPreview(); }}><Play size={15} />{t(previewBusy ? "Checking…" : previewFormOpen ? "Check with these conditions" : "Check result")}</button>
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
            <div className={s.actions}><button type="button" disabled={!yamlDirty || yamlBusy} onClick={applyYaml}><Check size={14} />{t(yamlBusy ? "Validating…" : "Apply YAML")}</button><button type="button" className={s.secondary} disabled={yamlBusy} onClick={() => { setYamlDirty(false); setYamlError(""); }}>{t("Reload from the graph")}</button></div>
          </div></section>}
    {previewIndex === selected && previewRun && <section ref={previewOutput} className={s.previewOutput} aria-label={t("Preview result")} aria-live="polite">
      <div className={s.previewOutputHeading}><div><span className={s.eyebrow}>STEP {selected + 1}</span><h2>{t("Preview result")}</h2></div><Link href={`/runs/${previewRun.id}`}>{t("View execution evidence")} <ArrowRight size={14} /></Link></div>
      {previewRun.running && <p role="status">{t("Running step {done}/{total} · {seconds} s", { done: previewRun.steps.length, total: selected + 1, seconds: previewElapsed })}</p>}
      {previewRun.needs_input && <RunPeriodInput key={`${previewRun.id}:${previewRun.scope_revision}`} run={previewRun} objects={objects} onDone={setPreviewRun} />}
      {previewRun.error && <p className={s.error} role="alert">{previewRun.error.message}</p>}
      {stoppedPreviewStep !== null && <div className={s.previewStopped}><span>{t("The preview stopped at step {number}.", { number: stoppedPreviewStep + 1 })}</span><button type="button" className={s.secondary} onClick={() => { setSelected(stoppedPreviewStep); inspector.current?.scrollTo({ top: 0, behavior: "smooth" }); }}>{t("Check step {number} settings", { number: stoppedPreviewStep + 1 })} <ArrowRight size={14} /></button></div>}
      {!previewRun.running && <><ValidationList items={previewRun.validation} />{previewRun.steps.at(-1) && <ResultView result={previewRun.steps.at(-1)!.result} titles={byRef} />}</>}
    </section>}
    {dialog && <div className={s.overlay}><section className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="recipe-dialog-title"><div className={s.inspectorHeading}><h2 id="recipe-dialog-title">{t("Save draft")}</h2><button className={s.icon} disabled={busy} aria-label={t("Close")} onClick={() => setDialog(false)}><X size={18} /></button></div>
      <p>{recipe.description || recipe.name} · v{nextVersion} · {t("{count} steps", { count: steps.length })}</p><h3>{t("Changes")}</h3><ul className={s.changeList}>{recipeChanges(saved, recipe, title, t).map((item, index) => <li key={`${index}:${item}`}>{item}</li>)}</ul><button className={s.run} disabled={busy || !recipe.name || !recipe.semantic_scope.primary_metric || !steps.length} onClick={save}><Save size={16} />{t(busy ? "Saving…" : "Save draft version")}</button>
      {error && <p className={s.error} role="alert">{error}</p>}
    </section></div>}
    {publishDialog && <div className={s.overlay}><section className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="publish-dialog-title"><div className={s.inspectorHeading}><h2 id="publish-dialog-title">{t("Publish analysis procedure")}</h2><button className={s.icon} disabled={busy} aria-label={t("Close")} onClick={() => setPublishDialog(false)}><X size={18} /></button></div>
      <p>{recipe.description || recipe.name} · {t("Draft v{version}", { version: saved?.version ?? "" })} · {t("{count} steps", { count: steps.length })}</p><p>{t("Publishing shows the new version in the Recipe list and MCP so it can run. The current draft is kept.")}</p>
      <ul className={s.changeList}><li>{t("Analysis metric")} · {title(recipe.semantic_scope.primary_metric)}</li>{steps.map((step, index) => <li key={step.id || index}>{t("Step {number}", { number: index + 1 })} · {displayMethod(step.method)}</li>)}</ul>
      <button className={s.run} disabled={busy} onClick={publish}><Check size={16} />{t(busy ? "Validating…" : "Validate and publish")}</button>{error && <p className={s.error} role="alert">{error}</p>}
    </section></div>}
  </div>;
}
