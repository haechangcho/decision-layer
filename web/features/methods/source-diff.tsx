"use client";

import { useMemo } from "react";
import { structuredPatch } from "diff";
import styles from "./method-content.module.css";

export function SourceDiff({ before, after, baseVersion, version }: {
  before: string; after: string; baseVersion: string; version: string;
}) {
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
  return <section className={styles.diffPanel} aria-label="코드 변경 비교">
    <h3>게시 v{baseVersion}</h3>
    <p className={styles.muted}>→ 작성 중 v{version} · <span className={styles.diffAdded}>+{added}줄 추가</span> · <span className={styles.diffRemoved}>−{removed}줄 삭제</span></p>
    {!patch ? <p className={styles.notice}>변경 범위가 커서 줄 비교를 생략했습니다. 미리보기에서 전체 코드를 확인하세요.</p>
      : !lines.length ? <p className={styles.notice}>코드 변경이 없습니다.{baseVersion !== version && " 버전만 변경했습니다."}</p>
      : <div className={styles.diffScroll} tabIndex={0} role="region" aria-label="변경된 코드 줄">
        <table className={styles.diffTable} aria-label="추가·삭제 코드"><thead><tr><th>이전</th><th>변경</th><th>코드</th></tr></thead>
          <tbody>{lines.map((line, index) => <tr key={index} className={line.type === "hunk" ? styles.diffHunk : line.type === "add" ? styles.diffAdd : line.type === "remove" ? styles.diffRemove : undefined}>
            <td>{line.old}</td><td>{line.next}</td><td><code>{line.text}</code></td>
          </tr>)}</tbody>
        </table>
      </div>}
  </section>;
}
