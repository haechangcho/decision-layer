"use client";

import { ParamInput } from "@/components/forms";
import type { ParamSpec, SemanticObject } from "@/lib/api";

export function RecipeRuntimeInputs({ specs, values, onChange, objects }: { specs: Record<string, ParamSpec>; values: Record<string, unknown>; onChange: (values: Record<string, unknown>) => void; objects: SemanticObject[] }) {
  return <>{Object.entries(specs).map(([name, spec]) => {
    const set = (value: unknown) => onChange({ ...values, [name]: value });
    const value = values[name] ?? spec.default;
    const label = spec.label || spec.description || name;
    if (spec.type === "drill_path") {
      const path = Array.isArray(value) ? value as { member: string; value: unknown }[] : [];
      return <fieldset key={name}><legend>{label}{spec.required ? " · 필수" : ""}</legend>{path.map((condition, i) => <div className="row" key={i}>
        <select aria-label={`${label} 차원 ${i + 1}`} value={condition.member} onChange={event => set(path.map((item, index) => index === i ? { member: event.target.value, value: "" } : item))}><option value="">분류 선택</option>{objects.filter(object => object.kind === "dimension").map(object => <option key={object.ref} value={object.ref}>{object.title}</option>)}</select>
        <input aria-label={`${label} 값 ${i + 1}`} value={String(condition.value ?? "")} onChange={event => set(path.map((item, index) => index === i ? { ...item, value: objects.find(object => object.ref === item.member)?.data_type === "number" ? Number(event.target.value) : event.target.value } : item))} />
        <button type="button" onClick={() => set(path.filter((_, index) => index !== i))}>삭제</button>
      </div>)}{(spec.meaning !== "comparison_subject" || !path.length) && <button type="button" onClick={() => set([...path, { member: "", value: "" }])}>조건 추가</button>}</fieldset>;
    }
    if (spec.type === "string") return <label className="field" key={name}>{label}{spec.required ? " · 필수" : ""}<input value={String(value ?? "")} onChange={event => set(event.target.value)} /></label>;
    if (spec.type === "boolean") return <label className="check" key={name}><input type="checkbox" checked={!!value} onChange={event => set(event.target.checked)} />{label}</label>;
    return <ParamInput key={name} name={label} spec={{ ...spec, description: "" }} value={value} onChange={set} />;
  })}</>;
}
