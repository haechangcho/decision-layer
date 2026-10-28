"use client";
import { InspectorDialog } from "@/components/inspector-dialog";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, Database, Info, Search, X } from "lucide-react";

import { api, getSourceCallerToken, type SemanticCatalog, type SemanticObject, type SourceReadiness } from "@/lib/api";
import { LoadingIndicator } from "@/components/loading-indicator";
import { useT } from "@/lib/i18n";
import styles from "../catalog.module.css";

type CatalogMetric = SemanticObject & { cube: string; checks?: SourceReadiness["metrics"][number]["checks"] };

function getCube(ref: string) {
  return ref.split("/").at(-2) ?? "Cube";
}

export default function CatalogPage() {
  const t = useT();
  const [technicalOpen, setTechnicalOpen] = useState(false);
  const [metrics, setMetrics] = useState<CatalogMetric[]>([]);
  const [selected, setSelected] = useState<CatalogMetric | null>(null);
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadCatalog() {
    setLoading(true);
    setError("");
    const callerToken = getSourceCallerToken();
    try {
      const [catalog, readiness] = await Promise.all([
        api<SemanticCatalog>("/semantic/catalog", { callerToken }),
        api<SourceReadiness>("/sources/current/readiness", { callerToken }).catch(() => null),
      ]);
      const checks = new Map((readiness?.metrics ?? []).map((item) => [item.metric.ref, item.checks]));
      const found = catalog.objects.filter((object) => object.kind === "measure").map((object) => ({
        ...object,
        cube: getCube(object.ref),
        checks: checks.get(object.ref),
      }));
      setMetrics(found);
      setSelected((current) => found.find((metric) => metric.ref === current?.ref) ?? found[0] ?? null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("Could not load the metric catalog."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadCatalog(); }, []);
  useEffect(() => {
    if (!mobileDetailOpen) return;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") setMobileDetailOpen(false); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mobileDetailOpen]);

  const shown = useMemo(() => metrics.filter((metric) => {
    const haystack = `${metric.title} ${metric.ref} ${metric.description ?? ""} ${metric.cube}`.toLowerCase();
    return haystack.includes(search.trim().toLowerCase());
  }), [metrics, search]);
  const groups = useMemo(() => shown.reduce<Record<string, CatalogMetric[]>>((all, metric) => {
    (all[metric.cube] ??= []).push(metric);
    return all;
  }, {}), [shown]);

  function methodHref(metric: CatalogMetric) {
    const method = "analysis.metric_lookup";
    return `/recipes/new?method=${method}&metric=${encodeURIComponent(metric.ref)}`;
  }

  return <div className={styles.page}>
    <div className={styles.heading}>
      <div><h1>{t("Metric catalog")}</h1><p className={styles.intro}>{t("Review the metrics and definitions in the connected semantic layer.")}</p></div>
      <Link className={styles.sourceLink} href="/sources"><Database size={16} />{t("Data connection settings")}</Link>
    </div>

    {error ? <section className={styles.empty} role="alert">
      <Info size={22} /><h2>{t("Cannot connect to the catalog")}</h2><p>{error}</p>
      <p>{t("Check the connection address and access permissions, then try again.")}</p>
      <div className={styles.actions}><Link className={styles.primaryButton} href="/sources">{t("Open connection settings")} <ArrowRight size={16} /></Link><button className={styles.secondaryButton} onClick={() => void loadCatalog()}>{t("Retry")}</button></div>
    </section> : loading ? <div className={styles.loading} role="status"><LoadingIndicator />{t("Loading the metric catalog…")}</div> : metrics.length === 0 ? <section className={styles.empty}>
      <Database size={24} /><h2>{t("No visible metrics")}</h2><p>{t("Check metric definitions and your access in the semantic model.")}</p>
      <Link className={styles.primaryButton} href="/sources">{t("Check connection")} <ArrowRight size={16} /></Link>
    </section> : <div className={styles.workspace}>
      <section className={styles.catalog} aria-label={t("Catalog metrics")}>
        <div className={styles.toolbar}><label className={styles.search}><Search size={17} /><input aria-label={t("Search metrics")} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("Search by name, description or model")} /></label><span className={styles.total}>{t("{count} metrics", { count: metrics.length })}</span></div>
        {Object.entries(groups).map(([cube, items]) => <section className={styles.group} key={cube} aria-label={t("{model} metrics", { model: cube })}>
          <h2><Database size={15} />{cube}<span>{items.length}</span></h2>
          {items.map((metric) => {
            return <button key={metric.ref} className={`${styles.row} ${selected?.ref === metric.ref ? styles.selected : ""}`} onClick={() => { setSelected(metric); setMobileDetailOpen(true); }} aria-pressed={selected?.ref === metric.ref}>
              <span className={styles.metricIcon}><Activity size={17} /></span>
              <span className={styles.metricCopy}><strong>{metric.title}</strong>{metric.description && <small>{metric.description}</small>}</span>
              <span className={styles.kind}>{metric.metric_kind ?? t("Measure")}</span>
            </button>;
          })}
        </section>)}
        {shown.length === 0 && <div className={styles.noResults}><Search size={22} /><strong>{t("No metrics match")}</strong><button onClick={() => setSearch("")}>{t("Reset search")}</button></div>}
      </section>

      {mobileDetailOpen && <button type="button" className={styles.mobileBackdrop} onClick={() => setMobileDetailOpen(false)} aria-label={t("Close metric details")} />}
      <aside className={`${styles.detail} ${mobileDetailOpen ? styles.detailMobileOpen : ""}`} aria-label={t("Metric details")}>
        {selected ? <>
          <div className={styles.detailHeader}><span className={styles.largeIcon}><Activity size={20} /></span><span className={styles.kindTag}>{selected.metric_kind ?? t("Measure")}</span><button type="button" className={styles.mobileClose} onClick={() => setMobileDetailOpen(false)} aria-label={t("Close")}><X size={19} /></button></div>
          <h2>{selected.title}</h2><p className={styles.description}>{selected.description || t("No description is registered in the semantic model.")}</p>
          <button type="button" className="ghost" onClick={() => setTechnicalOpen(true)}>{t("View technical details")}</button><InspectorDialog title={t("Metric technical details")} open={technicalOpen} onClose={() => setTechnicalOpen(false)}><div className={styles.reference}><span>{t("Metric reference")}</span><code>{selected.ref}</code></div>
            {selected.ratio_parts?.length ? <div className={styles.reference}><span>{t("Numerator / denominator")}</span><code>{selected.ratio_parts.join(" / ")}</code></div> : null}
            {selected.entity && <div className={styles.reference}><span>{t("Analysis unit reference")}</span><code>{selected.entity}</code></div>}</InspectorDialog>
          <div className={styles.readinessTitle}><Info size={16} /><strong>{t("Confirmed in the model")}</strong></div>
          {!selected.checks ? <p className={styles.help}>{t("Model details unavailable. Execution will check the required inputs.")}</p> : <ul className={styles.checks}>
            <li><span>{t("Time dimension")}</span><strong>{selected.checks.time.status === "ready" ? t("Registered") : t("Not confirmed")}</strong></li>
            {(selected.metric_kind === "ratio" || selected.checks.decomposition.status !== "not_applicable") && <li><span>{t("Numerator / denominator")}</span><strong>{selected.checks.decomposition.status === "ready" ? t("Registered") : t("Not confirmed")}</strong></li>}
          </ul>}
          <Link className={styles.primaryButton} href={methodHref(selected)}>{t("Create Recipe")} <ArrowRight size={16} /></Link>
          <p className={styles.footnote}>{t("The semantic layer manages metric definitions and access.")}</p>
        </> : <div className={styles.noSelection}>{t("Choose a metric from the list.")}</div>}
      </aside>
    </div>}
  </div>;
}
