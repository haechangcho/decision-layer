"use client";
import { useT } from "@/lib/i18n";

import { useMemo } from "react";
import { structuredPatch } from "diff";
import styles from "./method-content.module.css";

export function SourceDiff({ before, after, baseVersion, version }: {
  before: string; after: string; baseVersion: string; version: string;
}) {
  const t = useT();
  const patch = useMemo(() => structuredPatch("published", "draft", before, after,
    undefined, undefined, { context: 3, timeout: 200, maxEditLength: 4000 }), [before, after]);
  const lines = patch?.hunks.flatMap(hunk => {
    let oldLine = hunk.oldStart, newLine = hunk.newStart;
    return [{ type: "hunk", text: `@@ ${hunk.oldStart},${hunk.oldLines} → ${hunk.newStart},${hunk.newLines} @@`, old: "", next: "" },
      ...hunk.lines.map(text => {
        const marker = text[0];
        return { type: marker === "+" ? "add" : marker === "-" ? "remove" : "context", text,
          old: marker === "+" || marker === "\\" ? "" : String(oldLine++),
          next: marker === "-" || marker === "\\" ? "" : String(newLine++) };
      })];
  }) || [];
  const added = lines.filter(line => line.type === "add").length;
  const removed = lines.filter(line => line.type === "remove").length;
  return <section className={styles.diffPanel} aria-label={t("Code comparison")}>
    <h3>{t("Published v{version}", { version: baseVersion })}</h3>
    <p className={styles.muted}>{t("→ Editing v{version}", { version })} · <span className={styles.diffAdded}>{t("+{count} lines added", { count: added })}</span> · <span className={styles.diffRemoved}>{t("−{count} lines removed", { count: removed })}</span></p>
    {!patch ? <p className={styles.notice}>{t("Too many changes for a line diff. Review the preview.")}</p>
      : !lines.length ? <p className={styles.notice}>{t("No code changes.")}{baseVersion !== version && t("Only the version changed.")}</p>
      : <div className={styles.diffScroll} tabIndex={0} role="region" aria-label={t("Changed code lines")}>
        <table className={styles.diffTable} aria-label={t("Added and removed code")}><thead><tr><th>{t("Before")}</th><th>{t("Change")}</th><th>{t("Code")}</th></tr></thead>
          <tbody>{lines.map((line, index) => <tr key={index} className={line.type === "hunk" ? styles.diffHunk : line.type === "add" ? styles.diffAdd : line.type === "remove" ? styles.diffRemove : undefined}>
            <td>{line.old}</td><td>{line.next}</td><td><code>{line.text}</code></td>
          </tr>)}</tbody>
        </table>
      </div>}
  </section>;
}
