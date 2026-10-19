"use client";

import { useEffect } from "react";
import { Handle, Position, useNodesInitialized, useReactFlow, type NodeProps } from "@xyflow/react";
import { GitBranch, Workflow } from "lucide-react";
import s from "@/components/analysis-canvas.module.css";

function RecipeNode({ data, selected }: NodeProps) {
  return <div className={`${s.node} ${selected ? s.selected : ""}`}>
    <Handle type="target" position={Position.Top} />
    <span className={s.nodeKind}>{data.scope ? <GitBranch size={16} /> : <Workflow size={16} />}{String(data.kind)}</span>
    <strong>{String(data.label)}</strong><span className={s.nodeStatus}>{String(data.detail)}</span>
    <Handle type="source" position={Position.Bottom} />
    <Handle type="source" id="selection-out" position={Position.Right} />
    <Handle type="target" id="selection-in" position={Position.Right} />
  </div>;
}
export const nodeTypes = { recipe: RecipeNode };

export function FitRecipe({ count }: { count: number }) {
  const initialized = useNodesInitialized();
  const { fitView } = useReactFlow();
  useEffect(() => {
    if (initialized) void fitView({ padding: 0.18, duration: 200 });
  }, [initialized, count, fitView]);
  return null;
}
