"use client";

import { useRef } from "react";
import { FileText, X } from "lucide-react";
import type { Run, Validation } from "@/lib/api";
import { methodName } from "@/lib/method-name";
import { stepFinding } from "@/lib/run-story";
import { ValidationList } from "./result";
import styles from "@/app/library.module.css";

export function RunAnswer({ run, warnings, onSelect }: { run: Run; warnings: Validation[]; onSelect: (index: number) => void }) {
  const original = useRef<HTMLDialogElement>(null);
  const authored = run.conclusion && run.conclusion.source !== "execution" ? run.conclusion : null;
  const findings = authored?.findings ?? run.steps.map((record, index) => ({ text: stepFinding(record), step_indices: [index] }));
  return <section className={styles.runAnswer} aria-label="분석 답변">
    <span>{authored ? `분석 결론${run.conclusion_author?.client_name === "Decision Layer Web" ? " · 사용자 작성" : run.origin === "mcp" && run.conclusion_author?.client_name ? " · AI 작성" : ""}` : run.steps.length ? "단계별 결과 요약" : "분석 상태"}</span>
    {authored ? <p>{authored.answer}</p> : <p>{run.running ? "분석이 진행 중입니다." : run.steps.length ? "질문에 대한 구조화된 결론은 기록되지 않았습니다. 실행한 단계의 결과를 확인할 수 있습니다." : "아직 실행된 분석 단계가 없습니다."}</p>}
    {findings.length > 0 && <ul className={styles.runFindings}>{findings.map((finding, index) => <li key={index}><p>{finding.text}</p><div>{finding.step_indices.filter(i => i >= 0 && i < run.steps.length).map(i => <button key={i} type="button" onClick={() => onSelect(i)}>{i + 1}단계 · {methodName(run.steps[i].step.method)}</button>)}</div></li>)}</ul>}
    {!!authored?.limitations.length && <div className={styles.runLimitations}><h3>해석의 한계</h3><ul>{authored.limitations.map((text, index) => <li key={index}>{text}</li>)}</ul></div>}
    {!authored && run.summary && <><button type="button" className={styles.runOriginalButton} onClick={() => original.current?.showModal()}><FileText size={14} />기존 결론 원문 보기</button>
      <dialog ref={original} className={styles.runDialog} aria-label="기존 결론 원문"><header><h2>기존 결론 원문</h2><button type="button" aria-label="닫기" title="닫기" onClick={() => original.current?.close()}><X size={18} /></button></header><p className={styles.runOriginalText}>{run.summary}</p></dialog></>}
    {warnings.length > 0 && <ValidationList items={warnings} />}
  </section>;
}
