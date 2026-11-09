"use client";

import { useState } from "react";
import { Pencil } from "lucide-react";
import { InspectorDialog } from "@/components/inspector-dialog";
import { api, type Run } from "@/lib/api";
import { useT } from "@/lib/i18n";
import s from "./run-title.module.css";

export function RunTitle({ run, mine, onSaved }: { run: Run; mine: boolean; onSaved: () => void }) {
  const t = useT();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(`/runs/${encodeURIComponent(run.id)}/title`, { method: "PATCH", body: { title, base_revision: revision } });
      setEditing(false);
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("Could not save the title."));
    } finally { setBusy(false); }
  }

  return <>
    <div className={s.heading}><h1>{run.title || t("Analysis result")}</h1>{mine && <button type="button" className={s.edit} disabled={!!run.running} aria-label={t("Edit analysis title")} title={t("Edit analysis title")}
      onClick={() => { setTitle(run.title || ""); setRevision(run.title_revision ?? 0); setError(""); setEditing(true); }}><Pencil size={16} /></button>}</div>
    <InspectorDialog title={t("Edit analysis title")} size="compact" open={editing} onClose={() => setEditing(false)}>
      <form onSubmit={save} className={s.form}>
        <label>{t("Analysis title")}<input autoFocus required maxLength={80} value={title} onChange={event => setTitle(event.target.value)} /></label>
        {error && <p role="alert">{error}</p>}
        <div className={s.actions}><button type="button" className="ghost" disabled={busy} onClick={() => setEditing(false)}>{t("Cancel")}</button><button type="submit" disabled={busy || !title.trim()}>{t(busy ? "Saving…" : "Save")}</button></div>
      </form>
    </InspectorDialog>
  </>;
}
