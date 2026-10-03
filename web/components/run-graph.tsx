"use client";

import { useEffect, useState } from "react";
import { Background, Handle, Position, ReactFlow, useNodesInitialized, useReactFlow, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Database, Workflow } from "lucide-react";

import type { Run, SemanticObject } from "@/lib/api";
import { methodName } from "@/lib/method-name";
import { stepFinding, stepPurpose } from "@/lib/run-story";
import s from "./run-graph.module.css";

function MetricNode({ data }: NodeProps) {
  const value = data as { names: string[]; compact: boolean };
  return <div className={s.metricNode}>
    <span className={s.eyebrow}><Database size={14} />분석 지표</span>
    <strong>{value.names.join(" · ")}</strong>
    <Handle type="source" position={value.compact ? Position.Bottom : Position.Right} isConnectable={false} />
  </div>;
}

function StepNode({ data, selected }: NodeProps) {
  const value = data as { index: number; method: string; purpose: string; finding: string; status: string; compact: boolean;
    select: () => void; draftSelected?: boolean; toggleDraft?: () => void };
  return <div className={`${s.node} ${selected ? s.selected : ""}`}>
    <Handle type="target" position={value.index === 0 && !value.compact ? Position.Left : Position.Top} isConnectable={false} />
    <button type="button" className={s.nodeButton} onClick={value.select} aria-label={`${value.index + 1}단계 ${methodName(value.method)} 결과 보기`}>
      <span className={s.eyebrow}><Workflow size={14} />{value.index + 1}단계 · {methodName(value.method)}</span>
      <strong>{value.purpose}</strong>
      <span className={s.finding}>{value.finding}</span>
      <span className={s.status}>{value.status === "success" ? "완료" : value.status === "failed" ? "실패" : value.status === "refused" ? "비교 불가" : "입력 필요"}</span>
    </button>
    {value.toggleDraft && <label className={s.draftChoice}><input type="checkbox" checked={value.draftSelected} onChange={value.toggleDraft} aria-label={`${value.index + 1}단계 초안에 포함`} />초안에 포함</label>}
    <Handle type="source" position={Position.Bottom} isConnectable={false} />
  </div>;
}

const nodeTypes = { metric: MetricNode, step: StepNode };

function FitGraph({ count, compact }: { count: number; compact: boolean }) {
  const initialized = useNodesInitialized();
  const { fitView } = useReactFlow();
  useEffect(() => { if (initialized) void fitView({ padding: 0.16, duration: 200 }); }, [initialized, count, compact, fitView]);
  return null;
}

export function RunGraph({ run, titles, selected, onSelect, draftSelection, onToggleDraft }: { run: Run; titles: Map<string, SemanticObject>; selected: number; onSelect: (index: number) => void; draftSelection?: number[]; onToggleDraft?: (index: number) => void }) {
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
  const metricNames = metricRefs.map((ref) => titles.get(ref)?.title ?? "지표 이름 확인 필요");
  const spacing = onToggleDraft ? 218 : 190;
  const nodes = [
    { id: "run-metric", type: "metric", position: compact ? { x: 20, y: 0 } : { x: 0, y: Math.max(0, (run.steps.length - 1) * spacing / 2) }, data: { names: metricNames.length ? metricNames : ["지표 미지정"], compact } },
    ...run.steps.map((record, index) => ({ id: `run-step:${index}`, type: "step", position: compact ? { x: 0, y: 135 + index * spacing } : { x: 330, y: index * spacing }, selected: index === selected,
      data: { index, method: record.step.method, purpose: stepPurpose(record.step), finding: stepFinding(record), status: record.result.status, compact,
        select: () => onSelect(index), draftSelected: draftSelection?.includes(index),
        toggleDraft: onToggleDraft && record.result.status === "success" ? () => onToggleDraft(index) : undefined } })),
  ];
  const edges = [
    { id: "metric-first", source: "run-metric", target: "run-step:0", style: { stroke: "#1b78c8", strokeWidth: 2 } },
    ...run.steps.slice(1).map((_, index) => ({ id: `order:${index}`, source: `run-step:${index}`, target: `run-step:${index + 1}`,
      label: "실행 순서", style: { stroke: "#93a6ae", strokeWidth: 1.5, strokeDasharray: "4 4" } })),
  ];
  const height = compact ? 135 + run.steps.length * spacing + 35 : Math.max(360, run.steps.length * spacing + 35);
  return <section className={s.section} aria-label="실행 그래프">
    <div className={s.heading}><h2>이 질문의 분석 경로</h2><span>지표 · 분석 방법 · 단계별 발견</span></div>
    <div className={s.canvas} style={{ height: Math.min(compact ? 700 : 680, height) }}>
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} nodesDraggable={false} nodesConnectable={false}
        panOnDrag={false} zoomOnScroll={false} zoomOnPinch={false} fitView minZoom={0.25} maxZoom={1.15} proOptions={{ hideAttribution: true }}>
        <FitGraph count={run.steps.length} compact={compact} /><Background color="#e3e9ec" gap={20} />
      </ReactFlow>
    </div>
  </section>;
}
