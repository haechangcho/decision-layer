"use client";
import { LoadingState } from "@/components/loading-indicator";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Search, X } from "lucide-react";

import type { MethodManifest } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { methodName } from "@/lib/method-name";
import styles from "../library.module.css";

export default function MethodsPage() {
  const t = useT();
  const { data, error, loading, reload } = useApi<MethodManifest[]>("/methods");
  const [search, setSearch] = useState("");
  const shown = useMemo(() => (data ?? []).filter((method) =>
    `${method.name} ${method.label || methodName(method.name, t)} ${method.description} ${method.kind}`.toLowerCase().includes(search.trim().toLowerCase())), [data, search, t]);

  return <div className={styles.page}>
    <div className={styles.libraryHeader}><div><h1>{t("Methods")}</h1><p>{t("{count} registered Methods", { count: data?.length ?? 0 })}</p></div></div>
    {error && <div className={styles.error} role="alert">{t("Could not load Methods.")} {error.message} <button className="ghost" onClick={reload}>{t("Retry")}</button></div>}
    <section className={styles.libraryList} aria-label={t("Method list")}>
      <div className={styles.libraryToolbar}>
        <label className={styles.librarySearch}><Search size={17} /><input aria-label={t("Search Methods")} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("Search by name or purpose")} />
          {search && <button type="button" aria-label={t("Clear search")} title={t("Clear search")} onClick={() => setSearch("")}><X size={15} /></button>}
        </label>
        <span className={styles.libraryCount}>{t("{count} results", { count: shown.length })}</span>
      </div>
      <div className={styles.libraryColumns} aria-hidden="true"><span>{t("Methods")}</span><span>{t("Description")}</span><span>{t("Version")}</span><span /></div>
      {loading && !data ? <LoadingState /> : shown.map((method) => <Link key={method.name} href={`/methods/${encodeURIComponent(method.name)}`} className={styles.libraryRow}>
        <span className={styles.libraryName}><strong>{method.label || methodName(method.name, t)}</strong><small>{method.name}</small></span>
        <span className={styles.libraryMetric}>{method.description.split(". ")[0].replace(/\.$/, "") + "."}</span>
        <span className={styles.librarySteps}>v{method.version}</span>
        <ArrowRight size={17} className={styles.libraryArrow} />
      </Link>)}
      {!loading && !error && shown.length === 0 && <div className={styles.libraryNoResults}><strong>{t("No matching Methods")}</strong><button className="ghost" type="button" onClick={() => setSearch("")}>{t("Clear search")}</button></div>}
    </section>
  </div>;
}
