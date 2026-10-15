"use client";

import { useEffect, useState } from "react";
import { Background, Handle, Position, ReactFlow, useNodesInitialized, useReactFlow, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Check, Database, Workflow } from "lucide-react";

import type { Run, SemanticObject } from "@/lib/api";
import { methodName } from "@/lib/method-name";
import { stepFinding, stepPurpose } from "@/lib/run-story";
import { useT } from "@/lib/i18n";
import s from "./run-graph.module.css";

function MetricNode({ data }: NodeProps) {
  const t = useT();
  const value = data as { names: string[]; compact: boolean };
  return <div className={s.metricNode}>
    <span className={s.eyebrow}><Database size={14} />{t("Analysis metric")}</span>
    <strong>{value.names.join(" · ")}</strong>
    <Handle type="source" position={value.compact ? Position.Bottom : Position.Right} isConnectable={false} />
  </div>;
}

function StepNode({ data, selected }: NodeProps) {
  const t = useT();
  const value = data as { index: number; method: string; purpose: string; finding: string; status: string; compact: boolean;
    select: () => void; draftSelected?: boolean; toggleDraft?: () => void; source?: string };
  return <div className={`${s.node} ${selected ? s.selected : ""}`}>
    <Handle type="target" position={value.index === 0 && !value.compact ? Position.Left : Position.Top} isConnectable={false} />
    <button type="button" className={s.nodeButton} onClick={value.select} aria-label={t("View step {number} {method} result", { number: value.index + 1, method: methodName(value.method, t) })}>
      <span className={s.eyebrow}><Workflow size={14} />{t("Step {number}", { number: value.index + 1 })} · {methodName(value.method, t)}</span>
      {value.source && <span className={s.source}>{t(value.source)}</span>}
      <strong>{value.purpose}</strong>
      <span className={s.finding}>{value.finding}</span>
      <span className={s.status} data-status={value.status}>{value.status === "success" && <Check size={12} />}{t(value.status === "success" ? "Completed" : value.status === "failed" ? "Failed" : value.status === "refused" ? "Not comparable" : "Input needed")}</span>
    </button>
    {value.toggleDraft && <label className={s.draftChoice}><input type="checkbox" checked={value.draftSelected} onChange={value.toggleDraft} aria-label={t("Include step {number} in draft", { number: value.index + 1 })} />{t("Include in draft")}</label>}
    <Handle type="source" position={Position.Bottom} isConnectable={false} />
  </div>;
}

const nodeTypes = { metric: MetricNode, step: StepNode };

function FitGraph({ count, compact }: { count: number; compact: boolean }) {
  const initialized = useNodesInitialized();
  const { fitView } = useReactFlow();
  useEffect(() => { if (initialized) void fitView({ padding: compact ? 0.06 : 0.12, duration: 200 }); }, [initialized, count, compact, fitView]);
  return null;
}

export function RunGraph({ run, titles, selected, onSelect, draftSelection, onToggleDraft }: { run: Run; titles: Map<string, SemanticObject>; selected: number; onSelect: (index: number) => void; draftSelection?: number[]; onToggleDraft?: (index: number) => void }) {
  const t = useT();
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 700px)");
    const update = () => setCompact(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  if (!run.steps.length) return null;

  const metricRefs = [...new Set(run.steps.flatMap((record) => typeof record.step.bindings.metric === "string" ? [record.step.bindings.metric] : []))];
  const metricNames = metricRefs.map((ref) => titles.get(ref)?.title ?? t("Metric name needs checking"));
  const spacing = onToggleDraft ? 248 : 216;
  const mixedProcedure = !!run.recipe_invocation && run.steps.some(record => !record.invocation_id);
  const nodes = [
    { id: "run-metric", type: "metric", position: compact ? { x: 20, y: 0 } : { x: 0, y: Math.max(0, (run.steps.length - 1) * spacing / 2) }, data: { names: metricNames.length ? metricNames : [t("No metric selected")], compact } },
    ...run.steps.map((record, index) => ({ id: `run-step:${index}`, type: "step", position: compact ? { x: 0, y: 135 + index * spacing } : { x: 330, y: index * spacing }, selected: index === selected,
      data: { index, method: record.step.method, purpose: stepPurpose(record.step, t, run), finding: stepFinding(record, t), status: record.result.status, compact,
        source: mixedProcedure ? record.invocation_id ? "Recipe step" :
          index < run.steps.findIndex(item => !!item.invocation_id) ? "Exploration step" : "Additional analysis" : undefined,
        select: () => onSelect(index), draftSelected: draftSelection?.includes(index),
        toggleDraft: onToggleDraft && record.result.status === "success" ? () => onToggleDraft(index) : undefined } })),
  ];
  const edges = [
    { id: "metric-first", source: "run-metric", target: "run-step:0", style: { stroke: "var(--dl-border-strong)", strokeWidth: 1.5 } },
    ...run.steps.slice(1).map((_, index) => ({ id: `order:${index}`, source: `run-step:${index}`, target: `run-step:${index + 1}`,
      label: t("Run order"), style: { stroke: "var(--dl-border-strong)", strokeWidth: 1.5, strokeDasharray: "4 4" } })),
  ];
  const height = compact ? 135 + (run.steps.length - 1) * spacing + (onToggleDraft ? 216 : 184) + 28 : Math.max(270, run.steps.length * spacing + 35);
  return <section className={s.section} aria-label={t("Run graph")}>
    <div className={s.heading}><h2>{t("Analysis path for this question")}</h2><span>{t("Metric · Method · findings by step")}</span></div>
    <div className={s.canvas} role="group" aria-label={t("Analysis steps")} tabIndex={0} style={{ height: Math.min(compact ? 700 : 680, height) }}>
      <div className={s.viewport} style={{ height }}>
      <ReactFlow key={compact ? "compact" : "wide"} nodes={nodes} edges={edges} nodeTypes={nodeTypes} nodesDraggable={false} nodesConnectable={false}
        panOnDrag={false} zoomOnScroll={false} zoomOnPinch={false} preventScrolling={false} fitView minZoom={0.8} maxZoom={1} proOptions={{ hideAttribution: true }}>
        <FitGraph count={run.steps.length} compact={compact} /><Background color="var(--dl-border-strong)" gap={20} />
      </ReactFlow>
      </div>
    </div>
  </section>;
}
