"use client";

// Inputs generated from a Method manifest: one picker per role, one input per parameter.
// A new Method (or a new parameter type that is JSON-shaped) needs no new page.

import { useState } from "react";

import type { Kind, MethodManifest, ParamSpec, RoleSpec, Scope, SemanticObject } from "@/lib/api";
import { useT } from "@/lib/i18n";

function refLabel(o: SemanticObject) {
  const [, , , cube, member] = o.ref.split("/");
  return `${o.title} — ${cube}.${member}`;
}

function candidates(objects: SemanticObject[], role: RoleSpec) {
  return objects.filter((o) => {
    const kindOk = o.kind === role.kind || (role.kind === "dimension" && o.kind === "time_dimension");
    const metricOk = !role.metric_kinds || role.kind !== "measure" || role.metric_kinds.includes(o.metric_kind ?? "");
    return kindOk && metricOk;
  });
}

export function RefSelect({ objects, kind, value, onChange, allowEmpty = true }: {
  objects: SemanticObject[]; kind: Kind[]; value: string; onChange: (v: string) => void; allowEmpty?: boolean;
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {allowEmpty && <option value="">—</option>}
      {objects.filter((o) => kind.includes(o.kind)).map((o) => (
        <option key={o.ref} value={o.ref}>{refLabel(o)}</option>
      ))}
    </select>
  );
}

export function RoleInput({ name, role, objects, value, onChange, restrictTo }: {
  name: string; role: RoleSpec; objects: SemanticObject[]; value: string | string[] | undefined;
  onChange: (v: string | string[] | undefined) => void; restrictTo?: string[];
}) {
  const t = useT();
  let options = candidates(objects, role);
  if (restrictTo && role.kind === "measure") options = options.filter((o) => restrictTo.includes(o.ref));
  const label = (
    <span className="label">
      {name} <span className="muted">({role.kind}{role.multiple ? "[]" : ""}{role.required ? "" : `, ${t("optional")}`})</span>
    </span>
  );
  if (role.multiple) {
    const list = Array.isArray(value) ? value : value ? [value] : [];
    return (
      <div className="field">
        {label}
        <div className="hint">{role.description}</div>
        {list.map((v, i) => (
          <div key={i} className="row">
            <span className="order">{i + 1}</span>
            <select value={v} onChange={(e) => onChange(list.map((x, j) => (j === i ? e.target.value : x)))}>
              {options.map((o) => <option key={o.ref} value={o.ref}>{refLabel(o)}</option>)}
            </select>
            <button type="button" className="ghost" onClick={() => onChange(list.filter((_, j) => j !== i))}>{t("Remove")}</button>
          </div>
        ))}
        <select value="" onChange={(e) => e.target.value && onChange([...list, e.target.value])}>
          <option value="">{t("+ Add")}</option>
          {options.filter((o) => !list.includes(o.ref)).map((o) => <option key={o.ref} value={o.ref}>{refLabel(o)}</option>)}
        </select>
      </div>
    );
  }
  return (
    <label className="field">
      {label}
      <div className="hint">{role.description}</div>
      <select value={(value as string) || ""} onChange={(e) => onChange(e.target.value || undefined)}>
        <option value="">—</option>
        {options.map((o) => <option key={o.ref} value={o.ref}>{refLabel(o)}</option>)}
      </select>
    </label>
  );
}

const JSON_TYPES = new Set(["drill_path", "ref_list", "group", "ranges", "number_list", "string"]);

export function ParamInput({ name, spec, value, onChange }: {
  name: string; spec: ParamSpec; value: unknown; onChange: (v: unknown) => void;
}) {
  const [text, setText] = useState(() => (value === undefined ? "" : typeof value === "string" ? value : JSON.stringify(value)));
  const [bad, setBad] = useState(false);
  const t = useT();
  const label = (
    <span className="label">{name} <span className="muted">({spec.type}{spec.required ? `, ${t("required")}` : ""})</span></span>
  );
  const hint = <div className="hint">{spec.description}{spec.default !== undefined && spec.default !== null ? ` · ${t("default {value}", { value: JSON.stringify(spec.default) })}` : ""}</div>;

  if (spec.type === "enum") {
    return (
      <label className="field">{label}{hint}
        <select value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value || undefined)}>
          <option value="">{t("(default)")}</option>
          {spec.enum?.map((x) => <option key={x}>{x}</option>)}
        </select>
      </label>
    );
  }
  if (spec.type === "boolean") {
    return (
      <label className="field">{label}{hint}
        <select value={value === undefined ? "" : String(value)} onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value === "true")}>
          <option value="">{t("(default)")}</option><option value="true">true</option><option value="false">false</option>
        </select>
      </label>
    );
  }
  if (spec.type === "integer" || spec.type === "number") {
    return (
      <label className="field">{label}{hint}
        <input type="number" value={(value as number) ?? ""} step={spec.type === "integer" ? 1 : "any"}
          onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))} />
      </label>
    );
  }
  if (spec.type === "date_range") {
    const [a, b] = (value as string[]) || ["", ""];
    return (
      <div className="field">{label}{hint}
        <div className="row">
          <input type="date" value={a} onChange={(e) => onChange(e.target.value || b ? [e.target.value, b] : undefined)} />
          <span>~</span>
          <input type="date" value={b} onChange={(e) => onChange(a || e.target.value ? [a, e.target.value] : undefined)} />
        </div>
      </div>
    );
  }
  // JSON-shaped parameters: a textarea that accepts JSON (or plain text for strings)
  return (
    <label className="field">{label}{hint}
      <textarea rows={JSON_TYPES.has(spec.type) && spec.type !== "string" ? 3 : 1} className={bad ? "bad" : ""} value={text}
        placeholder={spec.type === "string" ? "" : "JSON"}
        onChange={(e) => {
          const t = e.target.value;
          setText(t);
          if (!t.trim()) { setBad(false); onChange(undefined); return; }
          try { onChange(JSON.parse(t)); setBad(false); } catch {
            if (spec.type === "string") { onChange(t); setBad(false); } else setBad(true);
          }
        }} />
    </label>
  );
}

export function ScopeInput({ objects, scope, onChange }: { objects: SemanticObject[]; scope: Scope; onChange: (s: Scope) => void }) {
  const [a, b] = scope.date_range || ["", ""];
  const [filters, setFilters] = useState(scope.filters?.length ? JSON.stringify(scope.filters) : "");
  const [bad, setBad] = useState(false);
  const t = useT();
  return (
    <fieldset>
      <legend>{t("Analysis scope")}</legend>
      <div className="field">
        <span className="label">{t("Period")}</span>
        <div className="row">
          <input type="date" value={a} onChange={(e) => onChange({ ...scope, date_range: e.target.value || b ? [e.target.value, b] : null })} />
          <span>~</span>
          <input type="date" value={b} onChange={(e) => onChange({ ...scope, date_range: a || e.target.value ? [a, e.target.value] : null })} />
        </div>
      </div>
      <label className="field">
        <span className="label">{t("Date basis")} <span className="muted">{t("(optional — only when asked)")}</span></span>
        <RefSelect objects={objects} kind={["time_dimension"]} value={scope.time_dimension || ""}
          onChange={(v) => onChange({ ...scope, time_dimension: v || null })} />
      </label>
      <label className="field">
        <span className="label">{t("Shared filters")} <span className="muted">(JSON: [{"{"}"member", "operator", "values"{"}"}])</span></span>
        <textarea rows={2} className={bad ? "bad" : ""} value={filters} onChange={(e) => {
          setFilters(e.target.value);
          if (!e.target.value.trim()) { setBad(false); onChange({ ...scope, filters: [] }); return; }
          try { onChange({ ...scope, filters: JSON.parse(e.target.value) }); setBad(false); } catch { setBad(true); }
        }} />
      </label>
    </fieldset>
  );
}

/** Role and parameter inputs for one Method; returns {bindings, params} through onChange. */
export function MethodInputs({ manifest, objects, bindings, params, onBindings, onParams, restrictMeasures }: {
  manifest: MethodManifest; objects: SemanticObject[];
  bindings: Record<string, string | string[] | undefined>; params: Record<string, unknown>;
  onBindings: (b: Record<string, string | string[] | undefined>) => void; onParams: (p: Record<string, unknown>) => void;
  restrictMeasures?: string[];
}) {
  const t = useT();
  return (
    <>
      <fieldset>
        <legend>{t("Roles (semantic refs)")}</legend>
        {Object.entries(manifest.roles).map(([name, role]) => (
          <RoleInput key={name} name={name} role={role} objects={objects} value={bindings[name]} restrictTo={restrictMeasures}
            onChange={(v) => onBindings({ ...bindings, [name]: v })} />
        ))}
      </fieldset>
      {Object.keys(manifest.parameters).length > 0 && (
        <fieldset>
          <legend>{t("Parameters")}</legend>
          {Object.entries(manifest.parameters).map(([name, spec]) => (
            <ParamInput key={`${manifest.name}.${name}`} name={name} spec={spec} value={params[name]}
              onChange={(v) => onParams({ ...params, [name]: v })} />
          ))}
        </fieldset>
      )}
    </>
  );
}

export function clean<T extends Record<string, unknown>>(o: T): Partial<T> {
  return Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined && v !== "" && !(Array.isArray(v) && !v.length))) as Partial<T>;
}
