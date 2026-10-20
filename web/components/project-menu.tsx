"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { ChevronDown, FolderOpen } from "lucide-react";
import { useApi } from "@/lib/hooks";

/** Console context belongs in navigation, not in every page's content. */
export function ProjectMenu() {
  const { data } = useApi<{ name: string; path: string }>("/project");
  const menu = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (menu.current && !menu.current.contains(event.target as Node)) menu.current.open = false;
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && menu.current?.open) {
        menu.current.open = false;
        menu.current.querySelector("summary")?.focus();
      }
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", escape);
    };
  }, []);
  if (!data) return null;
  return <details className="app-project" ref={menu}>
    <summary aria-label={`프로젝트 ${data.name}`}><FolderOpen size={15} /><span>{data.name}</span><ChevronDown size={14} /></summary>
    <div className="app-project-popover">
      <small>현재 프로젝트</small><strong>{data.name}</strong>
      {data.path && <><small>파일 위치</small><code>{data.path}</code></>}
      <Link href="/sources" onClick={() => { if (menu.current) menu.current.open = false; }}>연결 설정 열기</Link>
    </div>
  </details>;
}
