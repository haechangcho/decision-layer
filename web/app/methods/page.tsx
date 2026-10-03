"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Search, X } from "lucide-react";

import type { MethodManifest } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { methodName } from "@/lib/method-name";
import styles from "../library.module.css";

export default function MethodsPage() {
  const { data, error, loading, reload } = useApi<MethodManifest[]>("/methods");
  const [search, setSearch] = useState("");
  const shown = useMemo(() => (data ?? []).filter((method) =>
    `${method.name} ${methodName(method.name)} ${method.description} ${method.kind}`.toLowerCase().includes(search.trim().toLowerCase())), [data, search]);

  return <div className={styles.page}>
    <div className={styles.libraryHeader}><div><h1>분석 방법</h1><p>등록된 방법 {data?.length ?? 0}개</p></div></div>
    {error && <div className={styles.error} role="alert">분석 방법을 불러오지 못했습니다. {error.message} <button className="ghost" onClick={reload}>다시 시도</button></div>}
    <section className={styles.libraryList} aria-label="분석 방법 목록">
      <div className={styles.libraryToolbar}>
        <label className={styles.librarySearch}><Search size={17} /><input aria-label="분석 방법 검색" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="이름 또는 목적 검색" />
          {search && <button type="button" aria-label="검색 지우기" title="검색 지우기" onClick={() => setSearch("")}><X size={15} /></button>}
        </label>
        <span className={styles.libraryCount}>{shown.length}개 결과</span>
      </div>
      <div className={styles.libraryColumns} aria-hidden="true"><span>분석 방법</span><span>설명</span><span>버전</span><span /></div>
      {loading && !data ? <div aria-label="불러오는 중">{[0, 1, 2, 3].map((row) => <div className={styles.skeleton} key={row} />)}</div> : shown.map((method) => <Link key={method.name} href={`/methods/${encodeURIComponent(method.name)}`} className={styles.libraryRow}>
        <span className={styles.libraryName}><strong>{methodName(method.name)}</strong><small>{method.name}</small></span>
        <span className={styles.libraryMetric}>{method.description.split(". ")[0].replace(/\.$/, "") + "."}</span>
        <span className={styles.librarySteps}>v{method.version}</span>
        <ArrowRight size={17} className={styles.libraryArrow} />
      </Link>)}
      {!loading && !error && shown.length === 0 && <div className={styles.libraryNoResults}><strong>일치하는 방법이 없습니다</strong><button className="ghost" type="button" onClick={() => setSearch("")}>검색 지우기</button></div>}
    </section>
  </div>;
}
