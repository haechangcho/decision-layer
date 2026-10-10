"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";
import type { ParamSpec } from "@/lib/api";
import s from "./group-input.module.css";

type Definition = { values?: unknown[]; exclude?: unknown[]; gte?: number; lt?: number };

export function GroupInput({ label, spec, value, dataType, oppositeValue, onChange }: {
  label: string; spec: ParamSpec; value: unknown; dataType?: string; oppositeValue?: unknown; onChange: (value: unknown) => void;
}) {
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
      <option value="">{automatic == null ? "실행할 때 선택" : `${automatic ? "예" : "아니요"} · ${spec.meaning === "comparison_subject" ? "기본값" : "반대 그룹"}`}</option>
      <option value="true">예</option><option value="false">아니요</option>
    </select></label>;
  }
  return <div>
    <label>{label}<select aria-label={`${label} 정의`} value={selected} onChange={event => changeMode(event.target.value)}>
      <option value="auto">{numeric && spec.meaning === "comparison_population" && (opposite.gte != null) !== (opposite.lt != null)
        ? opposite.gte != null ? `${opposite.gte} 미만 · 반대 범위` : `${opposite.lt} 이상 · 반대 범위`
        : "실행할 때 선택"}</option>
      <option value="values">지정한 값</option><option value="exclude">지정한 값 제외</option>
      {numeric && <option value="range">숫자 범위</option>}
    </select></label>
    {(selected === "values" || selected === "exclude") && <>
      {mode === selected && list.map((item, index) => <div key={index} className={s.row}>
        <span>{String(item)}</span><button type="button" title="값 삭제" aria-label={`${label} 값 ${index + 1} 삭제`} onClick={() => { const remaining = list.filter((_, i) => i !== index); onChange(remaining.length ? { [selected]: remaining } : null); }}><X size={14} /></button>
      </div>)}
      <div className={s.row}><input aria-label={`${label} 값`} type={numeric ? "number" : "text"} step={numeric ? "any" : undefined} value={entry} onChange={event => setEntry(event.target.value)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); add(); } }} />
        <button type="button" title="값 추가" aria-label={`${label} 값 추가`} disabled={!entry.trim() || numeric && !Number.isFinite(Number(entry))} onClick={add}><Plus size={15} /></button></div>
    </>}
    {selected === "range" && <div className={s.range}>
      {([['gte', '이상'], ['lt', '미만']] as const).map(([key, text]) => <label key={key}>{text}<input aria-label={`${label} ${text}`} type="number" step="any" value={mode === "range" ? definition[key] ?? "" : ""} onChange={event => {
        const range = mode === "range" ? { ...definition } : {};
        if (event.target.value === "") delete range[key]; else range[key] = Number(event.target.value);
        onChange(Object.keys(range).length ? range : null); setPendingMode(null);
      }} /></label>)}
    </div>}
  </div>;
}
