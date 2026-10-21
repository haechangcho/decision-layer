"use client";

import { useT } from "@/lib/i18n";
import type { MethodManifest } from "@/lib/api";
import styles from "./method-content.module.css";

export function PythonInputContract({ method }: { method: MethodManifest }) {
  const t = useT();
  const tables = Object.entries(method.data_inputs || {});
  if (!tables.length) return <p className={styles.muted}>{t("This Method uses an advanced input adapter. For a new calculation, start with python_method and DataInput.")}</p>;
  return <section className={styles.inputContract} aria-label={t("Data passed to the function")}>
    <h3>{t("Data passed to the function")}</h3>
    <p>{t("At execution, connect Cube metrics, dimensions and dates. Data is queried and checked before it reaches the function.")}</p>
    {tables.map(([name, spec]) => <section key={name}>
      <h3><code>{name}</code> · {spec.format === "dataframe" ? "pandas DataFrame" : t("List of records")}</h3>
      <p>{spec.entity ? t("One row per entity bound to {entity}.", { entity: spec.entity })
        : spec.dimensions.length ? t("One row per {dimensions} combination.", { dimensions: spec.dimensions.join(" × ") })
        : t("One row for the overall aggregate.")}
        {spec.time_granularity && t(" One row per {period} period.", { period: spec.time_granularity })}
        {" "}{t("Minimum {count} rows.", { count: spec.minimum_rows })}</p>
      <div className={styles.contractScroll}><table><thead><tr><th>{t("Function column")}</th><th>{t("Execution binding")}</th></tr></thead><tbody>
        {spec.entity && !spec.columns?.[spec.entity] && <tr><td><code>unit</code></td><td>{t("{entity} · provider entity key", { entity: spec.entity })}</td></tr>}
        {spec.time_granularity && <tr><td><code>time</code></td><td>{t("Selected time dimension · {period}", { period: spec.time_granularity })}</td></tr>}
        {spec.dimensions.map(column => <tr key={column}><td><code>{column}</code></td><td>{t("{column} · dimension", { column })}</td></tr>)}
        {spec.measures.map(column => <tr key={column}><td><code>{column}</code></td><td>{t("{column} · measure", { column })}</td></tr>)}
        {Object.entries(spec.columns || {}).map(([column, role]) => <tr key={column}><td><code>{role.multiple ? `${column}_0, ${column}_1, …` : column}</code></td>
          <td>{column} · {(role.accepted_kinds || [role.kind]).map(kind => t(kind === "entity" ? "Entity identifier" : kind === "measure" ? "Measure" : "Dimension")).join(` ${t("or")} `)} · {t(role.required ? "required" : "optional")}</td></tr>)}
      </tbody></table></div>
      {!!spec.column_args?.length && <div>
        <h4>{t("Function column arguments")}</h4>
        <p>{t("These arguments are filled after querying the selected metrics and dimensions. They are not calculation options.")}</p>
        <ul>{spec.column_args.map(argument => <li key={argument}><code>{argument}</code>{" ← "}
          <code>{spec.columns?.[argument]?.multiple ? `["${argument}_0", "${argument}_1", …]` : `"${argument}"`}</code>
          {spec.columns?.[argument]?.required === false && <> {t("(empty list or None when omitted)")}</>}
        </li>)}</ul>
      </div>}
      <p>{t("Period:")} {spec.period_parameter ? t("{parameter} input ({role})", { parameter: spec.period_parameter, role: spec.period_role }) : t("The Run’s selected period")}.
        {" "}{t("Filters: Run scope")}{spec.filters_parameter && t(" + {parameter} input", { parameter: spec.filters_parameter })}.</p>
    </section>)}
    <p className={styles.muted}>{t("Resolve missing bindings before execution. Type and data checks do not establish business meaning, source completeness or causality.")}</p>
  </section>;
}
