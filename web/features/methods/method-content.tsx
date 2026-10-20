"use client";
import { useState } from "react";
import { InspectorDialog } from "@/components/inspector-dialog";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { MethodSource } from "@/lib/api";
import styles from "./method-content.module.css";

export function MethodMarkdown({ content }: { content: string }) {
  return <div className={styles.document}><Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}
    components={{ img: ({ alt }) => <span>{alt}</span>, a: ({ children, href }) => <a href={href} rel="noreferrer noopener">{children}</a> }}>{content}</Markdown></div>;
}
export function MethodCode({ content, language="python" }: { content: string; language?: string }) {
  const longest = Math.max(3, ...(content.match(/`+/g) || []).map(part => part.length));
  const fence = "`".repeat(longest + 1);
  return <div className={`${styles.document} ${styles.code}`}><Markdown rehypePlugins={[rehypeHighlight]}>{`${fence}${language}\n${content}\n${fence}`}</Markdown></div>;
}
export function SourceEvidence({ source, historical=false }: { source?: MethodSource | null; historical?: boolean }) {
  const [open, setOpen] = useState(false);
  const [filename, setFilename] = useState("");
  if (!source?.available || !source.files.length) return <p className={styles.muted}>{historical ? "이 Run에는 실행 당시 코드가 기록되지 않았습니다. 현재 코드로 대신 표시하지 않습니다." : "설치된 패키지에서 소스 코드를 읽을 수 없습니다."}</p>;
  const file = source.files.find(item => item.name === filename) ?? source.files[0];
  const original = <div className={styles.originalSource}>
    <label>소스 파일<select aria-label="소스 파일" value={file.name} onChange={event => setFilename(event.target.value)}>{source.files.map(item => <option key={item.name} value={item.name}>{item.name.startsWith("dl_method_assets.") ? "게시한 Python 모듈" : item.name}</option>)}</select></label>
    <MethodCode content={file.content} /><p className={styles.hash}>SHA-256 {file.sha256}</p>
  </div>;
  return <div aria-label={historical ? "실행 당시 Python 코드" : "현재 Python 코드"}>
    <div className={styles.sourceToolbar}><p className={styles.muted}>{historical ? "실행 당시 보존한 코드" : "현재 등록 시 보존한 코드"} / v{source.version}</p>
      {source.authoring_content && <button type="button" className="ghost" onClick={() => setOpen(true)}>원본 파일 보기</button>}</div>
    {source.authoring_content ? <div aria-label="이 분석의 작성 코드"><MethodCode content={source.authoring_content} /></div> : original}
    <InspectorDialog title="Python 원본 파일" open={open} onClose={() => setOpen(false)}><p>보존된 진입 모듈과 보조 코드입니다. 외부 라이브러리 전체를 포함하지 않습니다.</p>{original}</InspectorDialog>
  </div>;
}
