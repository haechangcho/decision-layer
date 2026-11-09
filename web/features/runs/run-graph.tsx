"use client";

import type { ReactNode } from "react";
import { Handle, Position, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { Check, Database } from "lucide-react";
import type { Run, SemanticObject } from "@/lib/api";
import { WorkflowCanvas, type WorkflowItem } from "@/components/workflow-canvas";
import { useMethodName } from "@/lib/method-name";
import { stepPurpose } from "@/lib/run-story";
import { useT } from "@/lib/i18n";
import s from "./run-graph.module.css";

function MetricNode({data}:NodeProps) {
  const t=useT();
  return <div className={s.metricNode}><span className={s.eyebrow}><Database size={13}/>{t("Analysis metric")}</span><strong>{String(data.label)}</strong><Handle type="source" position={data.flowOut as Position||Position.Right} isConnectable={false}/></div>;
}
function StepNode({id,data,selected}:NodeProps) {
  return <div className={`${s.node} ${selected?s.selected:""}`}>
    <Handle type="target" position={data.flowIn as Position||Position.Left} isConnectable={false}/>
    <button type="button" data-workflow-step={id} aria-current={selected?"step":undefined} className={s.nodeButton} aria-label={String(data.ariaLabel)}>
      <span className={s.eyebrow}><span>{String(data.number)}</span><span className={s.status} data-status={String(data.status)}>{data.status==="success"&&<Check size={12}/>} {String(data.statusLabel)}</span></span>
      <strong>{String(data.label)}</strong><span className={s.purpose}>{String(data.purpose)}</span>
      {Boolean(data.source)&&<span className={s.source}>{String(data.source)}</span>}
    </button>
    {data.footer as ReactNode}
    <Handle type="source" position={data.flowOut as Position||Position.Right} isConnectable={false}/>
    <Handle type="source" id="selection-out" position={Position.Bottom} isConnectable={false}/><Handle type="target" id="selection-in" position={Position.Top} isConnectable={false}/>
  </div>;
}
const nodeTypes={metric:MetricNode,step:StepNode};

export function RunGraph({run,titles,selected,onSelect,draftSelection,onToggleDraft}:{run:Run;titles:Map<string,SemanticObject>;selected:number;onSelect:(index:number)=>void;draftSelection?:number[];onToggleDraft?:(index:number)=>void}) {
  const t=useT();const methodName=useMethodName(t);
  if(!run.steps.length)return null;
  const refs=[...new Set([
    ...(run.recipe_snapshot?.semantic_scope.primary_metric?[run.recipe_snapshot.semantic_scope.primary_metric]:[]),
    ...run.steps.flatMap(record=>Object.values(record.step.bindings).flatMap(value=>(Array.isArray(value)?value:[value])
      .filter((ref):ref is string=>typeof ref==="string"&&titles.get(ref)?.kind==="measure"))),
  ])];
  const metric=refs.map(ref=>titles.get(ref)?.title??t("Metric name needs checking")).join(" · ")||t("No metric selected");
  const items:WorkflowItem[]=[{id:"run-metric",title:metric,eyebrow:t("Analysis metric"),selectable:false}];
  const nodes:Node[]=[{id:"run-metric",type:"metric",position:{x:0,y:0},data:{label:metric}}];
  const mixed=!!run.recipe_invocation&&run.steps.some(record=>!record.invocation_id);
  run.steps.forEach((record,index)=>{
    const status=record.skill?.status==="awaiting_agent"?"awaiting_agent":record.result.status;
    const statusLabel=t(status==="success"?"Completed":status==="failed"?"Failed":status==="refused"?"Not comparable":status==="awaiting_agent"?"Waiting for AI":"Input needed");
    const footer=onToggleDraft&&record.result.status==="success"?<label className={s.draftChoice}><input type="checkbox" checked={draftSelection?.includes(index)} onChange={()=>onToggleDraft(index)} aria-label={t("Include step {number} in draft",{number:index+1})}/>{t("Include in draft")}</label>:undefined;
    const label=methodName(record.step.method);const purpose=stepPurpose(record.step,t,run);
    items.push({id:`run-step:${index}`,number:index+1,title:label,description:purpose,status,statusLabel,footer});
    nodes.push({id:`run-step:${index}`,type:"step",position:{x:0,y:0},data:{number:t("Step {number}",{number:index+1}),label,purpose,status,statusLabel,footer,
      ariaLabel:t("View step {number} {method} result",{number:index+1,method:label}),
      source:mixed?t(record.invocation_id?"Recipe step":"Exploration step"):undefined}});
  });
  const edges:Edge[]=[{id:"metric-first",source:"run-metric",target:"run-step:0",style:{stroke:"var(--dl-border-strong)",strokeWidth:1.5}},
    ...run.steps.slice(1).map((_,index)=>({id:`order:${index}`,source:`run-step:${index}`,target:`run-step:${index+1}`,style:{stroke:"var(--dl-border-strong)",strokeWidth:1.5,strokeDasharray:"4 4"}}))];
  run.steps.forEach((record,index)=>{
    const params=record.requested_step?.params??record.step.params;
    const sources=new Set(Object.values(params).flatMap(value=>value&&typeof value==="object"&&!Array.isArray(value)&&(value as Record<string,unknown>).source==="step"?[String((value as Record<string,unknown>).step_id)]:[]));
    sources.forEach(source=>{
      const from=run.steps.findIndex(item=>item.step.id===source);if(from<0||from>=index)return;
      edges.push({id:`selection:${from}:${index}`,source:`run-step:${from}`,target:`run-step:${index}`,sourceHandle:"selection-out",targetHandle:"selection-in",data:{resultTransfer:true},style:{stroke:"var(--accent)",strokeWidth:2}});
    });
  });
  return <section id="run-analysis-path" className={s.section} aria-label={t("Run graph")}><div className={s.heading}><h2>{t("Analysis path for this question")}</h2><span>{t("{count} steps",{count:run.steps.length})}</span></div>
    <WorkflowCanvas label={t("Analysis steps")} items={items} nodes={nodes} edges={edges} nodeTypes={nodeTypes} selected={`run-step:${selected}`} onSelect={id=>{if(id.startsWith("run-step:"))onSelect(Number(id.split(":")[1]));}}/>
  </section>;
}
