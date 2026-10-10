"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, Database, Info, Search, X } from "lucide-react";

import { api, getSourceCallerToken, type SemanticCatalog, type SemanticObject, type SourceReadiness } from "@/lib/api";
import { LoadingIndicator } from "@/components/loading-indicator";
import styles from "../catalog.module.css";

type CatalogMetric = SemanticObject & { cube: string; checks?: SourceReadiness["metrics"][number]["checks"] };

function getCube(ref: string) {
  return ref.split("/").at(-2) ?? "Cube";
}

export default function CatalogPage() {
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
      setError(cause instanceof Error ? cause.message : "지표 카탈로그를 불러오지 못했습니다.");
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
    const method = metric.checks?.time.status === "ready" ? "query.trend" : "query.drilldown";
    return `/recipes/new?method=${method}&metric=${encodeURIComponent(metric.ref)}`;
  }

  return <div className={styles.page}>
    <div className={styles.heading}>
      <div><h1>지표 탐색</h1><p className={styles.intro}>연결된 시맨틱 레이어의 지표와 정의를 확인하세요.</p></div>
      <Link className={styles.sourceLink} href="/sources"><Database size={16} />데이터 연결 설정</Link>
    </div>

    {error ? <section className={styles.empty} role="alert">
      <Info size={22} /><h2>카탈로그에 연결할 수 없습니다</h2><p>{error}</p>
      <p>연결 주소와 접근 권한을 확인한 다음 다시 시도해 주세요.</p>
      <div className={styles.actions}><Link className={styles.primaryButton} href="/sources">연결 설정 열기 <ArrowRight size={16} /></Link><button className={styles.secondaryButton} onClick={() => void loadCatalog()}>다시 시도</button></div>
    </section> : loading ? <div className={styles.loading} role="status"><LoadingIndicator />지표 카탈로그를 불러오는 중…</div> : metrics.length === 0 ? <section className={styles.empty}>
      <Database size={24} /><h2>공개된 지표가 없습니다</h2><p>시맨틱 모델에 지표를 등록하고, 현재 사용자에게 공개되어 있는지 확인해 주세요.</p>
      <Link className={styles.primaryButton} href="/sources">연결 확인 <ArrowRight size={16} /></Link>
    </section> : <div className={styles.workspace}>
      <section className={styles.catalog} aria-label="지표 카탈로그">
        <div className={styles.toolbar}><label className={styles.search}><Search size={17} /><input aria-label="지표 검색" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="이름, 설명 또는 모델 검색" /></label><span className={styles.total}>{metrics.length}개 지표</span></div>
        {Object.entries(groups).map(([cube, items]) => <section className={styles.group} key={cube} aria-label={`${cube} 지표`}>
          <h2><Database size={15} />{cube}<span>{items.length}</span></h2>
          {items.map((metric) => {
            return <button key={metric.ref} className={`${styles.row} ${selected?.ref === metric.ref ? styles.selected : ""}`} onClick={() => { setSelected(metric); setMobileDetailOpen(true); }} aria-pressed={selected?.ref === metric.ref}>
              <span className={styles.metricIcon}><Activity size={17} /></span>
              <span className={styles.metricCopy}><strong>{metric.title}</strong>{metric.description && <small>{metric.description}</small>}</span>
              <span className={styles.kind}>{metric.metric_kind ?? "측정값"}</span>
            </button>;
          })}
        </section>)}
        {shown.length === 0 && <div className={styles.noResults}><Search size={22} /><strong>조건에 맞는 지표가 없습니다</strong><button onClick={() => setSearch("")}>검색 초기화</button></div>}
      </section>

      {mobileDetailOpen && <button type="button" className={styles.mobileBackdrop} onClick={() => setMobileDetailOpen(false)} aria-label="지표 상세 닫기" />}
      <aside className={`${styles.detail} ${mobileDetailOpen ? styles.detailMobileOpen : ""}`} aria-label="지표 상세">
        {selected ? <>
          <div className={styles.detailHeader}><span className={styles.largeIcon}><Activity size={20} /></span><span className={styles.kindTag}>{selected.metric_kind ?? "측정값"}</span><button type="button" className={styles.mobileClose} onClick={() => setMobileDetailOpen(false)} aria-label="닫기"><X size={19} /></button></div>
          <h2>{selected.title}</h2><p className={styles.description}>{selected.description || "시맨틱 모델에 설명이 등록되지 않았습니다."}</p>
          <details className={styles.technicalDetails}><summary>기술 정보</summary><div className={styles.reference}><span>지표 참조</span><code>{selected.ref}</code></div>
            {selected.ratio_parts?.length ? <div className={styles.reference}><span>분자 / 분모</span><code>{selected.ratio_parts.join(" / ")}</code></div> : null}
            {selected.entity && <div className={styles.reference}><span>개별 분석 단위 참조</span><code>{selected.entity}</code></div>}</details>
          <div className={styles.readinessTitle}><Info size={16} /><strong>모델에서 확인한 정보</strong></div>
          {!selected.checks ? <p className={styles.help}>추가 모델 정보를 불러오지 못했습니다. 분석 가능 여부는 실행할 때 확인합니다.</p> : <ul className={styles.checks}>
            <li><span>시간 차원</span><strong>{selected.checks.time.status === "ready" ? "등록됨" : "확인되지 않음"}</strong></li>
            {(selected.metric_kind === "ratio" || selected.checks.decomposition.status !== "not_applicable") && <li><span>분자 / 분모</span><strong>{selected.checks.decomposition.status === "ready" ? "등록됨" : "확인되지 않음"}</strong></li>}
          </ul>}
          <Link className={styles.primaryButton} href={methodHref(selected)}>Recipe 만들기 <ArrowRight size={16} /></Link>
          <p className={styles.footnote}>지표 정의와 데이터 접근 권한은 연결된 시맨틱 레이어에서 관리합니다.</p>
        </> : <div className={styles.noSelection}>목록에서 지표를 선택하세요.</div>}
      </aside>
    </div>}
  </div>;
}
