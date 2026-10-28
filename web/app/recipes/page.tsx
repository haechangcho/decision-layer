"use client";
import { RequestError } from "@/components/request-error";
import { LoadingState } from "@/components/loading-indicator";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, BookOpen, Plus, Search, X } from "lucide-react";

import type { Recipe } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { RecipeDelete } from "@/features/recipes/recipe-delete";
import styles from "../library.module.css";

export default function RecipesPage() {
  const { data, error, loading, reload } = useApi<Recipe[]>("/recipes");
  const { data: drafts, reload: reloadDrafts } = useApi<Recipe[]>("/recipes:drafts");
  const [deleted, setDeleted] = useState("");
  const onDeleted = (recipe: Recipe) => { setDeleted(t("{name} archived", { name: recipe.description || recipe.name })); reload(); reloadDrafts(); };
  const { byRef } = useCatalog();
  const [search, setSearch] = useState("");
  const t = useT();
  const title = (ref: string) => byRef.get(ref)?.title ?? t("Metric name needs checking");
  const shown = useMemo(() => (data ?? []).filter((recipe) => {
    const text = `${recipe.name} ${recipe.description} ${recipe.semantic_scope.primary_metric} ${title(recipe.semantic_scope.primary_metric)} ${recipe.routing.use_for.join(" ")}`.toLowerCase();
    return text.includes(search.trim().toLowerCase());
  }), [data, search, byRef]);
  const repeated = new Map<string, number>();
  for (const recipe of data ?? []) repeated.set(recipe.description, (repeated.get(recipe.description) ?? 0) + 1);

  return <div className={styles.page}>
    <div className={styles.libraryHeader}>
      <div><h1>{t("Recipes")}</h1><p>{data ? t("{count} saved analyses", { count: data.length }) : t("Keep recurring analysis procedures in one place.")}</p></div>
      <Link className={styles.createLink} href="/recipes/new"><Plus size={16} />{t("New analysis procedure")}</Link>
    </div>
    {deleted && <p role="status">{deleted}</p>}
    {error && <RequestError title={t("Could not load the analysis procedures")} error={error} retry={reload} />}
    {error && !data ? null : data && !data.length && !drafts?.length && !loading ? <section className={styles.empty}>
      <BookOpen size={24} /><h2>{t("No analysis procedures yet")}</h2>
      <p>{t("Connect a semantic layer and choose a metric to start.")}</p>
      <div className={styles.emptyActions}><Link href="/catalog">{t("Explore metrics")} <ArrowRight size={15} /></Link><Link href="/recipes/new">{t("New analysis procedure")} <ArrowRight size={15} /></Link></div>
    </section> : <section className={styles.libraryList} aria-label={t("Recipes")}>
      <div className={styles.libraryToolbar}>
        <label className={styles.librarySearch}><Search size={17} /><input aria-label={t("Search analyses")} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("Search by purpose or metric")} />
          {search && <button type="button" onClick={() => setSearch("")} aria-label={t("Clear search")} title={t("Clear search")}><X size={15} /></button>}
        </label>
        <span className={styles.libraryCount}>{t("{count} results", { count: shown.length })}</span>
      </div>
      <div className={styles.libraryColumns} aria-hidden="true"><span>{t("Analysis procedure")}</span><span>{t("Primary metric")}</span><span>{t("Steps")}</span><span /></div>
      {loading && !data ? <LoadingState label={t("Loading analyses")} /> : shown.map((recipe) => <div key={recipe.name} className={styles.libraryItem}><Link className={styles.libraryRow} href={`/recipes/${encodeURIComponent(recipe.name)}`}>
        <span className={styles.libraryName}><strong>{recipe.description || recipe.name}</strong>{(repeated.get(recipe.description) ?? 0) > 1 && <small>{recipe.name}</small>}</span>
        <span className={styles.libraryMetric}>{title(recipe.semantic_scope.primary_metric)}</span>
        <span className={styles.librarySteps}>{recipe.mode === "pipeline" ? t("{count} steps", { count: recipe.steps.length }) : t("Guided exploration")}</span>
        <ArrowRight size={17} className={styles.libraryArrow} />
      </Link><RecipeDelete recipe={recipe} onDeleted={() => onDeleted(recipe)} /></div>)}
      {!loading && !error && shown.length === 0 && <div className={styles.libraryNoResults}><strong>{t("No matching analyses")}</strong><button type="button" className="ghost" onClick={() => setSearch("")}>{t("Clear search")}</button></div>}
    </section>}
    {!!drafts?.length && <section className={styles.libraryList} aria-label={t("Drafts in progress")}><div className={styles.libraryToolbar}><strong>{t("Drafts in progress")}</strong><span className={styles.libraryCount}>{t("{count} items", { count: drafts.length })}</span></div>
      {drafts.map((recipe) => <div key={recipe.name} className={styles.libraryItem}><Link className={styles.libraryRow} href={`/recipes/${encodeURIComponent(recipe.name)}/edit`}><span className={styles.libraryName}><strong>{recipe.description || recipe.name}</strong><small>v{recipe.version} · {t("Unpublished")}</small></span><span className={styles.libraryMetric}>{title(recipe.semantic_scope.primary_metric)}</span><span className={styles.librarySteps}>{t("{count} steps", { count: recipe.steps.length })}</span><ArrowRight size={17} className={styles.libraryArrow} /></Link><RecipeDelete recipe={recipe} onDeleted={() => onDeleted(recipe)} /></div>)}
    </section>}
  </div>;
}
