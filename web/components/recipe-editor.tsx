"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Background, Controls, Handle, Position, ReactFlow, applyNodeChanges, type Node, type NodeProps } from "@xyflow/react";
import { ArrowLeft, ArrowDown, ArrowUp, Check, GitBranch, Play, Plus, Save, Search, Trash2, Undo2, Workflow, X } from "lucide-react";
import "@xyflow/react/dist/style.css";
import { api, ApiError, type MethodManifest, type ParamSpec, type PlanStep, type Recipe, type RoleSpec, type Run, type SemanticObject } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import s from "./analysis-canvas.module.css";

const names: Record<string, string> = { "query.trend": "시간에 따른 변화", "query.drilldown": "항목별로 나눠 보기", "causal.cem": "조건을 맞춰 비교" };
const methodName = (name: string) => names[name] || name;
const blank = (): Recipe => ({ name: "", version: "1.0.0", description: "", mode: "pipeline", routing: { use_for: [], do_not_use_for: [] }, semantic_scope: { primary_metric: "", related_metrics: [], preferred_dimensions: [], required_filters: [] }, steps: [], allowed_methods: [], validators: [], limits: { max_steps: 12, max_queries: 30 } });
const bump = (version: string) => version.replace(/\d+$/, n => String(Number(n) + 1));
const refs = (value: unknown): string[] => Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
const explainError = (error: unknown) => {
  if (error instanceof ApiError && error.details && typeof error.details === "object" && "field" in error.details) {
    const field = (error.details as { field?: unknown }).field;
    if (typeof field === "string") return `${field}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Recipe를 저장하지 못했습니다.";
};

function RecipeNode({ data, selected }: NodeProps) {
  return <div className={`${s.node} ${selected ? s.selected : ""}`}>
    <Handle type="target" position={Position.Top} />
    <span className={s.nodeKind}>{data.scope ? <GitBranch size={16} /> : <Workflow size={16} />}{String(data.kind)}</span>
    <strong>{String(data.label)}</strong><span className={s.nodeStatus}>{String(data.detail)}</span>
    <Handle type="source" position={Position.Bottom} />
  </div>;
}
const nodeTypes = { recipe: RecipeNode };

function RefField({ label, value, objects, multiple, onChange, inherited }: {
  label: string; value: unknown; objects: SemanticObject[]; multiple?: boolean;
  onChange: (value: string | string[]) => void; inherited?: string;
}) {
  const list = refs(value);
  const expression = typeof value === "string" && value.startsWith("$") ? value : null;
  return <div className={s.refField}><span>{label}</span>{expression ? <div className={s.inherited}><span>{inherited || expression}</span><button type="button" className={s.secondary} onClick={() => onChange(multiple ? [] : "")}>직접 선택</button></div> : multiple ? <>
    {list.map((ref, i) => <div className={s.refRow} key={`${ref}-${i}`}><span>{objects.find(o => o.ref === ref)?.title || ref}</span><button type="button" className={s.icon} title={`${label} 삭제`} aria-label={`${label} ${i + 1} 삭제`} onClick={() => onChange(list.filter((_, j) => i !== j))}><X size={14} /></button></div>)}
    <select aria-label={label} value="" onChange={e => e.target.value && onChange([...list, e.target.value])}><option value="">선택해서 추가</option>{objects.filter(o => !list.includes(o.ref)).map(o => <option key={o.ref} value={o.ref}>{o.title}</option>)}</select>
  </> : <select aria-label={label} value={list[0] || ""} onChange={e => onChange(e.target.value)}><option value="">선택하세요</option>{list[0] && !objects.some(o => o.ref === list[0]) && <option value={list[0]}>{list[0]}</option>}{objects.map(o => <option key={o.ref} value={o.ref}>{o.title}</option>)}</select>}</div>;
}

function roleObjects(role: RoleSpec, objects: SemanticObject[]) {
  if (role.kind === "measure") return objects.filter((object) => object.kind === "measure");
  if (role.kind === "dimension") return objects.filter((object) => object.kind === "dimension" || object.kind === "time_dimension");
  if (role.kind === "time_dimension") return objects.filter((object) => object.kind === "time_dimension");
  return objects.filter((object) => !!object.entity);
}

const roleLabels: Record<string, string> = {
  metric: "분석 지표", related: "함께 볼 지표", dimensions: "분류 순서", conditions: "비교 조건",
  treatment: "비교 대상", treatment_measure: "비교 기준 지표", entity: "분석 단위",
};

function ParameterField({ name, spec, value, onChange }: { name: string; spec: ParamSpec; value: unknown; onChange: (value: unknown) => void }) {
  const label = name === "granularity" ? "시간 단위" : name === "vs_previous" ? "직전 같은 길이와 비교"
    : name === "top_n" ? "표시할 그룹 수" : name === "min_count" ? "최소 그룹 건수"
      : name === "rank_by" ? "정렬 기준" : name;
  const current = value ?? spec.default;
  if (spec.type === "boolean") return <label className={s.check}><input type="checkbox" checked={!!current} onChange={event => onChange(event.target.checked)} />{label}<small>{spec.description}</small></label>;
  if (spec.type === "enum") return <label>{label}<select value={String(current ?? "")} onChange={event => onChange(event.target.value)}>{(spec.enum || []).map(option => <option value={option} key={option}>{option}</option>)}</select><small>{spec.description}</small></label>;
  if (spec.type === "integer" || spec.type === "number") return <label>{label}<input type="number" step={spec.type === "integer" ? 1 : "any"} value={current == null ? "" : Number(current)} onChange={event => onChange(event.target.value === "" ? null : Number(event.target.value))} /><small>{spec.description}</small></label>;
  if (spec.type === "string") return <label>{label}<input value={String(current ?? "")} onChange={event => onChange(event.target.value)} /><small>{spec.description}</small></label>;
  return null;
}

function StepSettings({ step, manifest, onChange, objects, recipe }: { step: PlanStep; manifest: MethodManifest; onChange: (s: PlanStep) => void; objects: SemanticObject[]; recipe: Recipe }) {
  const [json, setJson] = useState("");
  const [jsonError, setJsonError] = useState("");
  const bind = (key: string, value: unknown) => onChange({ ...step, bindings: { ...step.bindings, [key]: value } });
  const param = (key: string, value: unknown) => onChange({ ...step, params: { ...step.params, [key]: value } });
  const basicParameters = Object.entries(manifest.parameters).filter(([, spec]) => spec.ui_group === "basic");
  return <>
    {Object.entries(manifest.roles).map(([name, role]) => {
      const inherited = name === "metric" ? `공통 지표 · ${objects.find(o => o.ref === recipe.semantic_scope.primary_metric)?.title || "미선택"}`
        : name === "dimensions" ? `공통 분류 · ${recipe.semantic_scope.preferred_dimensions.map(ref => objects.find(o => o.ref === ref)?.title || ref).join(" → ")}` : undefined;
      const value = step.bindings[name] ?? (name === "metric" ? "$scope.primary_metric" : name === "dimensions" ? "$scope.preferred_dimensions" : undefined);
      return <RefField key={name} label={roleLabels[name] || name} value={value} objects={roleObjects(role, objects)} multiple={role.multiple} inherited={inherited} onChange={next => bind(name, next)} />;
    })}
    {basicParameters.map(([name, spec]) => <ParameterField key={name} name={name} spec={spec} value={step.params[name]} onChange={value => param(name, value)} />)}
    <details className={s.advanced} onToggle={e => { if (e.currentTarget.open) { setJson(JSON.stringify({ bindings: step.bindings, params: step.params }, null, 2)); setJsonError(""); } }}><summary>고급 설정</summary>
      <p className="hint">전체 Method 입력과 고급 파라미터를 JSON으로 편집합니다.</p><label>bindings / params<textarea rows={12} value={json} onChange={e => setJson(e.target.value)} /></label>
      <button type="button" className={s.secondary} onClick={() => { try { const value = JSON.parse(json); if (!value.bindings || !value.params || typeof value.bindings !== "object" || typeof value.params !== "object" || Array.isArray(value.bindings) || Array.isArray(value.params)) throw new Error("bindings와 params는 객체여야 합니다."); onChange({ ...step, bindings: value.bindings, params: value.params }); setJsonError(""); } catch (e) { setJsonError((e as Error).message); } }}>설정 적용</button>{jsonError && <p role="alert" className={s.error}>{jsonError}</p>}
    </details>
  </>;
}

export function RecipeEditor({ initial }: { initial?: Recipe }) {
  const router = useRouter();
  const { objects, byRef, error: catalogError } = useCatalog();
  const { data: methods, error: methodsError } = useApi<MethodManifest[]>("/methods");
  const [recipe, setRecipe] = useState<Recipe>(() => initial || blank());
  const [saved, setSaved] = useState<Recipe | undefined>(initial);
  const [selected, setSelected] = useState(-1);
  const [positions, setPositions] = useState<Node[]>([]);
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState<"save" | "run" | null>(null);
  const [key, setKey] = useState("");
  const [dates, setDates] = useState<[string, string]>(["", ""]);
  const dirty = !saved || JSON.stringify(recipe) !== JSON.stringify(saved);
  const pipeline = recipe.mode === "pipeline";
  const steps: PlanStep[] = pipeline ? recipe.steps : recipe.allowed_methods.map(method => ({ method, bindings: {}, params: {} }));
  const active = steps[selected];
  const title = (ref: string) => byRef.get(ref)?.title || ref;
  useEffect(() => {
    if (initial) return;
    const params = new URLSearchParams(window.location.search);
    const method = params.get("method");
    setRecipe(r => ({ ...r, semantic_scope: { ...r.semantic_scope, primary_metric: params.get("metric") || "" }, steps: method ? [{ id: "step_1", method, bindings: { metric: "$scope.primary_metric" }, params: {} }] : [] }));
    if (method) setSelected(0);
  }, [initial]);
  useEffect(() => { if (!dirty) return; const warn = (e: BeforeUnloadEvent) => e.preventDefault(); window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, [dirty]);
  function change(next: Recipe) { setRecipe(next); setError(""); }
  function add(method: string) {
    if (pipeline) {
      let id = 1; while (recipe.steps.some(step => step.id === `step_${id}`)) id++;
      change({ ...recipe, steps: [...recipe.steps, { id: `step_${id}`, method, bindings: { metric: "$scope.primary_metric" }, params: {} }] });
    } else change({ ...recipe, allowed_methods: [...recipe.allowed_methods, method] });
    setSelected(steps.length); setAdding(false); setPositions([]);
  }
  function updateSteps(next: PlanStep[]) {
    const seen = new Set<string>();
    for (const step of next) {
      const expressions = JSON.stringify(step).match(/\$steps\.([^."\\]+)\./g) || [];
      if (expressions.some(expression => !seen.has(expression.split(".")[1]))) { setError("이전 결과를 사용하는 단계가 있습니다. 고급 설정에서 참조를 변경한 뒤 순서를 바꾸거나 삭제해 주세요."); return; }
      if (step.id) seen.add(step.id);
    }
    change({ ...recipe, steps: next }); setPositions([]);
  }
  const nodes: Node[] = [
    { id: "scope", type: "recipe", position: { x: 200, y: 20 }, data: { scope: true, kind: "공통 분석 대상", label: recipe.semantic_scope.primary_metric ? title(recipe.semantic_scope.primary_metric) : "지표 선택", detail: pipeline ? "순서대로 실행" : "단계별 조사" } },
    ...steps.map((step, i) => ({ id: `step:${i}`, type: "recipe", position: { x: pipeline ? 200 : 40 + (i % 2) * 300, y: pipeline ? 200 + i * 180 : 220 + Math.floor(i / 2) * 180 }, data: { kind: pipeline ? `STEP ${i + 1} · ${step.id || ""}` : "사용 가능한 방법", label: methodName(step.method), detail: pipeline ? (step.bindings.dimensions ? refs(step.bindings.dimensions).map(ref => ref.startsWith("$") ? "공통 분류 기준" : title(ref)).join(" → ") : step.params.granularity ? `${step.params.granularity} · 추이` : "설정값 보기") : step.method } })),
  ].map(n => ({ ...n, ...positions.find(p => p.id === n.id), data: n.data, selected: n.id === (selected < 0 ? "scope" : `step:${selected}`) }));
  const nextVersion = saved ? bump(saved.version) : recipe.version;
  async function save() {
    setBusy(true); setError("");
    try {
      const candidate = { ...recipe, version: nextVersion };
      await api<{ valid: boolean; semantic_checked: boolean }>("/recipes:validate?live=true", { body: candidate });
      const value = await api<Recipe>(`/recipes/${encodeURIComponent(recipe.name)}`, { method: "PUT", recipeKey: key, body: { recipe: candidate, base_version: saved?.version || null } });
      setRecipe(value); setSaved(value); setDialog(null);
      if (!initial) router.replace(`/recipes/${encodeURIComponent(value.name)}/edit`);
    } catch (e) { setError(explainError(e)); } finally { setBusy(false); }
  }
  async function run() {
    if (!saved || dirty) return;
    setBusy(true); setError("");
    try { const result = await api<Run>("/runs", { body: { recipe: `${saved.name}@${saved.version}`, scope: { date_range: dates } } }); router.push(`/runs/${result.id}`); }
    catch (e) { setError((e as Error).message); setBusy(false); }
  }
  return <div className={s.page}>
    <header className={s.header}><div><Link className={s.back} href="/recipes"><ArrowLeft size={14} />Recipes</Link><h1>{recipe.name || "새 Recipe"}</h1><span className={s.nodeStatus}>{dirty ? "저장되지 않은 변경" : `v${saved?.version} · 저장됨`}</span></div><div className={s.actions}>
      {dirty && saved && <button className={s.secondary} title="저장된 버전으로 되돌리기" onClick={() => { setRecipe(saved); setSelected(-1); setPositions([]); }}><Undo2 size={16} />되돌리기</button>}
      <button disabled={busy || !dirty} onClick={() => { setError(""); setDialog("save"); }}><Save size={16} />Recipe 저장</button>
      <button disabled={busy || dirty} title={dirty ? "Recipe를 먼저 저장해 주세요" : "저장된 Recipe 실행"} onClick={() => { setError(""); setDialog("run"); }}><Play size={16} />{pipeline ? "Recipe 실행" : "조사 시작"}</button>
    </div></header>
    {(catalogError || methodsError) && <p className={s.error} role="alert">{catalogError?.message || methodsError?.message} <Link href="/sources">연결 확인</Link></p>}
    {error && !dialog && <p className={s.error} role="alert">{error}</p>}
    <div className={s.toolbar}><div className={s.modeSwitch} role="group" aria-label="Recipe 실행 방식"><button className={pipeline ? s.modeActive : s.secondary} aria-pressed={pipeline} onClick={() => { if (!pipeline) change({ ...recipe, mode: "pipeline", steps: recipe.allowed_methods.map((method, i) => ({ id: `step_${i + 1}`, method, bindings: { metric: "$scope.primary_metric" }, params: {} })) }); }}><ArrowDown size={14} />순서대로 실행</button><button className={!pipeline ? s.modeActive : s.secondary} aria-pressed={!pipeline} onClick={() => { if (pipeline) change({ ...recipe, mode: "investigation", allowed_methods: [...new Set(recipe.steps.map(step => step.method))], steps: [] }); }}><Workflow size={14} />단계별 조사</button></div><span className={s.recipeMode}>{pipeline ? `실행 순서 · ${steps.length}단계` : `조사에 허용된 방법 · ${steps.length}개`}</span><button className={s.secondary} onClick={() => { setAdding(false); setSelected(-1); }}>공통 설정</button><button onClick={() => { setAdding(true); setSearch(""); }}><Plus size={16} />{pipeline ? "분석 단계 추가" : "허용할 방법 추가"}</button></div>
    <div className={s.workspace}>
      <section className={s.canvas} aria-label="Recipe 그래프"><ReactFlow nodes={nodes} edges={steps.map((_, i) => ({ id: `edge:${i}`, source: pipeline && i > 0 ? `step:${i - 1}` : "scope", target: `step:${i}`, label: pipeline ? "다음 단계" : "허용", style: { stroke: "#8fa5a9", strokeWidth: 2 } }))} nodeTypes={nodeTypes} onNodesChange={changes => setPositions(applyNodeChanges(changes, nodes))} onNodeClick={(_, node) => { setSelected(node.id === "scope" ? -1 : Number(node.id.split(":")[1])); setAdding(false); }} nodesConnectable={false} deleteKeyCode={null} fitView minZoom={.25} maxZoom={1.1}><Background color="#ced5d8" gap={20} /><Controls showInteractive={false} /></ReactFlow>
        {!steps.length && <div className={s.canvasEmpty}><Workflow size={24} /><h2>첫 분석 단계</h2><button onClick={() => setAdding(true)}><Plus size={16} />분석 방법 선택</button></div>}
      </section>
      <aside className={s.inspector}>
        {adding ? <><h2>분석 방법 선택</h2><label className={s.search}><Search size={16} /><input aria-label="분석 방법 검색" value={search} placeholder="추이, 항목별, 조건 맞춤" onChange={e => setSearch(e.target.value)} /></label><div className={s.choices}>{(methods || []).filter(m => (pipeline || !recipe.allowed_methods.includes(m.name)) && `${methodName(m.name)} ${m.name} ${m.description}`.toLowerCase().includes(search.toLowerCase())).map(m => <button key={m.name} onClick={() => add(m.name)}><span>{methodName(m.name)}</span><Plus size={16} /><small>{m.description}</small></button>)}</div><button className={s.secondary} onClick={() => setAdding(false)}>취소</button></> : !active ? <div className={s.fields}>
          <h2>Recipe 설정</h2><label>Recipe 이름<input value={recipe.name} disabled={!!saved} placeholder="return-rate-analysis" onChange={e => change({ ...recipe, name: e.target.value })} /></label><label>설명<textarea rows={2} value={recipe.description} onChange={e => change({ ...recipe, description: e.target.value })} /></label>
          <RefField label="공통 지표" value={recipe.semantic_scope.primary_metric} objects={objects.filter(o => o.kind === "measure")} onChange={v => change({ ...recipe, semantic_scope: { ...recipe.semantic_scope, primary_metric: String(v) } })} />
          <RefField label="기본 분류 순서" value={recipe.semantic_scope.preferred_dimensions} multiple objects={objects.filter(o => o.kind === "dimension")} onChange={v => change({ ...recipe, semantic_scope: { ...recipe.semantic_scope, preferred_dimensions: refs(v) } })} />
          <details className={s.advanced}><summary>고급 설정</summary><RefField label="함께 볼 지표" value={recipe.semantic_scope.related_metrics} multiple objects={objects.filter(o => o.kind === "measure")} onChange={v => change({ ...recipe, semantic_scope: { ...recipe.semantic_scope, related_metrics: refs(v) } })} /><label>최대 단계<input type="number" min={1} value={recipe.limits.max_steps} onChange={e => change({ ...recipe, limits: { ...recipe.limits, max_steps: Number(e.target.value) } })} /></label><label>최대 쿼리<input type="number" min={1} value={recipe.limits.max_queries} onChange={e => change({ ...recipe, limits: { ...recipe.limits, max_queries: Number(e.target.value) } })} /></label><pre className={s.definition}>{JSON.stringify({ routing: recipe.routing, validators: recipe.validators, required_filters: recipe.semantic_scope.required_filters, instructions: recipe.instructions }, null, 2)}</pre></details>
        </div> : <div className={s.fields}>
          <div className={s.inspectorHeading}><span className={s.eyebrow}>{pipeline ? `STEP ${selected + 1}` : "ALLOWED METHOD"}</span><div className={s.actions}>
            {pipeline && <><button className={s.icon} disabled={selected === 0} title="이전 순서로" aria-label="이전 순서로" onClick={() => { const next = [...recipe.steps]; [next[selected - 1], next[selected]] = [next[selected], next[selected - 1]]; updateSteps(next); }}><ArrowUp size={16} /></button><button className={s.icon} disabled={selected === steps.length - 1} title="다음 순서로" aria-label="다음 순서로" onClick={() => { const next = [...recipe.steps]; [next[selected + 1], next[selected]] = [next[selected], next[selected + 1]]; updateSteps(next); }}><ArrowDown size={16} /></button></>}
            <button className={s.icon} title="단계 삭제" aria-label="단계 삭제" onClick={() => pipeline ? updateSteps(recipe.steps.filter((_, i) => i !== selected)) : change({ ...recipe, allowed_methods: recipe.allowed_methods.filter((_, i) => i !== selected) })}><Trash2 size={16} /></button>
          </div></div>
          <h2>{methodName(active.method)}</h2><span className={s.nodeStatus}>{active.method}</span>
          {pipeline && methods?.find(method => method.name === active.method) ? <StepSettings key={`${selected}-${active.method}`} step={active} manifest={methods.find(method => method.name === active.method)!} objects={objects} recipe={recipe} onChange={step => change({ ...recipe, steps: recipe.steps.map((s, i) => i === selected ? step : s) })} /> : !pipeline ? <p className={s.dependency}>이 Recipe는 단계별 조사입니다. 구체적인 입력값은 조사 실행 중 각 단계에서 정합니다.</p> : <p role="status">분석 설정을 불러오는 중…</p>}
        </div>}
      </aside>
    </div>
    {dialog && <div className={s.overlay}><section className={s.dialog} role="dialog" aria-modal="true" aria-labelledby="recipe-dialog-title"><div className={s.inspectorHeading}><h2 id="recipe-dialog-title">{dialog === "save" ? "Recipe 저장" : "분석 기간"}</h2><button className={s.icon} disabled={busy} aria-label="닫기" onClick={() => setDialog(null)}><X size={18} /></button></div>
      {dialog === "save" ? <><p>{recipe.name || "이름 미입력"} · v{nextVersion} · {steps.length}단계</p><label>Recipe 편집 키<input type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)} /></label><p className={s.nodeStatus}>관리자가 발급한 DL_RECIPE_ADMIN_TOKEN이 필요합니다.</p><details><summary>변경 내용</summary><h3>저장 전</h3><pre className={s.definition}>{saved ? JSON.stringify(saved, null, 2) : "새 Recipe"}</pre><h3>저장 후</h3><pre className={s.definition}>{JSON.stringify({ ...recipe, version: nextVersion }, null, 2)}</pre></details><button className={s.run} disabled={busy || !key || !recipe.name || !recipe.semantic_scope.primary_metric || !steps.length} onClick={save}><Check size={16} />{busy ? "저장 중…" : "새 버전 저장"}</button></> : <><label>시작일<input type="date" value={dates[0]} onChange={e => setDates([e.target.value, dates[1]])} /></label><label>종료일<input type="date" value={dates[1]} onChange={e => setDates([dates[0], e.target.value])} /></label><button className={s.run} disabled={busy || !dates[0] || !dates[1] || dates[0] > dates[1]} onClick={run}><Play size={16} />{busy ? "실행 시작 중…" : "저장된 Recipe 실행"}</button></>}
      {error && <p className={s.error} role="alert">{error}</p>}
    </section></div>}
  </div>;
}
