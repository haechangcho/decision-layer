"use client";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { Pencil, Eye, Code2, Save, Check, Upload, GitCompareArrows, AlignLeft, Undo2 } from "lucide-react";
import { api, ApiError, MethodSource } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { MethodCode, MethodMarkdown, SourceEvidence } from "@/components/method-content";
import { SourceDiff } from "@/components/source-diff";
import styles from "@/components/method-content.module.css";
const SourceEditor = dynamic(() => import("@/components/source-editor").then(module => module.SourceEditor),
  { ssr:false, loading:() => <p role="status">편집기를 준비하고 있습니다…</p> });

type Draft = { revision:string; version:string; content:string; validation?:{ status:string; message?:string } | null };
type Asset = { version:string; implementation:string; content?:string | null; code?:MethodSource | null;
  permissions:{ edit:boolean; publish:boolean }; draft?:Draft | null; history:{ version:string; published_at:string }[] };
type TextState = { content:string; version:string };
type View = "edit" | "preview" | "compare";
const nextVersion = (value:string) => { const parts=value.split(".").map(Number);parts[2]++;return parts.join("."); };
const bodyOnly = (text:string) => text.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "");
const same = (a:TextState,b:TextState) => a.content===b.content && a.version===b.version;

export function MethodAssetEditor({ name, onPublished, children }: { name:string; onPublished:() => void; children?:ReactNode }) {
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
        setMessage("코드 형식을 정리했습니다. 변경 비교에서 확인한 뒤 초안을 저장하세요.");
      } else setMessage("이미 공통 Python 형식입니다.");
    } catch(error) {setFailure(error instanceof Error ? error.message : "코드를 정리하지 못했습니다.");}
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
        await save();setMessage("초안을 저장했습니다. 실행에는 아직 반영되지 않았습니다.");
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
        setEditing(false);reload();onPublished();setMessage(`v${text.version}을 게시했습니다. 고정된 Recipe와 과거 Run은 기존 버전을 유지합니다.`);
      }
      return true;
    } catch(error) { setFailure(error instanceof Error ? error.message : "변경을 저장하지 못했습니다.");return false; }
    finally { pending.current=false;setBusy(null); }
  }
  function leave() { navigating.current=true;location.assign(destination!); }
  async function saveAndLeave() {
    if (await action("save")) { navigating.current=true;setDestination(null);leaveDialog.current?.close();location.assign(destination!); }
  }
  async function inspectRemote() {
    try { setRemote(await api<Asset>(`/methods/${name}/source`)); }
    catch(error) {setFailure(error instanceof Error ? error.message : "서버 상태를 확인하지 못했습니다.");}
  }
  function keepLocalAgainstRemote() {
    if (!remote) return;
    const version=nextVersion(remote.version);
    setBaseVersion(remote.version);setDraft(remote.draft || null);
    setText(current => ({version,content:skill ? current.content.replace(/^version:.*$/m,`version: ${version}`) : current.content}));
    setReviewed(false);setRemote(null);setFailure("");setMessage("내 변경을 유지했습니다. 다시 검사하고 저장하면 확인한 서버 초안을 대체합니다.");reload();
  }
  if (error instanceof ApiError && error.status === 401 && !info) return <section className={styles.panel}>{children}<p>서버의 코드 보기와 편집에는 연결 인증이 필요합니다. 프로젝트 Method는 로컬 method.py 파일에서도 확인하고 수정할 수 있습니다.</p><Link href="/sources">연결 설정 확인</Link></section>;
  if (error && !info) return <section className={styles.panel}>{children}<p role="alert">편집 정보를 가져오지 못했습니다: {error.message}</p><button onClick={reload}>다시 시도</button></section>;
  if (!info) return <section className={styles.panel}>{children}<p role="status">편집 권한을 불러오고 있습니다…</p></section>;
  const status=busy ? ({save:"저장 중…",check:"구문·등록 검사 중…",publish:"게시 중…",format:"코드 정리 중…"}[busy])
    : dirty ? "저장하지 않은 변경" : checked ? "등록 검사 통과 · 게시 전" : draft ? "서버에 저장된 초안" : "게시된 버전";
  return <section id="method-editor" className={styles.panel} aria-label="분석 자산 코드와 편집" aria-busy={!!busy}>
    <div className={`${styles.heading} ${editing ? styles.editorToolbar : ""}`}>
      <div><h2>{skill ? "Skill.md" : "Python 작성 코드"}</h2>
        <p className={styles.muted}><span className={dirty ? styles.unsaved : styles.badge}>{status}</span> · 게시 v{info.version}{editing && ` → 초안 v${text.version}`}{savedAt && ` · ${savedAt} 저장`}</p></div>
      {info.permissions.edit && info.content && <div className={styles.controls}>
        {editing && <button className={`${styles.button} ${styles.secondary}`} disabled={!!busy || !needsSave || !validVersion} onClick={() => action("save")}><Save size={15}/>초안 저장</button>}
        <button className={`${styles.button} ${styles.secondary}`} disabled={!!busy} onClick={() => {setEditing(!editing);setView("edit");}}><Pencil size={15}/>{editing ? "읽기로 돌아가기" : draft || dirty ? "편집 이어서" : skill ? "Skill.md 편집" : "Python 편집"}</button>
      </div>}
    </div>
    {!editing && <>{skill ? children || <MethodMarkdown content={bodyOnly(info.content || "")} /> : <SourceEvidence source={info.code} />}
      {dirty && <p className={styles.notice}>작성 중인 내용은 이 화면에 유지됩니다. 편집을 이어서 초안으로 저장하세요.</p>}
      {draft && <p className={styles.notice}>v{draft.version} 초안이 저장되어 있습니다. 게시 전까지 실행에는 반영되지 않습니다.</p>}</>}
    {!info.permissions.edit && <p className={styles.muted}>읽기 전용입니다. 운영자가 UI 편집을 활성화하고 Method 편집 권한을 부여하면 수정할 수 있습니다.</p>}
    {editing && <div className={styles.workspace}>
      <div className={styles.versionBar}><label className={styles.versionField}>게시할 새 버전<input aria-label="게시 버전" value={text.version} disabled={!!busy} aria-invalid={!validVersion}
        onChange={event => change(skill ? text.content.replace(/^version:.*$/m,`version: ${event.target.value}`) : text.content,event.target.value)} /></label>
        <p className={styles.muted}>내용을 수정하고 검사한 뒤 게시합니다. 초안 저장만으로 실행이 바뀌지 않습니다.</p></div>
      {!validVersion && <p role="alert" className={styles.error}>버전은 1.0.1 형식으로 입력하세요.</p>}
      {stale && <div role="alert" className={styles.notice}>게시된 버전이 변경되었습니다. 작성 내용은 유지됩니다. <button className={styles.textButton} onClick={inspectRemote}>서버 상태 확인</button></div>}
      <div className={styles.tabs} role="tablist" aria-label="편집 보기">
        {([['edit','편집',Code2],['preview','미리보기',Eye],['compare','변경 비교',GitCompareArrows]] as const).map(([key,label,Icon]) =>
          <button key={key} type="button" role="tab" id={`asset-tab-${key}`} aria-selected={view===key} tabIndex={view===key ? 0 : -1} aria-controls="asset-editor-panel" onClick={() => setView(key)}
            onKeyDown={event => {
              const views:View[]=["edit","preview","compare"];
              const offset=event.key==="ArrowRight" ? 1 : event.key==="ArrowLeft" ? -1 : 0;
              if(offset) {event.preventDefault();const next=views[(views.indexOf(view)+offset+3)%3];setView(next);document.getElementById(`asset-tab-${next}`)?.focus();}
            }}><Icon size={15}/>{label}</button>)}
      </div>
      <div id="asset-editor-panel" role="tabpanel" aria-labelledby={`asset-tab-${view}`}>
        <div hidden={view!=="edit"} className={styles.editorFrame}>
          <div className={styles.fileBar}><code>{skill ? "SKILL.md" : `${name}.py`}</code><span>UTF-8 · {text.content.split("\n").length}줄</span>
            {!skill && <div className={styles.formatControls}>
              {formatUndo !== null && <button type="button" className={styles.textButton} disabled={!!busy} onClick={() => change(formatUndo)}><Undo2 size={14}/>정리 되돌리기</button>}
              <button type="button" className={styles.formatButton} disabled={!!busy || !text.content.trim()} onClick={formatCode}><AlignLeft size={14}/>{busy==="format" ? "정리 중…" : "코드 정리"}</button>
            </div>}
          </div>
          <SourceEditor value={text.content} language={skill ? "markdown" : "python"} onChange={value => change(value)} onSave={() => action("save")} onFormat={skill ? undefined : formatCode} readOnly={busy==="publish" || busy==="format"} />
        </div>
        {view==="preview" && <div className={styles.preview}>{skill ? <MethodMarkdown content={bodyOnly(text.content)} /> : <MethodCode content={text.content} />}</div>}
        {view==="compare" && <SourceDiff before={info.content || ""} after={text.content} baseVersion={baseVersion} version={text.version} />}
      </div>
      <p id="source-editor-help" className={styles.muted}>⌘ / Ctrl+S 저장 · ⌘ / Ctrl+F 찾기·바꾸기 · ⌘ / Ctrl+] 들여쓰기{!skill && " · Shift+Alt+F 코드 정리 (Ruff · 88열 · 공백 4칸)"} · Tab 다음 컨트롤</p>
      <div className={styles.publishPanel}>
        <label className={styles.review}><input type="checkbox" checked={reviewed} disabled={!!busy} onChange={event => setReviewed(event.target.checked)}/>
          {skill ? "변경한 지침과 입력 조건을 검토했습니다." : "코드를 검토했으며, 서버 권한으로 실행할 수 있는 신뢰한 코드임을 확인했습니다."}</label>
        {!skill && <p className={styles.muted}>Python 등록 검사는 코드를 실행합니다. 분석 정확성 검사나 보안 sandbox는 아닙니다.</p>}
        <div className={styles.controls}>
          <button className={`${styles.button} ${styles.secondary}`} disabled={!!busy || stale || !validVersion || !text.content.trim() || !skill && (!reviewed || !info.permissions.publish)} onClick={() => action("check")}><Check size={15}/>{busy==="check" ? "검사 중…" : "구문·등록 검사"}</button>
          <button className={styles.button} disabled={!!busy || stale || !checked || !reviewed || !info.permissions.publish} onClick={() => action("publish")}><Upload size={15}/>{busy==="publish" ? "게시 중…" : `v${text.version} 게시`}</button>
        </div>
        {!checked && <p className={styles.muted}>{!skill && !reviewed ? "코드 검토를 확인하면 등록 검사를 실행할 수 있습니다." : "검사할 때 초안을 먼저 저장합니다. 검사 통과 후 게시할 수 있습니다."}</p>}
        {!info.permissions.publish && <p className={styles.notice}>초안 편집 권한만 있습니다. {skill ? "게시는" : "Python 등록 검사·게시는"} Method 게시 권한이 있는 운영자에게 요청하세요.</p>}
        {draft?.validation && !needsSave && <p className={draft.validation.status==="pass" ? styles.success : styles.error} role={draft.validation.status==="fail" ? "alert" : "status"}>
          {draft.validation.status==="pass" ? "구문·등록 검사를 통과했습니다. 실제 데이터·분석 품질은 검사하지 않았습니다." : draft.validation.message}</p>}
      </div>
    </div>}
    {message && <p className={styles.success} role="status">{message}</p>}
    {failure && <div className={styles.notice} role="alert"><p>{failure}</p><p>작성 내용은 유지됩니다. 충돌한 경우 서버 초안을 확인한 뒤 다시 저장하세요.</p><button className={styles.textButton} onClick={inspectRemote}>서버 상태 확인</button></div>}
    {remote && <div className={styles.notice} aria-label="서버 초안과 내 변경 비교"><h3>서버 초안과 내 변경</h3><div className={styles.compare}>
      <div><h3>서버 v{remote.draft?.version || remote.version}</h3><MethodCode content={remote.draft?.content || remote.content || ""} language={skill ? "markdown" : "python"}/></div>
      <div><h3>내 변경 v{text.version}</h3><MethodCode content={text.content} language={skill ? "markdown" : "python"}/></div>
    </div><p>내 변경을 유지하면 다음 저장 시 확인한 서버 초안을 대체합니다. 자동으로 덮어쓰지 않습니다.</p><div className={styles.controls}>
      <button className={styles.button} onClick={keepLocalAgainstRemote}>내 변경을 유지하고 기준 갱신</button>
      <button className={`${styles.button} ${styles.secondary}`} onClick={() => {hydrate(remote);setRemote(null);}}>서버 내용으로 교체</button>
      <button className={styles.textButton} onClick={() => setRemote(null)}>비교 닫기</button>
    </div></div>}
    {!!info.history.length && !editing && <details className={styles.file}><summary>게시 이력</summary><ul>{info.history.map(item => <li key={item.version}>v{item.version} · {new Date(item.published_at).toLocaleString()}</li>)}</ul></details>}
    <dialog ref={leaveDialog} className={styles.leaveDialog} aria-labelledby="leave-editor-title" onCancel={() => setDestination(null)}>
      <h2 id="leave-editor-title">작성한 내용을 저장할까요?</h2><p>아직 서버에 저장하지 않은 변경이 있습니다.</p>
      {failure && <p role="alert" className={styles.error}>{failure}</p>}
      <div className={styles.controls}><button className={styles.button} disabled={!!busy} onClick={saveAndLeave}>저장하고 이동</button>
        <button className={`${styles.button} ${styles.secondary}`} onClick={() => {setDestination(null);leaveDialog.current?.close();}}>계속 편집</button>
        <button className={styles.textButton} onClick={leave}>저장하지 않고 이동</button></div>
    </dialog>
  </section>;
}
