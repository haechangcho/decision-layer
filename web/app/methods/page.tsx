"use client";
import { useT } from "@/lib/i18n";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Code2, FileText, Search, X } from "lucide-react";
import { LoadingState } from "@/components/loading-indicator";
import { RequestError } from "@/components/request-error";
import type { MethodManifest } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { methodTitle, methodSummary } from "@/lib/method-name";
import styles from "../library.module.css";

const groups = [
  { key: "skill", title: "Skill", description: "AI follows the instructions to query data. Actual queries and responses are saved in the Run.", Icon: FileText },
  { key: "python", title: "Python", description: "Runs the registered function. Inspect its inputs, results and checks.", Icon: Code2 },
] as const;

export default function MethodsPage() {
  const t = useT();
  const { data, error, loading, reload } = useApi<MethodManifest[]>("/methods");
  const [search, setSearch] = useState("");
  const shown = useMemo(() => (data ?? []).filter(method =>
    `${method.name} ${methodTitle(method, t)} ${method.description}`
      .toLowerCase().includes(search.trim().toLowerCase())), [data, search, t]);

  return <div className={styles.page}>
    <div className={styles.libraryHeader}><div><h1>{t("Methods")}</h1><p>{t("Review a Method, then test it with real data.")}</p></div>
      <Link className={styles.createLink} href="/runs">{t("Runs")} <ArrowRight size={16} /></Link>
    </div>
    {error && <RequestError title={t("Could not load the Method")} error={error} retry={reload} />}
    {loading && !data ? <LoadingState /> : data && <>
      <div className={styles.methodToolbar}>
        <label className={styles.librarySearch}><Search size={17} />
          <input aria-label={t("Search Methods")} value={search} onChange={event => setSearch(event.target.value)} placeholder={t("Search by name or purpose")} />
          {search && <button aria-label={t("Clear search")} onClick={() => setSearch("")}><X size={15} /></button>}
        </label><span className={styles.libraryCount}>{t("{count} Methods", { count: shown.length })}</span>
      </div>
      {groups.map(({ key, title, description, Icon }) => {
        const methods = shown.filter(method => (method.implementation || "python") === key);
        if (!methods.length) return null;
        return <section key={key} className={styles.methodGroup} aria-label={t("{kind} Methods", { kind: title })}>
          <div className={styles.methodGroupHeading}><h2><Icon size={18} />{title}<span>{methods.length}</span></h2><p>{t(description)}</p></div>
          <div className={styles.libraryList}>
            {methods.map(method => <Link key={method.name} href={`/methods/${encodeURIComponent(method.name)}`} className={styles.methodRow}>
              <span className={styles.libraryName}><strong>{methodTitle(method, t)}</strong><small>{method.name}</small></span>
              <span className={styles.libraryMetric}>{methodSummary(method, t)}</span>
              <span className={styles.librarySteps}>v{method.version}</span><ArrowRight size={17} className={styles.libraryArrow} />
            </Link>)}
          </div>
        </section>;
      })}
      {shown.length === 0 && <div className={styles.empty}><h2>{data.length ? t("No search results") : t("No Methods registered")}</h2>
        {search && <button className="ghost" onClick={() => setSearch("")}>{t("Clear search")}</button>}
      </div>}
    </>}
  </div>;
}
