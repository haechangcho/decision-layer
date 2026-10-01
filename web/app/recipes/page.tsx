"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, BookOpen, Plus, Search, Sparkles } from "lucide-react";

import type { Recipe } from "@/lib/api";
import { useApi, useCatalog } from "@/lib/hooks";
import styles from "../library.module.css";

const humanize = (value: string) => value.replaceAll("_", " ").replaceAll(".", " · ");

export default function RecipesPage() {
  const { data, error, loading, reload } = useApi<Recipe[]>("/recipes");
  const { byRef } = useCatalog();
  const [search, setSearch] = useState("");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const title = (ref: string) => byRef.get(ref)?.title ?? ref;
  const shown = useMemo(() => (data ?? []).filter((recipe) => {
    const text = `${recipe.name} ${recipe.description} ${recipe.semantic_scope.primary_metric} ${title(recipe.semantic_scope.primary_metric)} ${recipe.routing.use_for.join(" ")}`.toLowerCase();
    return text.includes(search.trim().toLowerCase());
  }), [data, search, byRef]);
  const selected = shown.find((recipe) => recipe.name === selectedName) ?? shown[0] ?? null;

  useEffect(() => {
    if (selected && selected.name !== selectedName) setSelectedName(selected.name);
  }, [selected, selectedName]);

  return <div className={styles.page}>
    <div className={styles.heading}><div><p className={styles.eyebrow}>ANALYSIS PLAYBOOKS</p><h1>분석 Recipe</h1></div><Link className={styles.primary} href="/recipes/new"><Plus size={16} />새 Recipe</Link></div>
    {error && <div className={styles.error} role="alert">Recipe를 불러오지 못했습니다. {error.message} <Link href="/sources">Cube 연결 확인</Link> <button className="ghost" onClick={reload}>다시 시도</button></div>}
    {data && !data.length && !loading ? <section className={styles.empty}>
      <BookOpen size={24} /><h2>등록된 분석 Recipe가 없습니다</h2><Link href="/recipes/new">첫 Recipe 만들기 <ArrowRight size={15} /></Link><Link href="/catalog">연결된 지표 보기 <ArrowRight size={15} /></Link>
    </section> : <div className={styles.layout}>
      <section className={styles.list} aria-label="분석 Recipe 목록">
        <div className={styles.toolbar}><label className={styles.search}><Search size={17} /><input aria-label="Recipe 검색" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="이름, 설명 또는 지표 검색" /></label><span className={styles.count}>{data?.length ?? 0}개 Recipe</span></div>
        {loading && !data ? <div aria-label="불러오는 중">{[0, 1, 2].map((row) => <div className={styles.skeleton} key={row} />)}</div> : shown.map((recipe) => <button key={recipe.name} className={`${styles.row} ${selected?.name === recipe.name ? styles.selected : ""}`} onClick={() => setSelectedName(recipe.name)} aria-pressed={selected?.name === recipe.name}>
          <span className={styles.icon}><BookOpen size={17} /></span><span className={styles.copy}><strong>{recipe.description || recipe.name}</strong><small>{title(recipe.semantic_scope.primary_metric)}</small></span><span className={styles.badge}>{recipe.mode === "pipeline" ? `${recipe.steps.length}단계` : "MCP 탐색"}</span>
        </button>)}
        {!loading && !error && shown.length === 0 && <div className={styles.noResults}>조건에 맞는 Recipe가 없습니다.</div>}
      </section>
      <aside className={styles.detail} aria-label="Recipe 상세">
        {selected ? <>
          <div className={styles.detailHeader}><span className={styles.icon}><BookOpen size={18} /></span><span className={styles.badge}>v{selected.version}</span></div>
          <h2>{selected.description || selected.name}</h2>
          <dl className={styles.meta}>
            <div className={styles.metaRow}><dt>분석 절차</dt><dd>{selected.mode === "pipeline" ? `${selected.steps.length}단계` : "MCP에서 결과에 따라 다음 분석 선택"}</dd></div>
            <div className={styles.metaRow}><dt>검증 항목</dt><dd>{selected.validators.length ? selected.validators.map((validator) => humanize(validator.name)).join(", ") : "없음"}</dd></div>
          </dl>
          <h3 className={styles.sectionTitle}>중심 지표</h3><div className={styles.tags}><span className={styles.tag}>{title(selected.semantic_scope.primary_metric)}</span></div>
          {selected.semantic_scope.related_metrics.length > 0 && <><h3 className={styles.sectionTitle}>함께 살펴보는 지표</h3><div className={styles.tags}>{selected.semantic_scope.related_metrics.map((ref) => <span className={styles.tag} key={ref}>{title(ref)}</span>)}</div></>}
          {selected.semantic_scope.preferred_dimensions.length > 0 && <><h3 className={styles.sectionTitle}>주요 분류 기준</h3><div className={styles.tags}>{selected.semantic_scope.preferred_dimensions.map((ref) => <span className={styles.tag} key={ref}>{title(ref)}</span>)}</div></>}
          <h3 className={styles.sectionTitle}>사용할 분석 방법</h3><div className={styles.tags}>{(selected.mode === "pipeline" ? selected.steps.map((step) => step.method) : selected.allowed_methods).map((method, index) => <span className={styles.tag} key={`${method}-${index}`}>{humanize(method)}</span>)}</div>
          <Link className={styles.primary} href={`/recipes/${encodeURIComponent(selected.name)}`}>이 Recipe로 분석 <ArrowRight size={16} /></Link>
          <Link className={styles.secondaryLink} href={`/recipes/${encodeURIComponent(selected.name)}/edit`}>Recipe 편집</Link>
        </> : <div className={styles.empty}><Sparkles size={22} /><h2>{loading ? "Recipe를 불러오는 중" : "Recipe를 선택하세요"}</h2><p>목록에서 분석 절차를 선택하면 대상 지표와 진행 방식을 확인할 수 있습니다.</p></div>}
      </aside>
    </div>}
  </div>;
}
