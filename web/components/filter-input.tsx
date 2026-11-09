"use client";

import { Plus, X } from "lucide-react";
import type { SemanticObject } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { completeFilters, filterOperators, filterValue, type FilterOperator, type QueryFilter } from "@/lib/query-filters";
import s from "./filter-input.module.css";

export function FilterInput({ label, value, objects, onChange, disabled = false }: {
  label: string; value: unknown; objects: SemanticObject[]; onChange: (value: QueryFilter[]) => void; disabled?: boolean;
}) {
  const t = useT();
  const filters: QueryFilter[] = Array.isArray(value) ? value.map(item => ({
    member: typeof item?.member === "string" ? item.member : "",
    operator: typeof item?.operator === "string" ? item.operator : "equals",
    values: Array.isArray(item?.values) ? item.values : [],
  })) : [];
  const fields = objects.filter(object => object.public !== false);
  const labels: Record<FilterOperator, string> = {
    equals: t("Equals"), notEquals: t("Does not equal"), contains: t("Contains text"),
    gt: t("Greater than"), gte: t("At least"), lt: t("Less than"), lte: t("At most"),
    set: t("Has a value"), notSet: t("Has no value"),
  };
  const update = (index: number, patch: Partial<QueryFilter>) => onChange(filters.map((item, i) => i === index ? { ...item, ...patch } : item));
  return <fieldset className={s.editor} disabled={disabled}>
    <legend>{label}</legend>
    <p className={s.hint}>{filters.length ? t("All conditions below must match. They are applied when querying data.") : t("No conditions. Query all data in the selected period.")}</p>
    {filters.map((filter, index) => {
      const field = fields.find(object => object.ref === filter.member);
      const operators = filterOperators(field?.data_type);
      const needsValue = !["set", "notSet"].includes(filter.operator);
      const values = filter.values.length ? filter.values : [undefined];
      const multi = ["equals", "notEquals"].includes(filter.operator);
      return <section key={index} className={s.condition} aria-label={t("Condition {number}", { number: index + 1 })}>
        <div className={s.heading}><strong>{t("Condition {number}", { number: index + 1 })}</strong><button type="button" className={s.remove} aria-label={t("Remove condition {number}", { number: index + 1 })} onClick={() => onChange(filters.filter((_, i) => i !== index))}><X size={15}/></button></div>
        <label>{t("Filter field")}<select aria-label={t("Filter field {number}", { number: index + 1 })} value={filter.member} onChange={event => update(index, { member: event.target.value, operator: "equals", values: [] })}>
          <option value="">{t("Choose a field from the catalog")}</option>
          {filter.member && !field && <option value={filter.member}>{t("Name needs checking in the catalog")}</option>}
          {([['dimension', t("Dimensions")], ['measure', t("Metrics")], ['time_dimension', t("Dates")]] as const).map(([kind, name]) => <optgroup key={kind} label={name}>{fields.filter(object => object.kind === kind).map(object => <option key={object.ref} value={object.ref}>{object.title}</option>)}</optgroup>)}
        </select></label>
        {field && <>
          {field.description && <p className={s.hint}>{field.description}</p>}
          <label>{t("Condition operator")}<select aria-label={t("Condition operator {number}", { number: index + 1 })} value={filter.operator} onChange={event => {
            const operator = event.target.value as FilterOperator;
            update(index, { operator, values: ["set", "notSet"].includes(operator) ? [] : multi && !["equals", "notEquals"].includes(operator) ? filter.values.slice(0, 1) : filter.values });
          }}>{!operators.includes(filter.operator) && <option value={filter.operator}>{filter.operator}</option>}{operators.map(operator => <option key={operator} value={operator}>{labels[operator]}</option>)}</select></label>
          {needsValue && <div className={s.values}>
            {values.map((current, valueIndex) => <label key={valueIndex}>{t("Filter value")}<div className={s.valueRow}>
              {field.data_type === "boolean" ? <select aria-label={t("Condition {number} value {value}", { number: index + 1, value: valueIndex + 1 })} value={current == null ? "" : String(current)} onChange={event => {
                const next = [...filter.values];
                if (event.target.value === "") next.splice(valueIndex, 1); else next[valueIndex] = filterValue(event.target.value, field.data_type);
                update(index, { values: next });
              }}><option value="">{t("Choose…")}</option><option value="true">{t("Yes")}</option><option value="false">{t("No")}</option></select>
                : <input aria-label={t("Condition {number} value {value}", { number: index + 1, value: valueIndex + 1 })} inputMode={field.data_type === "number" ? "decimal" : undefined} placeholder={t("Enter a value from the data")} value={current == null ? "" : String(current)} onChange={event => {
                  const next = [...filter.values]; next[valueIndex] = filterValue(event.target.value, field.data_type);
                  update(index, { values: event.target.value === "" && next.length <= 1 ? [] : next });
                }}/>}
              {values.length > 1 && <button type="button" className={s.remove} aria-label={t("Remove condition {number} value {value}", { number: index + 1, value: valueIndex + 1 })} onClick={() => update(index, { values: filter.values.filter((_, i) => i !== valueIndex) })}><X size={14}/></button>}
            </div></label>)}
            {multi && field.data_type !== "boolean" && filter.values.length > 0 && <button type="button" className={s.textButton} disabled={!completeFilters([filter], fields)} onClick={() => update(index, { values: [...filter.values, ""] })}><Plus size={13}/>{t("Add another value")}</button>}
            {filter.values.length > 1 && <p className={s.hint}>{filter.operator === "equals" ? t("Match any of these values.") : t("Exclude all of these values.")}</p>}
          </div>}
        </>}
      </section>;
    })}
    {filters.length > 0 && !completeFilters(filters, fields) && <p className={s.incomplete} role="status">{t("Complete each condition or remove it before saving or testing.")}</p>}
    <button type="button" className={s.add} onClick={() => onChange([...filters, { member: "", operator: "equals", values: [] }])}><Plus size={14}/>{t("Add condition")}</button>
  </fieldset>;
}
