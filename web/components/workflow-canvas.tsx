"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Background, MarkerType, Position, ReactFlow, ReactFlowProvider, useNodesInitialized, useReactFlow, useStore, type Edge, type Node, type NodeTypes } from "@xyflow/react";
import { ArrowRight, Check, ChevronRight, Focus, GitBranch, ListOrdered, Maximize2, Minus, Plus, Scan } from "lucide-react";
import "@xyflow/react/dist/style.css";
import { useT } from "@/lib/i18n";
import { InspectorDialog } from "./inspector-dialog";
import { workflowLayout } from "./workflow-layout";
import s from "./workflow-canvas.module.css";

export type WorkflowItem = { id:string; title:string; description?:string; eyebrow?:string; status?:string; statusLabel?:string; number?:number; selectable?:boolean; footer?:ReactNode };
type Props = { label:string; items:WorkflowItem[]; nodes:Node[]; edges:Edge[]; nodeTypes:NodeTypes; selected:string; onSelect:(id:string)=>void };

function useWidth() {
  const element=useRef<HTMLDivElement>(null);
  const [width,setWidth]=useState(0);
  useEffect(()=>{
    const node=element.current;if(!node)return;
    const observer=new ResizeObserver(entries=>setWidth(Math.round(entries[0].contentRect.width)));
    observer.observe(node);return()=>observer.disconnect();
  },[]);
  return {element,width};
}

function Camera({ layoutKey, selected }: { layoutKey:string; selected:string }) {
  const t=useT();const initialized=useNodesInitialized();
  const selectedRef=useRef(selected);selectedRef.current=selected;
  const {fitView,zoomIn,zoomOut,viewportInitialized}=useReactFlow();
  const width=useStore(state=>state.width);const height=useStore(state=>state.height);
  const zoom=useStore(state=>state.transform[2]);
  useEffect(()=>{
    if(!initialized||!viewportInitialized||!width||!height)return;
    const frame=requestAnimationFrame(()=>{void fitView({padding:.12,maxZoom:1,duration:0,...(width<760?{nodes:[{id:selectedRef.current}]}:{})});});
    return()=>cancelAnimationFrame(frame);
  },[initialized,viewportInitialized,width,height,layoutKey,fitView]);
  return <div className={`${s.camera} nodrag nopan`} role="toolbar" aria-label={t("Flow navigation")}>
    <button type="button" aria-label={t("Zoom out")} title={t("Zoom out")} onClick={()=>void zoomOut({duration:150})}><Minus size={15}/></button>
    <span aria-live="off">{Math.round(zoom*100)}%</span>
    <button type="button" aria-label={t("Zoom in")} title={t("Zoom in")} onClick={()=>void zoomIn({duration:150})}><Plus size={15}/></button>
    <span className={s.separator}/>
    <button type="button" title={t("Fit all steps")} onClick={()=>void fitView({padding:.12,maxZoom:1,duration:200})}><Scan size={15}/>{t("Fit all")}</button>
    <button type="button" title={t("Focus selected step")} onClick={()=>void fitView({nodes:[{id:selected}],padding:.5,maxZoom:1.15,duration:200})}><Focus size={15}/>{t("Selected step")}</button>
  </div>;
}

function FlowSurface({ nodes,edges,nodeTypes,selected,onSelect,expanded=false }: Pick<Props,"nodes"|"edges"|"nodeTypes"|"selected"|"onSelect"> & {expanded?:boolean}) {
  const t=useT();const {element,width}=useWidth();
  const layout=workflowLayout(nodes.length,width);
  const sides={top:Position.Top,bottom:Position.Bottom,left:Position.Left,right:Position.Right};
  const arranged=nodes.map((node,index)=>({...node,initialWidth:260,initialHeight:node.data.footer?180:148,position:layout.positions[index],selected:node.id===selected,
    data:{...node.data,flowIn:sides[layout.positions[index].entry as keyof typeof sides],flowOut:sides[layout.positions[index].exit as keyof typeof sides]}}));
  const connections=edges.map(edge=>({...edge,type:"smoothstep",markerEnd:{type:MarkerType.ArrowClosed,width:15,height:15,color:edge.style?.stroke as string||"#94a3b8"},labelStyle:{fontSize:11,fill:"var(--muted)"},labelBgStyle:{fill:"var(--dl-canvas)"},labelBgPadding:[5,3] as [number,number]}));
  return <div ref={element} className={`${s.surface} ${expanded?s.expanded:""}`} style={expanded?undefined:{height:layout.height}}>
    {width>0&&<ReactFlowProvider key={`${layout.columns}:${nodes.length}`}><ReactFlow nodes={arranged} edges={connections} nodeTypes={nodeTypes} onNodeClick={(_,node)=>onSelect(node.id)}
      nodesDraggable={false} nodesConnectable={false} nodesFocusable={false} edgesFocusable={false} deleteKeyCode={null}
      panOnDrag zoomOnScroll={false} zoomOnPinch preventScrolling={false} minZoom={.15} maxZoom={1.75}
      fitView fitViewOptions={{padding:.12,maxZoom:1,...(width<760?{nodes:[{id:selected}]}:{})}}
      aria-label={t("Analysis flow diagram")}>
      <Background color="var(--dl-border-strong)" gap={24}/><Camera layoutKey={`${nodes.map(node=>node.id).join("|")}:${layout.columns}`} selected={selected}/>
    </ReactFlow></ReactFlowProvider>}
  </div>;
}

/** Shared Run/Recipe navigation. Responsive choice never changes the procedure. */
export function WorkflowCanvas({label,items,nodes,edges,nodeTypes,selected,onSelect}:Props) {
  const t=useT();const {element,width}=useWidth();
  const [choice,setChoice]=useState<"list"|"graph"|null>(null);
  const [expanded,setExpanded]=useState(false);const [modalSelection,setModalSelection]=useState(selected);
  const view=choice??(workflowLayout(items.length,width).readableOverview?"graph":"list");
  const selectedItem=items.find(item=>item.id===modalSelection);
  return <div ref={element} className={s.workspace}>
    <div className={s.toolbar}>
      <div className={s.switch} role="group" aria-label={t("Flow view")}>
        <button type="button" aria-pressed={view==="list"} onClick={()=>setChoice("list")}><ListOrdered size={15}/>{t("Step list")}</button>
        <button type="button" aria-pressed={view==="graph"} onClick={()=>setChoice("graph")}><GitBranch size={15}/>{t("Flow diagram")}</button>
      </div>
      <button type="button" className={s.expand} onClick={()=>{setModalSelection(selected);setExpanded(true);}}><Maximize2 size={15}/>{t("Expand flow")}</button>
    </div>
    {view==="graph"?<FlowSurface nodes={nodes} edges={edges} nodeTypes={nodeTypes} selected={selected} onSelect={onSelect}/>:<div className={s.list} aria-label={label}>
      {items.map(item=><div className={`${s.row} ${item.id===selected?s.current:""}`} key={item.id}>
        {item.selectable===false?<div className={s.subject}><GitBranch size={17}/><span><small>{item.eyebrow}</small><strong>{item.title}</strong></span></div>:
        <button type="button" className={s.item} data-workflow-step={item.id} aria-current={item.id===selected?"step":undefined} onClick={()=>onSelect(item.id)}>
          <span className={s.number}>{item.number??<GitBranch size={16}/>}</span>
          <span className={s.itemText}><strong>{item.title}</strong>{item.description&&<span>{item.description}</span>}</span>
          {item.statusLabel&&<span className={s.status} data-status={item.status}>{item.status==="success"&&<Check size={12}/>}<span>{item.statusLabel}</span></span>}
          <ChevronRight className={s.chevron} size={16}/>
        </button>}{item.footer&&<div className={s.footer}>{item.footer}</div>}
      </div>)}
    </div>}
    {view==="graph"&&edges.some(edge=>edge.data?.resultTransfer)&&<p className={s.legend}><span data-kind="order"/>{t("Run order")}<span/>{t("Result passed to another step")}</p>}
    <InspectorDialog title={label} open={expanded} onClose={()=>setExpanded(false)} size="wide">
      {expanded&&<FlowSurface nodes={nodes} edges={edges} nodeTypes={nodeTypes} selected={modalSelection} onSelect={id=>{if(items.find(item=>item.id===id)?.selectable!==false)setModalSelection(id);}} expanded/>}
      <div className={s.modalFooter}><div><strong>{selectedItem?.title}</strong><p>{selectedItem?.description}</p></div><button type="button" disabled={selectedItem?.selectable===false} onClick={()=>{setExpanded(false);onSelect(modalSelection);}}>{t("Open selected step")}<ArrowRight size={15}/></button></div>
    </InspectorDialog>
  </div>;
}
