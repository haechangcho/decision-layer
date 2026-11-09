"use client";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { GitBranch, Workflow } from "lucide-react";
import s from "@/components/analysis-canvas.module.css";

function RecipeNode({id,data,selected}:NodeProps) {
  return <button type="button" data-workflow-step={id} aria-current={selected?"step":undefined} className={`${s.node} ${selected?s.selected:""}`} aria-label={`${String(data.kind)} · ${String(data.label)}`}>
    {!data.scope&&<Handle type="target" position={data.flowIn as Position||Position.Left} isConnectable={false}/>}
    <span className={s.nodeKind}>{data.scope?<GitBranch size={14}/>:<Workflow size={14}/>} {String(data.kind)}</span>
    <strong>{String(data.label)}</strong><span className={s.nodeStatus}>{String(data.detail)}</span>
    <Handle type="source" position={data.flowOut as Position||Position.Right} isConnectable={false}/>
    <Handle type="source" id="selection-out" position={Position.Bottom} isConnectable={false}/><Handle type="target" id="selection-in" position={Position.Top} isConnectable={false}/>
  </button>;
}
export const nodeTypes={recipe:RecipeNode};
