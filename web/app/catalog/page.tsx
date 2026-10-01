"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, CheckCircle2, Database, Info, Search, ShieldCheck } from "lucide-react";

import { api, getSourceCallerToken, type SemanticCatalog, type SemanticObject, type SourceReadiness } from "@/lib/api";
import styles from "../catalog.module.css";

type CatalogMetric = SemanticObject & { cube: string; checks?: SourceReadiness["metrics"][number]["checks"] };

function getCube(ref: string) {
  return ref.split("/").at(-2) ?? "Cube";
}

function statusFor(metric: CatalogMetric) {
  if (!metric.checks) return { label: "점검 필요", ready: false };
  const missing = Object.values(metric.checks).some((check) => check.status === "missing");
  return { label: missing ? "일부 제한" : "분석 준비됨", ready: !missing };
}

export default function CatalogPage() {
  const [metrics, setMetrics] = useState<CatalogMetric[]>([]);
  const [selected, setSelected] = useState<CatalogMetric | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "ready" | "attention">("all");
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
      setError(cause instanceof Error ? cause.message : "Cube 카탈로그를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadCatalog(); }, []);

  const shown = useMemo(() => metrics.filter((metric) => {
    const status = statusFor(metric);
    const matchesFilter = filter === "all" || (filter === "ready" ? status.ready : !status.ready);
    const haystack = `${metric.title} ${metric.ref} ${metric.description ?? ""} ${metric.cube}`.toLowerCase();
    return matchesFilter && haystack.includes(search.trim().toLowerCase());
  }), [metrics, filter, search]);
  const groups = useMemo(() => shown.reduce<Record<string, CatalogMetric[]>>((all, metric) => {
    (all[metric.cube] ??= []).push(metric);
    return all;
  }, {}), [shown]);
  const readyCount = metrics.filter((metric) => statusFor(metric).ready).length;

  function methodHref(metric: CatalogMetric) {
    const method = metric.checks?.time.status === "ready" ? "query.trend" : "query.drilldown";
    return `/recipes/new?method=${method}&metric=${encodeURIComponent(metric.ref)}`;
  }

  return <div className={styles.page}>
    <div className={styles.heading}>
      <div><p className={styles.eyebrow}>SEMANTIC CATALOG</p><h1>지표 탐색</h1><p className={styles.intro}>Cube에서 관리하는 지표를 찾고, 분석 준비 상태를 확인하세요.</p></div>
      <Link className={styles.sourceLink} href="/sources"><Database size={16} />데이터 연결 설정</Link>
    </div>

    {error ? <section className={styles.empty} role="alert">
      <Info size={22} /><h2>카탈로그에 연결할 수 없습니다</h2><p>{error}</p>
      <p>Cube 주소와 사용자 토큰을 확인한 다음 다시 시도해 주세요.</p>
      <div className={styles.actions}><Link className={styles.primaryButton} href="/sources">연결 설정 열기 <ArrowRight size={16} /></Link><button className={styles.secondaryButton} onClick={() => void loadCatalog()}>다시 시도</button></div>
    </section> : loading ? <div className={styles.loading} role="status"><span className={styles.spinner} />Cube 카탈로그를 불러오는 중…</div> : metrics.length === 0 ? <section className={styles.empty}>
      <Database size={24} /><h2>공개된 지표가 없습니다</h2><p>Cube 모델에 measure를 추가하고, 현재 사용자에게 공개되어 있는지 확인해 주세요.</p>
      <Link className={styles.primaryButton} href="/sources">Cube 연결 확인 <ArrowRight size={16} /></Link>
    </section> : <div className={styles.workspace}>
      <section className={styles.catalog} aria-label="지표 카탈로그">
        <div className={styles.toolbar}><label className={styles.search}><Search size={17} /><input aria-label="지표 검색" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="이름, 설명 또는 Cube 검색" /></label><span className={styles.total}>{metrics.length}개 지표</span></div>
        <div className={styles.filters} role="group" aria-label="준비 상태 필터">
          {([ ["all", `전체 ${metrics.length}`], ["ready", `분석 준비됨 ${readyCount}`], ["attention", `확인 필요 ${metrics.length - readyCount}`] ] as const).map(([value, label]) => <button key={value} className={filter === value ? styles.activeFilter : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}
        </div>
        {Object.entries(groups).map(([cube, items]) => <section className={styles.group} key={cube} aria-label={`${cube} 지표`}>
          <h2><Database size={15} />{cube}<span>{items.length}</span></h2>
          {items.map((metric) => {
            const status = statusFor(metric);
            return <button key={metric.ref} className={`${styles.row} ${selected?.ref === metric.ref ? styles.selected : ""}`} onClick={() => setSelected(metric)} aria-pressed={selected?.ref === metric.ref}>
              <span className={styles.metricIcon}><Activity size={17} /></span>
              <span className={styles.metricCopy}><strong>{metric.title}</strong><small>{metric.description || metric.ref}</small></span>
              <span className={styles.kind}>{metric.metric_kind ?? "측정값"}</span>
              <span className={`${styles.status} ${status.ready ? styles.ready : styles.warning}`}><i />{status.label}</span>
            </button>;
          })}
        </section>)}
        {shown.length === 0 && <div className={styles.noResults}><Search size={22} /><strong>조건에 맞는 지표가 없습니다</strong><button onClick={() => { setSearch(""); setFilter("all"); }}>필터 초기화</button></div>}
      </section>

      <aside className={styles.detail} aria-label="지표 상세">
        {selected ? <>
          <div className={styles.detailHeader}><span className={styles.largeIcon}><Activity size={20} /></span><span className={styles.kindTag}>{selected.metric_kind ?? "측정값"}</span></div>
          <h2>{selected.title}</h2><p className={styles.description}>{selected.description || "Cube에 설명이 등록되지 않았습니다."}</p>
          <div className={styles.reference}><span>Cube 참조</span><code>{selected.ref}</code></div>
          <div className={styles.readinessTitle}><ShieldCheck size={16} /><strong>분석 준비 상태</strong></div>
          {!selected.checks ? <p className={styles.help}>준비 상태를 확인할 수 없어요. 연결 권한과 Cube 응답을 점검해 주세요.</p> : <ul className={styles.checks}>
            <li className={selected.checks.time.status === "missing" ? styles.checkWarning : ""}><span>시간 추이</span><strong>{selected.checks.time.status === "ready" ? "가능" : "확인 필요"}</strong></li>
            <li className={selected.checks.decomposition.status === "missing" ? styles.checkWarning : ""}><span>구성 분해</span><strong>{selected.checks.decomposition.status === "ready" ? "가능" : selected.checks.decomposition.status === "not_applicable" ? "해당 없음" : "확인 필요"}</strong></li>
            <li className={selected.checks.entity_key.status === "missing" ? styles.checkWarning : ""}><span>기본 키</span><strong>{selected.checks.entity_key.status === "ready" ? "가능" : "확인 필요"}</strong></li>
          </ul>}
          {selected.ratio_parts?.length ? <div className={styles.reference}><span>분자 / 분모</span><code>{selected.ratio_parts.join(" / ")}</code></div> : null}
          {selected.entity && <div className={styles.reference}><span>Entity key</span><code>{selected.entity}</code></div>}
          {selected.checks && [selected.checks.time.impact, selected.checks.decomposition.impact, selected.checks.entity_key.impact].filter(Boolean).map((impact) => <p className={styles.impact} key={impact}>{impact}</p>)}
          <Link className={styles.primaryButton} href={methodHref(selected)}>Recipe 만들기 <ArrowRight size={16} /></Link>
          <p className={styles.footnote}>분석 정의와 접근 권한은 Cube에서 관리합니다.</p>
        </> : <div className={styles.noSelection}>목록에서 지표를 선택하세요.</div>}
      </aside>
    </div>}
  </div>;
}
