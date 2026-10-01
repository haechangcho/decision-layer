"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Search, ShieldCheck, SlidersHorizontal, Workflow } from "lucide-react";

import type { MethodManifest } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import styles from "../library.module.css";

const humanize = (value: string) => value.replaceAll("_", " ").replaceAll(".", " · ");

export default function MethodsPage() {
  const { data, error, loading, reload } = useApi<MethodManifest[]>("/methods");
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("all");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const kinds = useMemo(() => [...new Set((data ?? []).map((method) => method.kind))].sort(), [data]);
  const shown = useMemo(() => (data ?? []).filter((method) => {
    const text = `${method.name} ${method.description} ${method.kind} ${method.interpretation}`.toLowerCase();
    return (kind === "all" || method.kind === kind) && text.includes(search.trim().toLowerCase());
  }), [data, kind, search]);
  const selected = shown.find((method) => method.name === selectedName) ?? shown[0] ?? null;

  useEffect(() => {
    if (selected && selected.name !== selectedName) setSelectedName(selected.name);
  }, [selected, selectedName]);

  return <div className={styles.page}>
    <div className={styles.heading}><div><p className={styles.eyebrow}>METHOD REGISTRY</p><h1>분석 방법</h1></div></div>
    {error && <div className={styles.error} role="alert">목록을 불러오지 못했습니다. {error.message} <button className="ghost" onClick={reload}>다시 시도</button></div>}
    <div className={styles.layout}>
      <section className={styles.list} aria-label="분석 방법 목록">
        <div className={styles.toolbar}><label className={styles.search}><Search size={17} /><input aria-label="분석 방법 검색" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="이름, 목적 또는 해석 방식 검색" /></label><span className={styles.count}>{data?.length ?? 0}개 방법</span></div>
        <div className={styles.filters} role="group" aria-label="방법 종류">
          {[...["all"], ...kinds].map((value) => <button key={value} className={kind === value ? styles.active : ""} aria-pressed={kind === value} onClick={() => setKind(value)}>{value === "all" ? `전체 ${data?.length ?? 0}` : humanize(value)}</button>)}
        </div>
        {loading && !data ? <div aria-label="불러오는 중">{[0, 1, 2, 3].map((row) => <div className={styles.skeleton} key={row} />)}</div> : shown.map((method) => <button key={method.name} className={`${styles.row} ${selected?.name === method.name ? styles.selected : ""}`} onClick={() => setSelectedName(method.name)} aria-pressed={selected?.name === method.name}>
          <span className={styles.icon}><Workflow size={17} /></span><span className={styles.copy}><strong>{method.name}</strong><small>{method.description}</small></span><span className={styles.badge}>{humanize(method.kind)}</span>
        </button>)}
        {!loading && !error && shown.length === 0 && <div className={styles.noResults}>조건에 맞는 방법이 없습니다.</div>}
      </section>
      <aside className={styles.detail} aria-label="분석 방법 상세">
        {selected ? <>
          <div className={styles.detailHeader}><span className={styles.icon}><Workflow size={18} /></span><span className={styles.badge}>{humanize(selected.interpretation)}</span></div>
          <h2>{selected.name}</h2><p className={styles.description}>{selected.description}</p>
          <dl className={styles.meta}>
            <div className={styles.metaRow}><dt>버전</dt><dd>{selected.version}</dd></div>
            <div className={styles.metaRow}><dt>실행 방식</dt><dd>{humanize(selected.execution)}</dd></div>
            <div className={styles.metaRow}><dt>입력 항목</dt><dd>{Object.keys(selected.roles).length}개 역할 · {Object.keys(selected.parameters).length}개 옵션</dd></div>
          </dl>
          <h3 className={styles.sectionTitle}>필요한 입력</h3>
          <div className={styles.tags}>{Object.entries(selected.roles).map(([name, role]) => <span className={styles.tag} key={name}>{humanize(name)} · {role.kind}{role.multiple ? " 여러 개" : ""}{role.required ? " · 필수" : ""}</span>)}</div>
          <h3 className={styles.sectionTitle}>결과</h3><div className={styles.tags}>{selected.outputs.map((output) => <span className={styles.tag} key={output}>{humanize(output)}</span>)}</div>
          <Link className={styles.primary} href={`/recipes/new?method=${encodeURIComponent(selected.name)}`}>이 방법으로 Recipe 만들기 <ArrowRight size={16} /></Link>
          <Link href={`/methods/${selected.name}`}>방법 명세 보기</Link>
        </> : <div className={styles.empty}><SlidersHorizontal size={22} /><h2>{loading ? "방법을 불러오는 중" : "등록된 분석 방법이 없습니다"}</h2><p>방법이 준비되면 여기에서 입력 조건과 결과를 확인할 수 있습니다.</p></div>}
      </aside>
    </div>
  </div>;
}
