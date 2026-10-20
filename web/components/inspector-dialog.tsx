"use client";

import { type ReactNode, useEffect, useRef } from "react";
import { X } from "lucide-react";
import styles from "./inspector-dialog.module.css";

/** Secondary evidence stays in context without displacing the main workspace. */
export function InspectorDialog({ title, open, onClose, children }: {
  title: string; open: boolean; onClose: () => void; children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current;
    if (open && node && !node.open) node.showModal();
    if (!open && node?.open) node.close();
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [open]);
  return <dialog ref={dialog} className={styles.dialog} aria-label={title} onClose={onClose}>
    <header><div><span>DECISION LAYER</span><h2>{title}</h2></div><button type="button" aria-label="닫기" onClick={() => dialog.current?.close()}><X size={20} /></button></header>
    <div className={styles.body}>{children}</div>
  </dialog>;
}
