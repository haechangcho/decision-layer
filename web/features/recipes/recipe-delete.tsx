"use client";

import { useEffect, useId, useRef, useState } from "react";
import { LoaderCircle, Trash2 } from "lucide-react";
import { api, type Recipe } from "@/lib/api";
import s from "./recipe-delete.module.css";

export function RecipeDelete({ recipe, onDeleted }: { recipe: Recipe; onDeleted: () => void }) {
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
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Recipe를 불러오지 못했습니다."); });
    return () => { active = false; };
  }, [open, recipe.name, retry]);
  function close() { if (!busy) { dialog.current?.close(); setOpen(false); } }
  async function remove() {
    if (!latest) return;
    setBusy(true); setError("");
    try {
      await api(`/recipes/${encodeURIComponent(recipe.name)}?base_version=${encodeURIComponent(latest.version)}`, { method: "DELETE" });
      dialog.current?.close(); setOpen(false); onDeleted();
    } catch (cause) { setError(`${cause instanceof Error ? cause.message : "삭제하지 못했습니다."} 목록을 다시 확인한 후 시도하세요.`); }
    finally { setBusy(false); }
  }
  return <>
    <button type="button" className={s.trigger} title="Recipe 삭제" aria-label={`Recipe 삭제: ${recipe.description || recipe.name}`} onClick={() => setOpen(true)}><Trash2 size={17} /></button>
    <dialog ref={dialog} className={s.dialog} aria-labelledby={id} aria-describedby={`${id}-description`} onCancel={event => { event.preventDefault(); close(); }} onClose={() => setOpen(false)}>
      <h2 id={id}>Recipe를 삭제할까요?</h2>
      <p className={s.name}>{recipe.description || recipe.name}</p>
      <p id={`${id}-description`}>초안을 포함한 모든 버전이 삭제되며, 이후 Web과 MCP에서 사용할 수 없습니다. 기존 실행 기록과 분석 결과는 유지됩니다.</p>
      {!latest && !error && <p role="status">최신 버전 확인 중…</p>}
      {error && <p role="alert" className={s.error}>{error}</p>}
      <div className={s.actions}><button type="button" disabled={busy} onClick={close} autoFocus>취소</button>
        {error && <button type="button" disabled={busy} onClick={() => setRetry(value => value + 1)}>다시 불러오기</button>}
        <button type="button" className={s.danger} disabled={!latest || busy} onClick={remove}>{busy ? <LoaderCircle size={16} /> : <Trash2 size={16} />}{busy ? "삭제 중…" : "Recipe 삭제"}</button></div>
    </dialog>
  </>;
}
