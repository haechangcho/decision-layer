"use client";
import { useT } from "@/lib/i18n";

import { useMemo } from "react";
import CodeMirror, { EditorView } from "@uiw/react-codemirror";
import { python } from "@codemirror/lang-python";
import { markdown } from "@codemirror/lang-markdown";
import { indentUnit } from "@codemirror/language";
import { yamlFrontmatter } from "@codemirror/lang-yaml";

export function SourceEditor({ value, language, onChange, onSave, onFormat, readOnly=false }: {
  value: string; language: "python" | "markdown"; onChange: (value: string) => void; onSave: () => void; onFormat?:() => void; readOnly?:boolean;
}) {
  const t = useT();
  const label = language === "markdown" ? t("Original Skill Markdown") : t("Authorable Python code");
  const extensions = useMemo(() => [language === "python" ? python() : yamlFrontmatter({content:markdown()}),
    indentUnit.of("    "),
    EditorView.contentAttributes.of({ "aria-label": label, "aria-describedby": "source-editor-help" }),
    ...(language === "markdown" ? [EditorView.lineWrapping] : []),
  ], [language, label]);
  return <div onKeyDownCapture={event => {
    if (onFormat && !readOnly && event.shiftKey && event.altKey && event.key.toLowerCase() === "f") {
      event.preventDefault();event.stopPropagation();onFormat();
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault(); event.stopPropagation(); onSave();
    }
  }}>
    <CodeMirror value={value} onChange={onChange} extensions={extensions} theme="light"
      minHeight="420px" maxHeight="65vh" autoFocus indentWithTab={false} readOnly={readOnly}
      basicSetup={{ lineNumbers:true, foldGutter:true, highlightActiveLine:true, searchKeymap:true, tabSize:4 }} />
  </div>;
}
