"use client";

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
  { key: "skill", title: "Skill", description: "AI가 지침을 따라 조회합니다. 실제 쿼리와 응답이 실행 기록에 남습니다.", Icon: FileText },
  { key: "python", title: "Python", description: "등록한 함수로 계산합니다. 입력과 결과, 검사 내용을 확인할 수 있습니다.", Icon: Code2 },
] as const;

export default function MethodsPage() {
  const { data, error, loading, reload } = useApi<MethodManifest[]>("/methods");
  const [search, setSearch] = useState("");
  const shown = useMemo(() => (data ?? []).filter(method =>
    `${method.name} ${methodTitle(method)} ${method.description}`
      .toLowerCase().includes(search.trim().toLowerCase())), [data, search]);

  return <div className={styles.page}>
    <div className={styles.libraryHeader}><div><h1>분석 방법</h1><p>방법을 살펴보고, 실제 데이터로 실행해 확인하세요.</p></div>
      <Link className={styles.createLink} href="/runs">실행 기록 <ArrowRight size={16} /></Link>
    </div>
    {error && <RequestError title="분석 방법을 불러오지 못했습니다" error={error} retry={reload} />}
    {loading && !data ? <LoadingState /> : data && <>
      <div className={styles.methodToolbar}>
        <label className={styles.librarySearch}><Search size={17} />
          <input aria-label="분석 방법 검색" value={search} onChange={event => setSearch(event.target.value)} placeholder="이름 또는 목적 검색" />
          {search && <button aria-label="검색 지우기" onClick={() => setSearch("")}><X size={15} /></button>}
        </label><span className={styles.libraryCount}>{shown.length}개</span>
      </div>
      {groups.map(({ key, title, description, Icon }) => {
        const methods = shown.filter(method => (method.implementation || "python") === key);
        if (!methods.length) return null;
        return <section key={key} className={styles.methodGroup} aria-label={`${title} 분석 방법`}>
          <div className={styles.methodGroupHeading}><h2><Icon size={18} />{title}<span>{methods.length}</span></h2><p>{description}</p></div>
          <div className={styles.libraryList}>
            {methods.map(method => <Link key={method.name} href={`/methods/${encodeURIComponent(method.name)}`} className={styles.methodRow}>
              <span className={styles.libraryName}><strong>{methodTitle(method)}</strong><small>{method.name}</small></span>
              <span className={styles.libraryMetric}>{methodSummary(method)}</span>
              <span className={styles.librarySteps}>v{method.version}</span><ArrowRight size={17} className={styles.libraryArrow} />
            </Link>)}
          </div>
        </section>;
      })}
      {shown.length === 0 && <div className={styles.empty}><h2>{data.length ? "검색 결과가 없습니다" : "등록된 분석 방법이 없습니다"}</h2>
        {search && <button className="ghost" onClick={() => setSearch("")}>검색 지우기</button>}
      </div>}
    </>}
  </div>;
}
