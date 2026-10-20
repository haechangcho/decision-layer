"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { MethodManifest, Run } from "@/lib/api";
import { LoadingState } from "@/components/loading-indicator";
import { RequestError } from "@/components/request-error";
import styles from "@/app/library.module.css";

/** Only execution-time version references count; registration is not a test. */
export function MethodExecutions({ method }: { method: MethodManifest }) {
  const { data, error, loading, reload } = useApi<Run[]>("/runs?limit=100");
  const reference = `method://${method.name.replaceAll(".", "/")}@${method.version}`;
  const executions = (data ?? []).flatMap(run => run.steps.flatMap((step, index) =>
    step.method === reference ? [{ run, step, index }] : [])).slice(0, 5);
  return <section className={styles.methodPanel} aria-label="이 버전의 실행 기록">
    <h2>이 버전의 실행 기록</h2>
    <p>최근 100개 실행에서 v{method.version}의 기록을 확인합니다.</p>
    {error ? <RequestError title="실행 기록을 불러오지 못했습니다" error={error} retry={reload} /> : loading || !data ? <LoadingState /> : executions.length ?
      <div className={styles.methodEvidence}>{executions.map(({ run, step, index }) => {
        const status = step.result.status;
        const label = status === "success" ? "실행 성공" : status === "refused" ? "검사로 중단" : status === "failed" ? "실행 실패" : step.skill?.status === "awaiting_agent" ? "AI 실행 대기" : "입력 대기";
        return <Link key={`${run.id}:${index}`} href={`/runs/${run.id}`}>
          <span><strong>{label}</strong><small>{run.plan.question || "분석 테스트"}</small>
            <small>{new Date(step.started_at).toLocaleString()} / {step.result.validation.length}개 검사 / 기록된 조회 {step.skill ? step.skill.queries.length : step.result.provenance.queries.length}개</small></span>
          <ArrowUpRight size={17} />
        </Link>;
      })}</div> : <p>이 범위에서 실행 기록을 찾지 못했습니다. 등록만으로 실행을 확인한 것은 아닙니다.</p>}
    <Link className={styles.secondaryLink} href="/runs">전체 실행 기록 보기</Link>
  </section>;
}
