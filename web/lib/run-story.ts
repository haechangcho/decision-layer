import type { PlanStep, Run } from "@/lib/api";
import { timeSeriesData } from "@/lib/artifact-data";
import type { Translate } from "@/lib/i18n";

const defaultPurposes: Record<string, string> = {
  "query.trend": "Check values and changes by period",
  "query.drilldown": "Check differences between groups",
  "query.peer_comparison": "Check differences from the peer group and overall",
  "causal.cem": "Check differences with conditions matched",
};

export function isSourcePurpose(step: PlanStep, run: Run): boolean {
  return !!run.plan.recipe && (step.purpose_context === "source_run" ||
    !step.purpose_context && !!run.recipe_snapshot?.origin_runs?.length);
}

export function stepPurpose(step: PlanStep, t: Translate, run?: Run): string {
  if (run && isSourcePurpose(step, run)) {
    const index = run.steps.findIndex(record => record.step === step);
    const outcomes = run.conclusion?.goal_outcomes?.filter(outcome => outcome.step_indices.includes(index));
    const ids = outcomes?.length ? outcomes.map(outcome => outcome.goal_id) : step.goal_ids || [];
    const goals = run.goals?.filter(goal => ids.includes(goal.id)) || [];
    // Historical purposes may contain the original dates. Use only unambiguous current goal links.
    if (goals.length === 1) return goals[0].description;
    return t(defaultPurposes[step.method] || "Run the saved analysis step");
  }
  return step.purpose?.trim() || t(defaultPurposes[step.method] || "Check the result with this Method");
}

const number = (value: number) => value.toLocaleString("ko-KR", { maximumFractionDigits: 2 });

export function populationLabel(index: number, fallback: unknown, t: Translate): unknown {
  const label = ["Selected subject", "Peer group (excluding subject)", "Overall (excluding subject)"][index];
  return label ? t(label) : fallback;
}

export function stepFinding(record: Run["steps"][number], t: Translate): string {
  const result = record.result;
  if (result.status === "needs_input") return t("More input is needed");
  if (result.status === "refused") return t("Check the analysis conditions");
  if (result.status === "failed") return t("The analysis failed");
  const primary = result.primary;
  if (!primary || !primary.data || typeof primary.data !== "object") return t("View result");
  const data = primary.data as Record<string, unknown>;
  const series = timeSeriesData(primary);
  if (series && Array.isArray(series.rows)) {
    const metric = series.metric;
    const last = series.rows.at(-1);
    const value = typeof metric === "string" && last && typeof last === "object" ? (last as Record<string, unknown>)[metric] : null;
    if (typeof value === "number") return series.rows.length === 1 ? t("Selected period {value}", { value: number(value) }) : t("Latest period {value}", { value: number(value) });
  }
  if (primary.type === "breakdown_table" && Array.isArray(data.rows) && data.rows.length) {
    if (data.subject && data.rows.length === 3) {
      const [subject, peers, overall] = data.rows as Record<string, unknown>[];
      if (typeof subject.metric === "number" && typeof peers.difference_from_subject === "number" && typeof overall.difference_from_subject === "number")
        return t("Subject {subject} · vs. peer group {peers} · vs. overall {overall}", { subject: number(subject.metric), peers: number(peers.difference_from_subject), overall: number(overall.difference_from_subject) });
    }
    const first = data.rows[0] as Record<string, unknown>;
    if (typeof first.value === "string") return `${first.value}${typeof first.metric === "number" ? ` · ${number(first.metric)}` : ""}`;
  }
  return primary.title || t("View result");
}
