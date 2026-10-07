import Link from "next/link";
import { BookOpen, ArrowUpRight, Compass } from "lucide-react";
import type { Run } from "@/lib/api";
import styles from "./run-procedure.module.css";

export function RunProcedure({ run, detailed = false }: { run: Run; detailed?: boolean }) {
  const ref = run.plan.recipe;
  if (!ref) return <span className={styles.direct} title="등록된 Recipe를 사용하지 않고 Method를 선택한 분석"><Compass size={13} aria-hidden="true" />{detailed ? "탐색 분석" : "탐색"}</span>;
  const identity = ref.replace(/^recipe:\/\//, "");
  const separator = identity.lastIndexOf("@");
  const name = run.recipe_snapshot?.name ?? (separator < 0 ? identity : identity.slice(0, separator));
  const version = separator < 0 ? run.recipe_snapshot?.version : identity.slice(separator + 1);
  const label = run.preview ? "Recipe 미리보기" : "Recipe로 실행";
  if (!detailed) return <span className={styles.summary} aria-label={`${label}: ${name}${version ? `, 버전 ${version}` : ""}`} title={`${name}${version ? ` (v${version})` : ""}`}><span className={styles.recipeBadge}><BookOpen size={12} aria-hidden="true" />{run.preview ? "미리보기" : "Recipe"}</span><span className={styles.name}>{name}</span></span>;
  return <div className={styles.detail} aria-label="사용한 분석 절차">
    <span className={styles.label}><BookOpen size={15} aria-hidden="true" />{label}</span>
    <Link href={`/recipes/${encodeURIComponent(name)}`}>{name}<ArrowUpRight size={14} aria-hidden="true" /></Link>
    {version && <span className={styles.version}>실행 당시 버전 {version}</span>}
  </div>;
}
