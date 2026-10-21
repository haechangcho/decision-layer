"use client";
import { useT } from "@/lib/i18n";

import { useState } from "react";
import { InspectorDialog } from "@/components/inspector-dialog";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { MethodSource } from "@/lib/api";
import styles from "./method-content.module.css";

export function MethodMarkdown({ content }: { content: string }) {
  const t = useT();
  return <div className={styles.document}><Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}
    components={{ img: ({ alt }) => <span>{alt}</span>, a: ({ children, href }) => <a href={href} rel="noreferrer noopener">{children}</a> }}>{content}</Markdown></div>;
}
export function MethodCode({ content, language="python" }: { content: string; language?: string }) {
  const t = useT();
  const longest = Math.max(3, ...(content.match(/`+/g) || []).map(part => part.length));
  const fence = "`".repeat(longest + 1);
  return <div className={`${styles.document} ${styles.code}`}><Markdown rehypePlugins={[rehypeHighlight]}>{`${fence}${language}\n${content}\n${fence}`}</Markdown></div>;
}
export function SourceEvidence({ source, historical=false }: { source?: MethodSource | null; historical?: boolean }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [filename, setFilename] = useState("");
  if (!source?.available || !source.files.length) return <p className={styles.muted}>{historical ? t("This Run has no execution-time source snapshot. Current source is not shown in its place.") : t("Cannot read source code from the installed package.")}</p>;
  const file = source.files.find(item => item.name === filename) ?? source.files[0];
  const original = <div className={styles.originalSource}>
    <label>{t("Source file")}<select aria-label={t("Source file")} value={file.name} onChange={event => setFilename(event.target.value)}>{source.files.map(item => <option key={item.name} value={item.name}>{item.name.startsWith("dl_method_assets.") ? t("Published Python module") : item.name}</option>)}</select></label>
    <MethodCode content={file.content} /><p className={styles.hash}>SHA-256 {file.sha256}</p>
  </div>;
  return <div aria-label={historical ? t("Execution-time Python code") : t("Current Python code")}>
    <div className={styles.sourceToolbar}><p className={styles.muted}>{historical ? t("Source saved at execution") : t("Source saved at registration")} / v{source.version}</p>
      {source.authoring_content && <button type="button" className="ghost" onClick={() => setOpen(true)}>{t("View original file")}</button>}</div>
    {source.authoring_content ? <div aria-label={t("Authorable analysis code")}><MethodCode content={source.authoring_content} /></div> : original}
    <InspectorDialog title={t("Original Python file")} open={open} onClose={() => setOpen(false)}><p>{t("Preserved entry module and helper code. External libraries are not included in full.")}</p>{original}</InspectorDialog>
  </div>;
}
