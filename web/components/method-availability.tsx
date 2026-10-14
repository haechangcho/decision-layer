"use client";
import { useState } from "react";
import { api, getSourceCallerToken, type MethodSearchReport } from "@/lib/api";
import { useT } from "@/lib/i18n";

/** Read-only inspection uses the same contract as Python and MCP. */
export function MethodAvailability({ name }: { name: string }) {
  const t = useT();
  const [report, setReport] = useState<MethodSearchReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  async function inspect() {
    setLoading(true); setError(""); setReport(null);
    try {
      setReport(await api<MethodSearchReport>("/methods:search", {
        method: "POST", body: { names: [name] }, callerToken: getSourceCallerToken(),
      }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setLoading(false); }
  }
  return <section>
    <button type="button" className="ghost" disabled={loading} onClick={inspect}>
      {t(loading ? "Checking Method requirements…" : "Check Method requirements")}
    </button>
    {error && <p role="alert">{error}</p>}
    {report && <div aria-live="polite">
      <p>{t(report.candidates.length ? "Required input types and dependencies are available. Select inputs before running." : "This connection cannot currently supply all Method requirements.")}</p>
      {report.excluded.flatMap(item => item.reasons).map((reason, index) =>
        <p key={index}>{t(reason.code)}{reason.input ? `: ${reason.input}` : ""}{reason.value ? `: ${reason.value}` : ""}{reason.message ? ` — ${reason.message}` : ""}</p>)}
      <p>{t("This check does not verify question relevance, joins, periods or analytical assumptions. Execution performs the remaining checks.")}</p>
    </div>}
  </section>;
}
