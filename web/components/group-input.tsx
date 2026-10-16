"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";
import type { ParamSpec } from "@/lib/api";
import { useT } from "@/lib/i18n";
import s from "./group-input.module.css";

type Definition = { values?: unknown[]; exclude?: unknown[]; gte?: number; lt?: number };

export function GroupInput({ label, spec, value, dataType, oppositeValue, onChange }: {
  label: string; spec: ParamSpec; value: unknown; dataType?: string; oppositeValue?: unknown; onChange: (value: unknown) => void;
}) {
  const t = useT();
  const [entry, setEntry] = useState("");
  const definition: Definition = Array.isArray(value) ? { values: value } :
    value && typeof value === "object" ? value as Definition : value != null ? { values: [value] } : {};
  const numeric = dataType === "number";
  const boolean = dataType === "boolean";
  const opposite: Definition = Array.isArray(oppositeValue) ? { values: oppositeValue } : oppositeValue && typeof oppositeValue === "object" ? oppositeValue as Definition : {};
  const mode = value == null ? "auto" : definition.exclude ? "exclude" : definition.gte != null || definition.lt != null ? "range" : "values";
  const [pendingMode, setPendingMode] = useState<string | null>(null);
  const selected = pendingMode ?? (mode === "auto" && dataType === "string" ? "values" : mode);
  const list = definition.exclude ?? definition.values ?? [];
  const changeMode = (next: string) => {
    setEntry(""); setPendingMode(next);
    if (next === "auto") { onChange(null); setPendingMode(null); }
  };
  const add = () => {
    if (!entry.trim() || numeric && !Number.isFinite(Number(entry))) return;
    const next = numeric ? Number(entry) : entry.trim();
    onChange({ [selected === "exclude" ? "exclude" : "values"]: [...new Set([...(mode === selected ? list : []), next])] });
    setEntry(""); setPendingMode(null);
  };
  if (boolean) {
    const automatic = spec.meaning === "comparison_subject" ? true : oppositeValue == null ? false : opposite.values?.length === 1 ? String(opposite.values[0]).toLowerCase() !== "true" : undefined;
    const current = definition.values?.length === 1 ? String(definition.values[0]).toLowerCase() : "";
    if (value == null || current === "true" || current === "false") return <label>{label}<select aria-label={label} value={current} onChange={event => onChange(event.target.value === "" ? null : { values: [event.target.value === "true"] })}>
      <option value="">{automatic == null ? t("Choose at run time") : `${t(automatic ? "Yes" : "No")} · ${t(spec.meaning === "comparison_subject" ? "Default" : "Opposite group")}`}</option>
      <option value="true">{t("Yes")}</option><option value="false">{t("No")}</option>
    </select></label>;
  }
  return <div>
    <label>{label}<select aria-label={t("{label} definition", { label })} value={selected} onChange={event => changeMode(event.target.value)}>
      <option value="auto">{numeric && spec.meaning === "comparison_population" && (opposite.gte != null) !== (opposite.lt != null)
        ? opposite.gte != null ? t("Below {value} · opposite range", { value: opposite.gte }) : t("{value} or more · opposite range", { value: opposite.lt! })
        : t("Choose at run time")}</option>
      <option value="values">{t("Listed values")}</option><option value="exclude">{t("Exclude listed values")}</option>
      {numeric && <option value="range">{t("Numeric range")}</option>}
    </select></label>
    {(selected === "values" || selected === "exclude") && <>
      {mode === selected && list.map((item, index) => <div key={index} className={s.row}>
        <span>{String(item)}</span><button type="button" title={t("Remove value")} aria-label={t("Remove {label} value {number}", { label, number: index + 1 })} onClick={() => { const remaining = list.filter((_, i) => i !== index); onChange(remaining.length ? { [selected]: remaining } : null); }}><X size={14} /></button>
      </div>)}
      <div className={s.row}><input aria-label={t("{label} value", { label })} type={numeric ? "number" : "text"} step={numeric ? "any" : undefined} value={entry} onChange={event => setEntry(event.target.value)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); add(); } }} />
        <button type="button" title={t("Add value")} aria-label={t("Add {label} value", { label })} disabled={!entry.trim() || numeric && !Number.isFinite(Number(entry))} onClick={add}><Plus size={15} /></button></div>
    </>}
    {selected === "range" && <div className={s.range}>
      {([['gte', t("At least")], ['lt', t("Below")]] as const).map(([key, text]) => <label key={key}>{text}<input aria-label={`${label} ${text}`} type="number" step="any" value={mode === "range" ? definition[key] ?? "" : ""} onChange={event => {
        const range = mode === "range" ? { ...definition } : {};
        if (event.target.value === "") delete range[key]; else range[key] = Number(event.target.value);
        onChange(Object.keys(range).length ? range : null); setPendingMode(null);
      }} /></label>)}
    </div>}
  </div>;
}
