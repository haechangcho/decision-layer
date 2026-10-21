"use client";

import { useEffect, useId, useRef, useState } from "react";
import { LoaderCircle, Trash2 } from "lucide-react";
import { api, type Recipe } from "@/lib/api";
import { useT } from "@/lib/i18n";
import s from "./recipe-delete.module.css";

export function RecipeDelete({ recipe, onDeleted }: { recipe: Recipe; onDeleted: () => void }) {
  const t = useT();
  const dialog = useRef<HTMLDialogElement>(null);
  const id = useId();
  const [open, setOpen] = useState(false);
  const [latest, setLatest] = useState<Recipe | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!open) return;
    dialog.current?.showModal();
    let active = true;
    setLatest(null); setError("");
    api<Recipe>(`/recipes/${encodeURIComponent(recipe.name)}/edit`)
      .then(value => { if (active) setLatest(value); })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : t("Could not load the Recipe.")); });
    return () => { active = false; };
  }, [open, recipe.name, retry, t]);
  function close() { if (!busy) { dialog.current?.close(); setOpen(false); } }
  async function remove() {
    if (!latest) return;
    setBusy(true); setError("");
    try {
      await api(`/recipes/${encodeURIComponent(recipe.name)}?base_version=${encodeURIComponent(latest.version)}`, { method: "DELETE" });
      dialog.current?.close(); setOpen(false); onDeleted();
    } catch (cause) { setError(t("{error} Check the list again before retrying.", { error: cause instanceof Error ? cause.message : t("Could not archive the Recipe.") })); }
    finally { setBusy(false); }
  }
  return <>
    <button type="button" className={s.trigger} title={t("Archive Recipe")} aria-label={t("Archive Recipe: {name}", { name: recipe.description || recipe.name })} onClick={() => setOpen(true)}><Trash2 size={17} /></button>
    <dialog ref={dialog} className={s.dialog} aria-labelledby={id} aria-describedby={`${id}-description`} onCancel={event => { event.preventDefault(); close(); }} onClose={() => setOpen(false)}>
      <h2 id={id}>{t("Archive this Recipe?")}</h2>
      <p className={s.name}>{recipe.description || recipe.name}</p>
      <p id={`${id}-description`}>{t("Remove it from lists and new executions. Original versions, drafts and existing Runs are retained and can be restored by a publisher.")}</p>
      {!latest && !error && <p role="status">{t("Checking the latest version…")}</p>}
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}><button type="button" disabled={busy} onClick={close} autoFocus>{t("Cancel")}</button>
        {error && <button type="button" disabled={busy} onClick={() => setRetry(value => value + 1)}>{t("Reload")}</button>}
        <button type="button" className={s.danger} disabled={!latest || busy} onClick={remove}>{busy ? <LoaderCircle size={16} /> : <Trash2 size={16} />}{busy ? t("Archiving…") : t("Archive Recipe")}</button></div>
    </dialog>
  </>;
}
