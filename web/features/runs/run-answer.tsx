"use client";

import { useRef } from "react";
import { ArrowUpRight, FileText, X } from "lucide-react";
import type { Run, Validation } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { methodName } from "@/lib/method-name";
import { stepFinding } from "@/lib/run-story";
import { ValidationList } from "@/components/result";
import styles from "@/app/library.module.css";

export function RunAnswer({ run, warnings, onSelect }: { run: Run; warnings: Validation[]; onSelect: (index: number) => void }) {
  const t = useT();
  const original = useRef<HTMLDialogElement>(null);
  const authored = run.conclusion && run.conclusion.source !== "execution" ? run.conclusion : null;
  const findings = authored?.findings ?? run.steps.map((record, index) => ({ text: stepFinding(record, t), step_indices: [index] }));
  if (!authored && !run.summary) return <section className={styles.runProgressSummary} aria-label={t("Analysis answer")}>
    <p>{run.running ? t("Analysis is running.") : run.steps.length ? t("Review the results, then write a conclusion.") : t("No analysis steps have run yet.")}</p>
    {warnings.length > 0 && <ValidationList items={warnings} />}
  </section>;
  return <section className={styles.runAnswer} aria-label={t("Analysis answer")}>
    <div className={styles.runAnswerHeading}><h2>{t(authored ? "Analysis conclusion" : run.steps.length ? "Summary of step results" : "Analysis status")}</h2>{authored && <span>{run.conclusion_author?.client_name === "Decision Layer Web" ? t("Written by a user") : run.origin === "mcp" && run.conclusion_author?.client_name ? t("Written by AI") : ""}</span>}</div>
    {authored ? <p>{authored.answer}</p> : <p>{t(run.running ? "The analysis is in progress." : run.steps.length ? "No structured conclusion to the question was recorded. You can review the results of the steps that ran." : "No analysis steps have run yet.")}</p>}
    {findings.length > 0 && <div className={styles.runDiscovery}><h3>{t("Key findings")}</h3><ol className={styles.runFindings}>{findings.map((finding, index) => <li key={index}><span className={styles.runFindingNumber} aria-hidden="true">{index + 1}</span><div><p>{finding.text}</p><div>{finding.step_indices.filter(i => i >= 0 && i < run.steps.length).map(i => <button key={i} type="button" onClick={() => onSelect(i)}>{t("Step {number}", { number: i + 1 })} · {methodName(run.steps[i].step.method, t)}<ArrowUpRight size={13} aria-hidden="true" /></button>)}</div></div></li>)}</ol></div>}
    {!!authored?.limitations.length && <div className={styles.runLimitations}><h3>{t("Limits of interpretation")}</h3><ul>{authored.limitations.map((text, index) => <li key={index}>{text}</li>)}</ul></div>}
    {!authored && run.summary && <><button type="button" className={styles.runOriginalButton} onClick={() => original.current?.showModal()}><FileText size={14} />{t("View original conclusion")}</button>
      <dialog ref={original} className={styles.runDialog} aria-label={t("Original conclusion")}><header><h2>{t("Original conclusion")}</h2><button type="button" aria-label={t("Close")} title={t("Close")} onClick={() => original.current?.close()}><X size={18} /></button></header><p className={styles.runOriginalText}>{run.summary}</p></dialog></>}
    {warnings.length > 0 && <ValidationList items={warnings} />}
  </section>;
}
