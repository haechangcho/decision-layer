"use client";
import { useT } from "@/lib/i18n";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { MethodManifest, Run } from "@/lib/api";
import { LoadingState } from "@/components/loading-indicator";
import { RequestError } from "@/components/request-error";
import styles from "@/app/library.module.css";

/** Only execution-time version references count; registration is not a test. */
export function MethodExecutions({ method }: { method: MethodManifest }) {
  const t = useT();
  const { data, error, loading, reload } = useApi<Run[]>("/runs?limit=100");
  const reference = `method://${method.name.replaceAll(".", "/")}@${method.version}`;
  const executions = (data ?? []).flatMap(run => run.steps.flatMap((step, index) =>
    step.method === reference ? [{ run, step, index }] : [])).slice(0, 5);
  return <section className={styles.methodPanel} aria-label={t("Runs for this version")}>
    <h2>{t("Runs for this version")}</h2>
    <p>{t("Runs for v{version} among the latest 100 Runs.", { version: method.version })}</p>
    {error ? <RequestError title={t("Could not load the Runs")} error={error} retry={reload} /> : loading || !data ? <LoadingState /> : executions.length ?
      <div className={styles.methodEvidence}>{executions.map(({ run, step, index }) => {
        const status = step.result.status;
        const label = status === "success" ? t("Execution succeeded") : status === "refused" ? t("Stopped by checks") : status === "failed" ? t("Execution failed") : step.skill?.status === "awaiting_agent" ? t("Waiting for AI") : t("Waiting for input");
        return <Link key={`${run.id}:${index}`} href={`/runs/${run.id}`}>
          <span><strong>{label}</strong><small>{run.plan.question || t("Analysis test")}</small>
            <small>{new Date(step.started_at).toLocaleString()} / {t("{checks} checks / {queries} recorded queries", { checks: step.result.validation.length, queries: step.skill ? step.skill.queries.length : step.result.provenance.queries.length })}</small></span>
          <ArrowUpRight size={17} />
        </Link>;
      })}</div> : <p>{t("No Runs found within this range. Registration alone does not verify execution.")}</p>}
    <Link className={styles.secondaryLink} href="/runs">{t("View all Runs")}</Link>
  </section>;
}
