"use client";

import { useId, useRef, useState } from "react";
import { LoaderCircle, Trash2 } from "lucide-react";
import { api, type Run } from "@/lib/api";
import { useT } from "@/lib/i18n";
import s from "./run-delete.module.css";

export function RunDelete({ run, onDeleted, compact = false }: { run: Run; onDeleted: () => void; compact?: boolean }) {
  const t = useT();
  const dialog = useRef<HTMLDialogElement>(null);
  const id = useId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const label = run.plan.question || run.recipe_snapshot?.description || t("this run");

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
      setError(cause instanceof Error ? cause.message : t("Could not delete the run."));
    } finally {
      setBusy(false);
    }
  }

  return <>
    <button type="button" className={compact ? s.compact : s.trigger} title={t(run.running ? "You can delete it when the analysis finishes" : "Delete run")} aria-label={t("Delete run: {name}", { name: label })}
      disabled={!!run.running} onClick={() => dialog.current?.showModal()}><Trash2 size={16} />{!compact && t("Delete record")}</button>
    <dialog ref={dialog} className={s.dialog} aria-labelledby={id} aria-describedby={`${id}-description`}
      onCancel={event => { if (busy) event.preventDefault(); }}>
      <h2 id={id}>{t("Delete this run?")}</h2>
      <p className={s.name}>{label}</p>
      <p id={`${id}-description`}>{t("Its results, queries and validation records are deleted too. Registered Recipes are kept.")}</p>
      {error && <p className={s.error} role="alert">{error}</p>}
      <div className={s.actions}><button type="button" disabled={busy} onClick={close} autoFocus>{t("Cancel")}</button>
        <button type="button" className={s.danger} disabled={busy} onClick={remove}>{busy ? <LoaderCircle size={16} /> : <Trash2 size={16} />}{t(busy ? "Deleting…" : "Delete record")}</button></div>
    </dialog>
  </>;
}
