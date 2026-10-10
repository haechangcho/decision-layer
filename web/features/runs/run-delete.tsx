"use client";

import { useId, useRef, useState } from "react";
import { LoaderCircle, Trash2 } from "lucide-react";
import { api, type Run } from "@/lib/api";
import s from "./run-delete.module.css";

export function RunDelete({ run, onDeleted, compact = false }: { run: Run; onDeleted: () => void; compact?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const id = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const label = run.plan.question || run.recipe_snapshot?.description || "이 실행 기록";

  function close() {
    if (!busy) dialog.current?.close();
  }

  async function remove() {
    setBusy(true);
    setError("");
    try {
      await api(`/runs/${encodeURIComponent(run.id)}`, { method: "DELETE" });
      dialog.current?.close();
      onDeleted();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "실행 기록을 삭제하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return <>
    <button type="button" className={compact ? s.compact : s.trigger} title={run.running ? "분석이 끝나면 삭제할 수 있습니다" : "실행 기록 삭제"} aria-label={`실행 기록 삭제: ${label}`}
      disabled={!!run.running} onClick={() => dialog.current?.showModal()}><Trash2 size={16} />{!compact && "기록 삭제"}</button>
    <dialog ref={dialog} className={s.dialog} aria-labelledby={id} aria-describedby={`${id}-description`}
      onCancel={event => { if (busy) event.preventDefault(); }}>
      <h2 id={id}>실행 기록을 삭제할까요?</h2>
      <p className={s.name}>{label}</p>
      <p id={`${id}-description`}>분석 결과와 쿼리, 검증 기록이 함께 삭제됩니다. 이미 등록한 Recipe는 유지됩니다.</p>
      {error && <p className={s.error} role="alert">{error}</p>}
      <div className={s.actions}><button type="button" disabled={busy} onClick={close} autoFocus>취소</button>
        <button type="button" className={s.danger} disabled={busy} onClick={remove}>{busy ? <LoaderCircle size={16} /> : <Trash2 size={16} />}{busy ? "삭제 중…" : "기록 삭제"}</button></div>
    </dialog>
  </>;
}
