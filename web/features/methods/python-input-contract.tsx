"use client";

import { useT } from "@/lib/i18n";
import type { MethodManifest } from "@/lib/api";
import styles from "./method-content.module.css";

type Role = MethodManifest["roles"][string];

export function PythonInputContract({ method }: { method: MethodManifest }) {
  const t = useT();
  const tables = Object.entries(method.data_inputs || {});
  if (!tables.length) return null;

  function sourceLabel(role: Role) {
    if (role.kind === "entity") return t("Observation ID");
    const kinds = role.accepted_kinds || [role.kind];
    if (role.data_type === "number") {
      if (kinds.length > 1) return t("Numeric metric or dimension");
      return t(kinds[0] === "measure" ? "Numeric metric" : "Numeric dimension");
    }
    return kinds.map(kind => t(kind === "measure" ? "Measure" : "Dimension")).join(` ${t("or")} `);
  }

  return <div className={styles.inputContract}>
    <p className={styles.inputIntro}>{t("Choose analysis inputs. Set dates and filters at run time.")}</p>
    {tables.map(([name, spec]) => {
      const roles: Record<string, Role> = {
        ...Object.fromEntries(spec.measures.map(key => [key, method.roles[key]])),
        ...Object.fromEntries(spec.dimensions.map(key => [key, method.roles[key]])),
        ...spec.columns,
      };
      if (spec.entity && !roles[spec.entity]) roles[spec.entity] = method.roles[spec.entity];
      return <section key={name} className={styles.inputDataset} aria-label={name}>
        <div className={styles.inputSummary}>
          {tables.length > 1 && <code>{name}</code>}
          <span>{spec.entity ? t("One row per selected ID")
            : spec.dimensions.length ? t("One row per selected group") : t("One row for the overall aggregate.")}</span>
          {spec.minimum_rows > 1 && <span>{t("Minimum {count} rows.", { count: spec.minimum_rows })}</span>}
        </div>
        <dl className={styles.inputList}>{Object.entries(roles).filter(([, role]) => role).map(([key, role]) => <div key={key} className={styles.inputRow}>
          <dt><span>{role.description ? t(role.description) : role.label || key}</span><code>{key}</code></dt>
          <dd><span>{sourceLabel(role)}</span>{role.multiple && <span>{t("Select one or more")}</span>}{!role.required && <span>{t("optional")}</span>}</dd>
        </div>)}</dl>
        {(spec.period_parameter || spec.filters_parameter) && <p className={styles.muted}>
          {spec.period_parameter && <span>{t("Additional period")}: <code>{spec.period_parameter}</code>{" "}</span>}
          {spec.filters_parameter && <span>{t("Additional filters")}: <code>{spec.filters_parameter}</code></span>}
        </p>}
      </section>;
    })}
  </div>;
}
