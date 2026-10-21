"use client";
import { useT } from "@/lib/i18n";

import type { Ref } from "react";
import { Plus, X } from "lucide-react";
import type { ParamSpec, SemanticObject } from "@/lib/api";
import { ParamInput } from "@/components/forms";
import { GroupInput } from "@/components/group-input";
import { sourceLabel } from "./step-input-source";
import { parameterLabel, refs } from "./editor-model";
import s from "@/components/analysis-canvas.module.css";

export function RefField({ label, value, objects, multiple, onChange, inherited, selectRef, error, fieldPath }: {
  label: string; value: unknown; objects: SemanticObject[]; multiple?: boolean;
  onChange: (value: string | string[]) => void; inherited?: string; selectRef?: Ref<HTMLSelectElement>; error?: string; fieldPath?: string;
}) {
  const t = useT();
  const list = refs(value);
  const expression = typeof value === "string" && value.startsWith("$") ? value : null;
  return <div className={s.refField} data-recipe-field={fieldPath}><span>{label}</span>{expression ? <div className={s.inherited}><span>{inherited || expression}</span><button type="button" className={s.secondary} onClick={() => onChange(multiple ? [] : "")}>{t("Choose directly")}</button></div> : multiple ? <>
    {list.map((ref, i) => <div className={s.refRow} key={`${ref}-${i}`}><span>{objects.find(o => o.ref === ref)?.title || ref}</span><button type="button" className={s.icon} title={t("Remove {label}", { label: label })} aria-label={t("Remove {label} {number}", { label: label, number: i + 1 })} onClick={() => onChange(list.filter((_, j) => i !== j))}><X size={14} /></button></div>)}
    <select aria-label={label} aria-invalid={!!error} value="" onChange={e => e.target.value && onChange([...list, e.target.value])}><option value="">{t("Choose to add")}</option>{objects.filter(o => !list.includes(o.ref)).map(o => <option key={o.ref} value={o.ref}>{o.title}</option>)}</select>
  </> : <select ref={selectRef} aria-label={label} aria-invalid={!!error} value={list[0] || ""} onChange={e => onChange(e.target.value)}><option value="">{t("Choose…")}</option>{list[0] && !objects.some(o => o.ref === list[0]) && <option value={list[0]}>{t("Name needs checking in the catalog")}</option>}{objects.map(o => <option key={o.ref} value={o.ref}>{o.title}</option>)}</select>}{error && <small className={s.fieldError} role="alert">{error}</small>}</div>;
}

export function ParameterField({ name, spec, value, onChange, disabled = false, error, fieldPath, objects = [], dataType, oppositeValue }: { name: string; spec: ParamSpec; value: unknown; onChange: (value: unknown) => void; disabled?: boolean; error?: string; fieldPath?: string; objects?: SemanticObject[]; dataType?: string; oppositeValue?: unknown }) {
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
        <select aria-label={t("{kind} dimension {number}", { kind: name === "subject" ? t("Subject") : t("Peer"), number: index + 1 })} value={item.member} onChange={event => change(index, { member: event.target.value, value: "" })}><option value="">{t("Choose a dimension")}</option>{objects.filter(object => object.kind === "dimension").map(object => <option key={object.ref} value={object.ref}>{object.title}</option>)}</select>
        <input aria-label={t("{kind} value {number}", { kind: name === "subject" ? t("Subject") : t("Peer"), number: index + 1 })} placeholder={t("Enter a value")} value={String(item.value ?? "")} onChange={event => change(index, { value: objects.find(object => object.ref === item.member)?.data_type === "number" && event.target.value !== "" ? Number(event.target.value) : event.target.value })} />
        <button type="button" className={s.secondary} onClick={() => onChange(items.filter((_, i) => i !== index))}><X size={13} />{t("Delete")}</button>
      </div>)}
      {(spec.meaning !== "comparison_subject" || !items.length) && <button type="button" className={s.secondary} onClick={() => onChange([...items, { member: "", value: "" }])}><Plus size={13} />{t("Add condition")}</button>}
      {error && <small className={s.fieldError} role="alert">{error}</small>}
    </fieldset>;
  }
  const options: Record<string, string> = { day: t("Daily"), week: t("Weekly"), month: t("Monthly"), quarter: t("Quarterly"), value: t("Metric value"), vs_rest: t("Difference from the other groups"), count: t("Count"), desc: t("Highest values first"), asc: t("Lowest values first") };
  if (spec.type === "boolean") return <label className={s.check} data-recipe-field={fieldPath}><input type="checkbox" aria-invalid={!!error} disabled={disabled} checked={!!current} onChange={event => onChange(event.target.checked)} />{label}{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  if (spec.type === "enum") return <label data-recipe-field={fieldPath}>{label}<select aria-label={label} aria-invalid={!!error} disabled={disabled} value={String(current ?? "")} onChange={event => onChange(event.target.value)}>{(spec.enum || []).map(option => <option value={option} key={option}>{options[option] || option}</option>)}</select>{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  if (spec.type === "integer" || spec.type === "number") return <label data-recipe-field={fieldPath}>{label}<input type="number" aria-invalid={!!error} disabled={disabled} step={spec.type === "integer" ? 1 : "any"} min={spec.minimum ?? undefined} max={spec.maximum ?? undefined} value={current == null ? "" : Number(current)} onChange={event => onChange(event.target.value === "" ? null : Number(event.target.value))} /><small>{spec.description}</small>{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  if (spec.semantic_kind) return <fieldset disabled={disabled}><RefField label={label} value={current} objects={objects.filter(object => object.kind === spec.semantic_kind || spec.semantic_kind === "dimension" && object.kind === "time_dimension")} multiple={spec.type === "ref_list"} onChange={onChange} error={error} fieldPath={fieldPath} /></fieldset>;
  if (spec.type === "string") return <label data-recipe-field={fieldPath}>{label}<input aria-invalid={!!error} disabled={disabled} value={String(current ?? "")} onChange={event => onChange(event.target.value)} /><small>{spec.description}</small>{error && <small className={s.fieldError} role="alert">{error}</small>}</label>;
  return <fieldset disabled={disabled} data-recipe-field={fieldPath}><ParamInput name={label} spec={spec} value={current} onChange={onChange} />{error && <small className={s.fieldError} role="alert">{error}</small>}</fieldset>;
}
