"use client";

import { ParamInput } from "@/components/forms";
import type { ParamSpec, SemanticObject } from "@/lib/api";
import { useT } from "@/lib/i18n";

export function RecipeRuntimeInputs({ specs, values, onChange, objects }: { specs: Record<string, ParamSpec>; values: Record<string, unknown>; onChange: (values: Record<string, unknown>) => void; objects: SemanticObject[] }) {
  const t = useT();
  return <>{Object.entries(specs).map(([name, spec]) => {
    const set = (value: unknown) => onChange({ ...values, [name]: value });
    const value = values[name] ?? spec.default;
    const label = spec.label || spec.description || name;
    if (spec.type === "drill_path") {
      const path = Array.isArray(value) ? value as { member: string; value: unknown }[] : [];
      return <fieldset key={name}><legend>{label}{spec.required ? ` · ${t("required")}` : ""}</legend>{path.map((condition, i) => <div className="row" key={i}>
        <select aria-label={t("{label} dimension {number}", { label, number: i + 1 })} value={condition.member} onChange={event => set(path.map((item, index) => index === i ? { member: event.target.value, value: "" } : item))}><option value="">{t("Choose a category")}</option>{objects.filter(object => object.kind === "dimension").map(object => <option key={object.ref} value={object.ref}>{object.title}</option>)}</select>
        <input aria-label={t("{label} value {number}", { label, number: i + 1 })} value={String(condition.value ?? "")} onChange={event => set(path.map((item, index) => index === i ? { ...item, value: objects.find(object => object.ref === item.member)?.data_type === "number" ? Number(event.target.value) : event.target.value } : item))} />
        <button type="button" onClick={() => set(path.filter((_, index) => index !== i))}>{t("Delete")}</button>
      </div>)}{(spec.meaning !== "comparison_subject" || !path.length) && <button type="button" onClick={() => set([...path, { member: "", value: "" }])}>{t("Add condition")}</button>}</fieldset>;
    }
    if (spec.type === "string") return <label className="field" key={name}>{label}{spec.required ? ` · ${t("required")}` : ""}<input value={String(value ?? "")} onChange={event => set(event.target.value)} /></label>;
    if (spec.type === "boolean") return <label className="check" key={name}><input type="checkbox" checked={!!value} onChange={event => set(event.target.checked)} />{label}</label>;
    return <ParamInput key={name} name={label} spec={{ ...spec, description: "" }} value={value} onChange={set} />;
  })}</>;
}
