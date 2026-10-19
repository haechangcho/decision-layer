"use client";
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
  if (!source?.available || !source.files.length) return <p className={styles.muted}>{historical ? "이 Run에는 실행 당시 코드가 기록되지 않았습니다. 현재 코드로 대신 표시하지 않습니다." : "설치된 패키지에서 소스 코드를 읽을 수 없습니다."}</p>;
  return <div aria-label={historical ? "실행 당시 Python 코드" : "현재 Python 코드"}>
    <p className={styles.muted}>{historical ? "실행 당시 보존한 코드" : "현재 등록 시 보존한 코드"} · v{source.version} · {source.origin === "managed" ? "관리 UI에서 게시" : "설치된 모듈"}</p>
    {source.authoring_content && <div aria-label="이 분석의 작성 코드">
      <p>이 분석에 필요한 함수와 등록 설정만 표시합니다. 조회·검사·기록을 처리하는 공통 실행기는 작성할 필요가 없습니다.</p>
      <p className={styles.muted}>작성 코드는 공통 Python 형식으로 표시합니다. 실행 원문과 SHA-256은 아래 전체 소스에서 확인하세요.</p>
      <MethodCode content={source.authoring_content} />
    </div>}
    <details className={styles.file}><summary>전체 소스와 실행 근거 보기</summary>
    <p className={styles.muted}>진입 모듈과 일부 계산 보조 코드를 보존합니다. 외부 라이브러리 내부 전체와 실행 환경을 보존한 것은 아닙니다.</p>
    {source.files.map((file,index) => <details key={file.name} className={styles.file}>
      <summary>{index===0 ? "실행 진입 코드" : "계산 보조 코드"} · {file.name.startsWith("dl_method_assets.") ? "게시한 Python 모듈" : file.name}</summary>
      <MethodCode content={file.content} /><p className={styles.muted}>SHA-256 {file.sha256}</p>
    </details>)}</details>
  </div>;
}
