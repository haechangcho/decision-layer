"use client";
import { useT } from "@/lib/i18n";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Pencil, Eye, Code2, Save, Check, Upload, GitCompareArrows, AlignLeft, Undo2 } from "lucide-react";
import { api, ApiError, MethodSource } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { MethodCode, MethodMarkdown, SourceEvidence } from "@/features/methods/method-content";
import { SourceDiff } from "@/features/methods/source-diff";
import styles from "@/features/methods/method-content.module.css";
function EditorLoading() { const t = useT(); return <p role="status">{t("Loading editor…")}</p>; }
const SourceEditor = dynamic(() => import("@/features/methods/source-editor").then(module => module.SourceEditor),
  { ssr:false, loading: EditorLoading });

type Draft = { revision:string; version:string; content:string; validation?:{ status:string; message?:string } | null };
type Asset = { version:string; implementation:string; content?:string | null; code?:MethodSource | null;
  permissions:{ edit:boolean; publish:boolean }; draft?:Draft | null; history:{ version:string; published_at:string }[] };
type TextState = { content:string; version:string };
type View = "edit" | "preview" | "compare";
const nextVersion = (value:string) => { const parts=value.split(".").map(Number);parts[2]++;return parts.join("."); };
const bodyOnly = (text:string) => text.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "");
const same = (a:TextState,b:TextState) => a.content===b.content && a.version===b.version;

export function MethodAssetEditor({ name, onPublished }: { name:string; onPublished:() => void }) {
  const t = useT();
  const { data:info, error, reload } = useApi<Asset>(`/methods/${name}/source`);
  const [editing,setEditing]=useState(false), [text,setText]=useState<TextState>({content:"",version:""});
  const [baseline,setBaseline]=useState<TextState>({content:"",version:""}), [baseVersion,setBaseVersion]=useState("");
  const [draft,setDraft]=useState<Draft|null>(null), [reviewed,setReviewed]=useState(false);
  const [busy,setBusy]=useState<"save"|"check"|"publish"|"format"|null>(null), [message,setMessage]=useState("");
  const [formatUndo,setFormatUndo]=useState<string|null>(null);
  const [failure,setFailure]=useState(""), [view,setView]=useState<View>("edit"), [savedAt,setSavedAt]=useState("");
  const [remote,setRemote]=useState<Asset|null>(null);
  const initialized=useRef(""), pending=useRef(false), navigating=useRef(false), leaveDialog=useRef<HTMLDialogElement>(null);
  const [destination,setDestination]=useState<string|null>(null);
  const skill=info?.implementation==="skill";
  const dirty=!same(text,baseline);
  const needsSave=!draft || !same(text,draft);
  const checked=!!draft && !needsSave && draft.validation?.status==="pass";
  const stale=!!info && !!baseVersion && info.version!==baseVersion;
  const validVersion=/^\d+\.\d+\.\d+$/.test(text.version);

  const hydrate=useCallback((asset:Asset) => {
    const version=asset.draft?.version || nextVersion(asset.version);
    const initial={version,content:asset.draft?.content || (asset.implementation==="skill"
      ? (asset.content || "").replace(/^version:.*$/m,`version: ${version}`) : asset.content || "")};
    setText(initial);setBaseline(initial);setDraft(asset.draft || null);setBaseVersion(asset.version);
    setReviewed(false);setFailure("");setSavedAt("");setFormatUndo(null);initialized.current=name;
  },[name]);
  useEffect(() => {
    if (info && initialized.current!==name) hydrate(info);
  },[info,name,hydrate]);
  useEffect(() => {
    if (!dirty) return;
    const unload=(event:BeforeUnloadEvent) => { if(!navigating.current) {event.preventDefault();event.returnValue="";} };
    const navigate=(event:MouseEvent) => {
      if (event.defaultPrevented || event.button!==0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link=(event.target as Element).closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || link.target==="_blank" || link.hasAttribute("download")) return;
      const target=new URL(link.href,location.href);
      if (target.href===location.href || target.pathname===location.pathname && target.search===location.search && target.hash) return;
      event.preventDefault();event.stopPropagation();setDestination(link.href);
    };
    window.addEventListener("beforeunload",unload);
    document.addEventListener("click",navigate,true);
    return () => { window.removeEventListener("beforeunload",unload);document.removeEventListener("click",navigate,true); };
  },[dirty]);
  useEffect(() => { if(destination) leaveDialog.current?.showModal(); },[destination]);

  function change(value:string, version?:string) {
    const header=skill ? value.match(/^---\r?\n([\s\S]*?)\r?\n---/)?.[1] : undefined;
    const declared=header?.match(/^version:\s*["']?(\d+\.\d+\.\d+)["']?\s*$/m)?.[1];
    setText({content:value,version:version || declared || text.version});setReviewed(false);setFailure("");setMessage("");setFormatUndo(null);
  }
  async function formatCode() {
    if (pending.current || skill || !info?.permissions.edit || !text.content.trim()) return;
    pending.current=true;setBusy("format");setFailure("");setMessage("");
    const original=text.content;
    try {
      const result=await api<{content:string;changed:boolean}>(`/methods/${name}/source:format`,{body:{content:original}});
      if (result.changed) {
        change(result.content);setFormatUndo(original);
        setMessage(t("Code formatted. Review changes before saving."));
      } else setMessage(t("The code already uses the shared Python format."));
    } catch(error) {setFailure(error instanceof Error ? error.message : t("Could not format the code."));}
    finally {pending.current=false;setBusy(null);}
  }
  async function save():Promise<Draft> {
    const result=await api<Draft>(`/methods/${name}/draft`,{ method:"PUT",
      body:{base_version:baseVersion, revision:draft?.revision || null, ...text} });
    setDraft(result);setBaseline({content:result.content,version:result.version});setSavedAt(new Date().toLocaleTimeString());
    return result;
  }
  async function action(kind:"save"|"check"|"publish"):Promise<boolean> {
    if (!info || pending.current || stale || !validVersion || !text.content.trim()) return false;
    if (kind!=="save" && !info.permissions.publish && !skill || kind==="check" && !skill && !reviewed) return false;
    pending.current=true;setBusy(kind);setFailure("");setMessage("");
    try {
      if (kind==="save") {
        await save();setMessage(t("Draft saved. Execution still uses the published version."));
      } else if (kind==="check") {
        const saved=needsSave ? await save() : draft!;
        const result=await api<Draft>(`/methods/${name}/draft:check`,{body:{revision:saved.revision,reviewed}});
        setDraft(result);
      } else {
        if (!checked || !reviewed || !info.permissions.publish) return false;
        await api(`/methods/${name}/draft:publish`,{body:{revision:draft!.revision,reviewed}});
        // Fetch the exact new base before reopening; no stale revision/version is reused.
        try { hydrate(await api<Asset>(`/methods/${name}/source`)); }
        catch {setBaseline(text);setDraft(null);setReviewed(false);initialized.current="";}
        setEditing(false);reload();onPublished();setMessage(t("Published v{version}. Existing Recipes and Runs keep their versions.", { version: text.version }));
      }
      return true;
    } catch(error) { setFailure(error instanceof Error ? error.message : t("Could not save the changes."));return false; }
    finally { pending.current=false;setBusy(null); }
  }
  function leave() { navigating.current=true;location.assign(destination!); }
  async function saveAndLeave() {
    if (await action("save")) { navigating.current=true;setDestination(null);leaveDialog.current?.close();location.assign(destination!); }
  }
  async function inspectRemote() {
    try { setRemote(await api<Asset>(`/methods/${name}/source`)); }
    catch(error) {setFailure(error instanceof Error ? error.message : t("Could not check the server state."));}
  }
  function keepLocalAgainstRemote() {
    if (!remote) return;
    const version=nextVersion(remote.version);
    setBaseVersion(remote.version);setDraft(remote.draft || null);
    setText(current => ({version,content:skill ? current.content.replace(/^version:.*$/m,`version: ${version}`) : current.content}));
    setReviewed(false);setRemote(null);setFailure("");setMessage(t("Changes kept. Check and save to replace the server draft."));reload();
  }
  if (error instanceof ApiError && error.status === 401 && !info) return <section className={styles.panel}><p>{t("Sign in to view server code, or edit the project files locally.")}</p><Link href="/sources">{t("Check connection settings")}</Link></section>;
  if (error && !info) return <section className={styles.panel}><p role="alert">{t("Could not load editing information:")} {error.message}</p><button onClick={reload}>{t("Retry")}</button></section>;
  if (!info) return <section className={styles.panel}><p role="status">{t("Loading editing permissions…")}</p></section>;
  const status=busy ? ({save:t("Saving…"),check:t("Checking syntax and registration…"),publish:t("Publishing…"),format:t("Formatting code…")}[busy])
    : dirty ? t("Unsaved changes") : checked ? t("Registration checked / not published") : draft ? t("Draft saved on server") : t("Published version");
  return <section id="method-editor" className={styles.panel} aria-label={t("Analysis source and editing")} aria-busy={!!busy}>
    <div className={`${styles.heading} ${editing ? styles.editorToolbar : ""}`}>
      <div><h2>{skill ? "SKILL.md" : t("Authorable Python code")}</h2>
        <p className={styles.muted}><span className={dirty ? styles.unsaved : styles.badge}>{status}</span> · v{info.version}{editing && t(" → Draft v{version}", { version: text.version })}{savedAt && t(" · Saved {time}", { time: savedAt })}</p></div>
      {info.permissions.edit && info.content && <div className={styles.controls}>
        {editing && <button className={`${styles.button} ${styles.secondary}`} disabled={!!busy || !needsSave || !validVersion} onClick={() => action("save")}><Save size={15}/>{t("Save draft")}</button>}
        <button className={`${styles.button} ${styles.secondary}`} disabled={!!busy} onClick={() => {setEditing(!editing);setView("edit");}}><Pencil size={15}/>{editing ? t("Back to reading") : draft || dirty ? t("Continue editing") : skill ? t("Edit SKILL.md") : t("Edit Python")}</button>
      </div>}
    </div>
    {!editing && <>{skill ? <pre className={styles.skillSource} aria-label={t("Original Skill Markdown")} tabIndex={0}><code>{info.content}</code></pre> : <SourceEvidence source={info.code} />}
      <p className={styles.muted}>{!info.permissions.edit && <>{t("Read-only.")} </>}{t(skill ? "Edit the project's SKILL.md file." : "Edit the project's method.py file.")}</p>
      {dirty && <p className={styles.notice}>{t("Unsaved edits kept. Continue editing to save them.")}</p>}
      {draft && <p className={styles.notice}>v{draft.version}  {t("Draft saved; publish to apply it.")}</p>}</>}
    {editing && <p className={styles.notice}>{t("Publishing updates the server only. Edit project files separately.")}</p>}
    {editing && <div className={styles.workspace}>
      <div className={styles.versionBar}><label className={styles.versionField}>{t("New version to publish")}<input aria-label={t("Published version")} value={text.version} disabled={!!busy} aria-invalid={!validVersion}
        onChange={event => change(skill ? text.content.replace(/^version:.*$/m,`version: ${event.target.value}`) : text.content,event.target.value)} /></label>
        <p className={styles.muted}>{t("Check and publish to apply your changes.")}</p></div>
      {!validVersion && <p role="alert" className={styles.error}>{t("Enter a version such as 1.0.1.")}</p>}
      {stale && <div role="alert" className={styles.notice}>{t("The published version changed. Your edits are preserved.")} <button className={styles.textButton} onClick={inspectRemote}>{t("Check server state")}</button></div>}
      <div className={styles.tabs} role="tablist" aria-label={t("Editor view")}>
        {([['edit',t("Edit"),Code2],['preview',t("Preview"),Eye],['compare',t("Compare changes"),GitCompareArrows]] as const).map(([key,label,Icon]) =>
          <button key={key} type="button" role="tab" id={`asset-tab-${key}`} aria-selected={view===key} tabIndex={view===key ? 0 : -1} aria-controls="asset-editor-panel" onClick={() => setView(key)}
            onKeyDown={event => {
              const views:View[]=["edit","preview","compare"];
              const offset=event.key==="ArrowRight" ? 1 : event.key==="ArrowLeft" ? -1 : 0;
              if(offset) {event.preventDefault();const next=views[(views.indexOf(view)+offset+3)%3];setView(next);document.getElementById(`asset-tab-${next}`)?.focus();}
            }}><Icon size={15}/>{label}</button>)}
      </div>
      <div id="asset-editor-panel" role="tabpanel" aria-labelledby={`asset-tab-${view}`}>
        <div hidden={view!=="edit"} className={styles.editorFrame}>
          <div className={styles.fileBar}><code>{skill ? "SKILL.md" : `${name}.py`}</code><span>UTF-8 · {text.content.split("\n").length}{t("lines")}</span>
            {!skill && <div className={styles.formatControls}>
              {formatUndo !== null && <button type="button" className={styles.textButton} disabled={!!busy} onClick={() => change(formatUndo)}><Undo2 size={14}/>{t("Undo formatting")}</button>}
              <button type="button" className={styles.formatButton} disabled={!!busy || !text.content.trim()} onClick={formatCode}><AlignLeft size={14}/>{busy==="format" ? t("Formatting…") : t("Format code")}</button>
            </div>}
          </div>
          <SourceEditor value={text.content} language={skill ? "markdown" : "python"} onChange={value => change(value)} onSave={() => action("save")} onFormat={skill ? undefined : formatCode} readOnly={busy==="publish" || busy==="format"} />
        </div>
        {view==="preview" && <div className={styles.preview}>{skill ? <MethodMarkdown content={bodyOnly(text.content)} /> : <MethodCode content={text.content} />}</div>}
        {view==="compare" && <SourceDiff before={info.content || ""} after={text.content} baseVersion={baseVersion} version={text.version} />}
      </div>
      <p id="source-editor-help" className={styles.muted}>{t("⌘ / Ctrl+S save / ⌘ / Ctrl+F find and replace / ⌘ / Ctrl+] indent")}{!skill && t("/ Shift+Alt+F format")}  {t("/ Tab next control")}</p>
      <div className={styles.publishPanel}>
        <label className={styles.review}><input type="checkbox" checked={reviewed} disabled={!!busy} onChange={event => setReviewed(event.target.checked)}/>
          {skill ? t("I reviewed the changed instructions and input requirements.") : t("I reviewed and trust this code to run with server permissions.")}</label>
        {!skill && <p className={styles.muted}>{t("Python checks run code without a security sandbox. Analytical accuracy is not checked.")}</p>}
        <div className={styles.controls}>
          <button className={`${styles.button} ${styles.secondary}`} disabled={!!busy || stale || !validVersion || !text.content.trim() || !skill && (!reviewed || !info.permissions.publish)} onClick={() => action("check")}><Check size={15}/>{busy==="check" ? t("Checking…") : t("Check syntax and registration")}</button>
          <button className={styles.button} disabled={!!busy || stale || !checked || !reviewed || !info.permissions.publish} onClick={() => action("publish")}><Upload size={15}/>{busy==="publish" ? t("Publishing…") : t("Publish v{version}", { version: text.version })}</button>
        </div>
        {!checked && <p className={styles.muted}>{!skill && !reviewed ? t("Confirm the code review to run registration checks.") : t("Checks save the draft. Publish after they pass.")}</p>}
        {!info.permissions.publish && <p className={styles.notice}>{t("You only have draft editing permission.")} {t(skill ? "Publication requires an operator with Method publishing permission." : "Python registration checks and publication require an operator with Method publishing permission.")}</p>}
        {draft?.validation && !needsSave && <p className={draft.validation.status==="pass" ? styles.success : styles.error} role={draft.validation.status==="fail" ? "alert" : "status"}>
          {draft.validation.status==="pass" ? t("Syntax and registration passed. Data and analysis are unchecked.") : draft.validation.message}</p>}
      </div>
    </div>}
    {message && <p className={styles.success} role="status">{message}</p>}
    {failure && <div className={styles.notice} role="alert"><p>{failure}</p><p>{t("Edits kept. Review the server draft before retrying.")}</p><button className={styles.textButton} onClick={inspectRemote}>{t("Check server state")}</button></div>}
    {remote && <div className={styles.notice} aria-label={t("Compare the server draft with your changes")}><h3>{t("Server draft and your changes")}</h3><div className={styles.compare}>
      <div><h3>{t("Server v")}{remote.draft?.version || remote.version}</h3><MethodCode content={remote.draft?.content || remote.content || ""} language={skill ? "markdown" : "python"}/></div>
      <div><h3>{t("Your changes v")}{text.version}</h3><MethodCode content={text.content} language={skill ? "markdown" : "python"}/></div>
    </div><p>{t("The next save will replace the server draft with your changes.")}</p><div className={styles.controls}>
      <button className={styles.button} onClick={keepLocalAgainstRemote}>{t("Keep your changes and update baseline")}</button>
      <button className={`${styles.button} ${styles.secondary}`} onClick={() => {hydrate(remote);setRemote(null);}}>{t("Replace with server content")}</button>
      <button className={styles.textButton} onClick={() => setRemote(null)}>{t("Close comparison")}</button>
    </div></div>}
    {!!info.history.length && !editing && <section className={styles.file}><h3>{t("Publication history")}</h3><ul>{info.history.map(item => <li key={item.version}>v{item.version} · {new Date(item.published_at).toLocaleString()}</li>)}</ul></section>}
    <dialog ref={leaveDialog} className={styles.leaveDialog} aria-labelledby="leave-editor-title" onCancel={() => setDestination(null)}>
      <h2 id="leave-editor-title">{t("Save your changes?")}</h2><p>{t("Some changes have not been saved to the server.")}</p>
      {failure && <p role="alert" className={styles.error}>{failure}</p>}
      <div className={styles.controls}><button className={styles.button} disabled={!!busy} onClick={saveAndLeave}>{t("Save and leave")}</button>
        <button className={`${styles.button} ${styles.secondary}`} onClick={() => {setDestination(null);leaveDialog.current?.close();}}>{t("Keep editing")}</button>
        <button className={styles.textButton} onClick={leave}>{t("Leave without saving")}</button></div>
    </dialog>
  </section>;
}
