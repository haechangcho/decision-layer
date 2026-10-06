"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, BookOpen, Plus, Search, X } from "lucide-react";

import type { Recipe } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { RecipeDelete } from "@/components/recipe-delete";
import styles from "../library.module.css";

export default function RecipesPage() {
  const { data, error, loading, reload } = useApi<Recipe[]>("/recipes");
  const { data: drafts, reload: reloadDrafts } = useApi<Recipe[]>("/recipes:drafts");
  const [deleted, setDeleted] = useState("");
  const onDeleted = (recipe: Recipe) => { setDeleted(`${recipe.description || recipe.name} 삭제됨`); reload(); reloadDrafts(); };
  const { byRef } = useCatalog();
  const [search, setSearch] = useState("");
  const t = useT();
  const title = (ref: string) => byRef.get(ref)?.title ?? "지표 이름 확인 필요";
  const shown = useMemo(() => (data ?? []).filter((recipe) => {
    const text = `${recipe.name} ${recipe.description} ${recipe.semantic_scope.primary_metric} ${title(recipe.semantic_scope.primary_metric)} ${recipe.routing.use_for.join(" ")}`.toLowerCase();
    return text.includes(search.trim().toLowerCase());
  }), [data, search, byRef]);
  const repeated = new Map<string, number>();
  for (const recipe of data ?? []) repeated.set(recipe.description, (repeated.get(recipe.description) ?? 0) + 1);

  return <div className={styles.page}>
    <div className={styles.libraryHeader}>
      <div><h1>{t("Analysis library")}</h1><p>{t("{count} saved analyses", { count: data?.length ?? 0 })}</p></div>
      <Link className={styles.createLink} href="/recipes/new"><Plus size={16} />{t("New analysis procedure")}</Link>
    </div>
    {deleted && <p role="status">{deleted}</p>}
    {error && <div className={styles.error} role="alert">{t("Could not load analyses.")} {error.message} <button className="ghost" onClick={reload}>{t("Retry")}</button></div>}
    {data && !data.length && !drafts?.length && !loading ? <section className={styles.empty}>
      <BookOpen size={24} /><h2>{t("No analysis procedures yet")}</h2>
      <p>{t("Connect a semantic layer and choose a metric to create the first one.")}</p>
      <div className={styles.emptyActions}><Link href="/catalog">{t("Explore metrics")} <ArrowRight size={15} /></Link><Link href="/recipes/new">{t("New analysis procedure")} <ArrowRight size={15} /></Link></div>
    </section> : <section className={styles.libraryList} aria-label={t("Analysis library")}>
      <div className={styles.libraryToolbar}>
        <label className={styles.librarySearch}><Search size={17} /><input aria-label={t("Search analyses")} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("Search by purpose or metric")} />
          {search && <button type="button" onClick={() => setSearch("")} aria-label={t("Clear search")} title={t("Clear search")}><X size={15} /></button>}
        </label>
        <span className={styles.libraryCount}>{t("{count} results", { count: shown.length })}</span>
      </div>
      <div className={styles.libraryColumns} aria-hidden="true"><span>{t("Analysis procedure")}</span><span>{t("Primary metric")}</span><span>{t("Steps")}</span><span /></div>
      {loading && !data ? <div aria-label={t("Loading analyses")}>{[0, 1, 2, 3].map((row) => <div className={styles.skeleton} key={row} />)}</div> : shown.map((recipe) => <div key={recipe.name} className={styles.libraryItem}><Link className={styles.libraryRow} href={`/recipes/${encodeURIComponent(recipe.name)}`}>
        <span className={styles.libraryName}><strong>{recipe.description || recipe.name}</strong>{(repeated.get(recipe.description) ?? 0) > 1 && <small>{recipe.name}</small>}</span>
        <span className={styles.libraryMetric}>{title(recipe.semantic_scope.primary_metric)}</span>
        <span className={styles.librarySteps}>{recipe.mode === "pipeline" ? t("{count} steps", { count: recipe.steps.length }) : t("Guided exploration")}</span>
        <ArrowRight size={17} className={styles.libraryArrow} />
      </Link><RecipeDelete recipe={recipe} onDeleted={() => onDeleted(recipe)} /></div>)}
      {!loading && !error && shown.length === 0 && <div className={styles.libraryNoResults}><strong>{t("No matching analyses")}</strong><button type="button" className="ghost" onClick={() => setSearch("")}>{t("Clear search")}</button></div>}
    </section>}
    {!!drafts?.length && <section className={styles.libraryList} aria-label="작성 중인 초안"><div className={styles.libraryToolbar}><strong>작성 중인 초안</strong><span className={styles.libraryCount}>{drafts.length}개</span></div>
      {drafts.map((recipe) => <div key={recipe.name} className={styles.libraryItem}><Link className={styles.libraryRow} href={`/recipes/${encodeURIComponent(recipe.name)}/edit`}><span className={styles.libraryName}><strong>{recipe.description || recipe.name}</strong><small>v{recipe.version} · 발행 전</small></span><span className={styles.libraryMetric}>{title(recipe.semantic_scope.primary_metric)}</span><span className={styles.librarySteps}>{recipe.steps.length}단계</span><ArrowRight size={17} className={styles.libraryArrow} /></Link><RecipeDelete recipe={recipe} onDeleted={() => onDeleted(recipe)} /></div>)}
    </section>}
  </div>;
}
