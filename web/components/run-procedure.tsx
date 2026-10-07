import Link from "next/link";
import { BookOpen, ArrowUpRight } from "lucide-react";
import type { Run } from "@/lib/api";
import styles from "./run-procedure.module.css";

export function RunProcedure({ run, detailed = false }: { run: Run; detailed?: boolean }) {
  const ref = run.plan.recipe;
  if (!ref) return <span className={styles.direct}>Recipe 없이 분석</span>;
  const identity = ref.replace(/^recipe:\/\//, "");
  const separator = identity.lastIndexOf("@");
  const name = run.recipe_snapshot?.name ?? (separator < 0 ? identity : identity.slice(0, separator));
  const version = separator < 0 ? run.recipe_snapshot?.version : identity.slice(separator + 1);
  const label = run.preview ? "Recipe 미리보기" : "Recipe로 실행";
  if (!detailed) return <span className={styles.summary}><BookOpen size={13} aria-hidden="true" />{label}: {name}{version && <span>v{version}</span>}</span>;
  return <div className={styles.detail} aria-label="사용한 분석 절차">
    <span className={styles.label}><BookOpen size={15} aria-hidden="true" />{label}</span>
    <Link href={`/recipes/${encodeURIComponent(name)}`}>{name}<ArrowUpRight size={14} aria-hidden="true" /></Link>
    {version && <span className={styles.version}>실행 당시 버전 {version}</span>}
  </div>;
}
