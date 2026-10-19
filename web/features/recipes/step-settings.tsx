"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Undo2 } from "lucide-react";
import { api, type MethodManifest, type ParamSpec, type PlanStep, type Recipe, type RoleSpec, type SemanticObject } from "@/lib/api";
import { declaredPath, selectionLabel, sourceLabel } from "./step-input-source";
import { explainError, parameterLabel, refs, roleLabels, roleObjects, type FieldError } from "./editor-model";
import { ParameterField, RefField } from "./recipe-fields";
import groupsStyle from "@/components/group-input.module.css";
import s from "@/components/analysis-canvas.module.css";

export function StepSettings({ step, manifest, onChange, objects, recipe, stepIndex, fieldError, methods }: { step: PlanStep; manifest: MethodManifest; onChange: (s: PlanStep) => void; objects: SemanticObject[]; recipe: Recipe; stepIndex: number; fieldError: FieldError | null; methods: MethodManifest[] }) {
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
          return `${index + 1}단계에서 ${selectionLabel(resolved, ref.project || "path", methods, { titles: new Map(objects.map(object => [object.ref, object])), steps: recipe.steps.map(item => ({ ...item, bindings: { ...item.bindings, dimensions: item.bindings.dimensions === "$scope.preferred_dimensions" ? recipe.semantic_scope.preferred_dimensions : item.bindings.dimensions } })) })} · 실행마다 다시 선택`;
        }
      }
      if (ref.source === "input") return `실행할 때 선택 · ${recipe.inputs?.[ref.name || ""]?.label || spec.label || "분석 대상"}`;
    }
    if (Array.isArray(value) && value.length) return value.map(item => `${objects.find(object => object.ref === item.member)?.title || "항목"}: ${String(item.value)}`).join(" · ");
    return spec.meaning === "comparison_population" ? "전체 분석 범위의 다른 대상들과 비교" : "전체 분석 범위";
  };
  const metricBinding = step.bindings.metric;
  const usesRecipeMetric = metricBinding === "$scope.primary_metric";
  const metricRef = usesRecipeMetric ? recipe.semantic_scope.primary_metric : metricBinding;
  const metricTitle = typeof metricRef === "string" ? objects.find(o => o.ref === metricRef)?.title || metricRef || "지표 미설정" : "지표 미설정";
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
    }).catch(error => { if (!cancelled) setCountError(explainError(error)); }).finally(() => { if (!cancelled) setCountBusy(false); });
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
    const inherited = name === "metric" ? objects.find(o => o.ref === recipe.semantic_scope.primary_metric)?.title || "미선택"
      : name === "dimensions" ? recipe.semantic_scope.preferred_dimensions.map(ref => objects.find(o => o.ref === ref)?.title || ref).join(" → ") || "미선택" : undefined;
    const path = `steps[${stepIndex}].bindings.${name}`;
    if (role.default_binding === "unit_count") {
      if (metricObject?.metric_kind !== "average") return step.bindings[name] ? <div key={name} className={groupsStyle.countIssue}><p>변경한 지표에는 이전 건수 연결을 사용할 수 없습니다.</p><button type="button" className={s.secondary} onClick={() => { const bindings = { ...step.bindings }; delete bindings[name]; onChange({ ...step, bindings }); }}>이전 건수 연결 제거</button></div> : null;
      const current = objects.find(object => object.ref === step.bindings[name]);
      if (current && metricObject.entity && current.count_measure === current.ref && current.entity === metricObject.entity && current.metric_kind === "count") return null;
      const candidates = roleObjects(role, objects).filter(object => !!metricObject.entity && object.entity === metricObject.entity && object.count_measure === object.ref);
      return <div key={name} className={groupsStyle.countIssue}>
        <p>{countBusy ? "비교할 분석 단위를 확인하고 있습니다…" : "평균을 비교하려면 같은 분석 단위의 건수를 확인해야 합니다. 자동으로 확인할 수 없어 연결이 필요합니다."}</p>
        {countError && <><p role="alert">{countError}</p><button type="button" className={s.secondary} onClick={() => setCountRetry(value => value + 1)}>다시 확인</button></>}
        {!countBusy && (candidates.length ? <RefField label="분석 단위의 건수 확인" value={step.bindings[name]} objects={candidates} onChange={next => { const bindings = { ...step.bindings }; if (next) bindings[name] = next; else delete bindings[name]; onChange({ ...step, bindings }); }} fieldPath={path} error={fieldError?.field === path ? fieldError.message : undefined} /> : <p>연결된 semantic layer에서 기본 분석 단위와 같은 단위의 행 건수를 제공해야 합니다. 모델 담당자에게 확인해 주세요. <Link href="/sources">연결 상태 확인</Link></p>)}
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
        <h3 className={groupsStyle.heading}>비교할 두 집단</h3>
        <fieldset className={s.fields} disabled={parameters.some(([key]) => fixed(key))}><RefField label={role.label || roleLabels[name] || name} value={value} objects={candidates} fieldPath={path} error={fieldError && keys.some(key => fieldError.field === `steps[${stepIndex}].bindings.${key}`) ? fieldError.message : undefined} onChange={next => {
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
      return <fieldset key={name} disabled={fixed(parameter)}><RefField label={role.label || roleLabels[name] || name} value={value} objects={candidates} fieldPath={path} error={fieldError?.field === path || fieldError?.field === parameterPath ? fieldError.message : undefined} onChange={next => {
        if (!next) {
          const params = { ...step.params }; delete params[parameter];
          onChange({ ...step, bindings: { ...step.bindings, [name]: [] }, params });
          return;
        }
        const dimensions = refs(resolved.bindings[name]);
        onChange({ ...step, bindings: { ...step.bindings, [name]: dimensions.includes(String(next)) ? dimensions : [...dimensions, String(next)] }, params: { ...step.params, [parameter]: next } });
      }} /></fieldset>;
    }
    return <RefField key={name} label={role.label || roleLabels[name] || name} value={step.bindings[name]} objects={roleObjects(role, objects)} multiple={role.multiple} inherited={inherited} fieldPath={path} error={fieldError?.field === path ? fieldError.message : undefined} onChange={next => bind(name, next)} />;
  };
  const context = Object.entries(manifest.parameters).filter(([, spec]) => spec.meaning === "analysis_scope").map(([name, spec]) => {
    const value = parameterValue(name);
    return sourceLabel(value) || Array.isArray(value) && value.length ? describeSource(value, spec) : null;
  }).filter(Boolean);
  return <>
    {manifest.roles.metric && <div><p className={s.nodeStatus}>{Object.values(manifest.roles).some(role => role.exclusive_group) ? "비교할 지표" : "분석 지표"}</p><div className={s.inherited}><strong>{metricTitle}</strong><button type="button" className={s.secondary} onClick={() => setEditingMetric(!editingMetric)}>{editingMetric ? "완료" : "지표 변경"}</button></div></div>}
    {editingMetric && manifest.roles.metric && <>
      <RefField label="이 단계에서 사용할 지표" value={metricBinding} objects={roleObjects(manifest.roles.metric, objects)} inherited={metricTitle} fieldPath={`steps[${stepIndex}].bindings.metric`} error={fieldError?.field === `steps[${stepIndex}].bindings.metric` ? fieldError.message : undefined} onChange={next => bind("metric", next)} />
      {!usesRecipeMetric && <button type="button" className={s.secondary} onClick={() => { bind("metric", "$scope.primary_metric"); setEditingMetric(false); }}><Undo2 size={13} />Recipe 지표 사용</button>}
    </>}
    {context.map((text, index) => <p key={index} className={s.nodeStatus}>{text}</p>)}
    {policy && <p className={s.nodeStatus}>이 절차에 지정된 실행 제약을 유지합니다. 변경은 코드 보기에서 할 수 있습니다.</p>}
    {Object.entries(manifest.roles).filter(([name, role]) => name !== "metric" && (role.required || role.exclusive_group || step.bindings[name] || role.default_binding === "unit_count" && metricObject?.metric_kind === "average")).map(roleField)}
    {basicParameters.filter(([, spec]) => !spec.semantic_role || !manifest.roles[spec.semantic_role]?.exclusive_group).map(([name, spec]) => {
      const path = `steps[${stepIndex}].params.${name}`;
      const value = parameterValue(name);
      return spec.type === "drill_path" && sourceLabel(value) ? <div className={s.refField} key={name}><strong>{spec.label || parameterLabel(name)}</strong><span className={s.nodeStatus}>{describeSource(value, spec)}</span></div>
        : parameterField([name, spec]);
    })}
    <label>{step.purpose_context === "source_run" ? "원래 분석의 단계 설명 (재사용할 설명으로 수정 가능)" : "이 단계에서 확인할 내용"}<textarea rows={2} maxLength={240} value={step.purpose ?? ""} onChange={event => onChange({ ...step, purpose: event.target.value || null, purpose_context: "procedure" })} /></label>
  </>;
}
