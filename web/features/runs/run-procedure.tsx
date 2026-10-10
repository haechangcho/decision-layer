import Link from "next/link";
import { BookOpen, ArrowUpRight, Compass } from "lucide-react";
import type { Run } from "@/lib/api";
import styles from "./run-procedure.module.css";
import { useT } from "@/lib/i18n";

function RecipeReviews({ run }: { run: Run }) {
  const t = useT();
  if (!run.recipe_review?.length) return null;
  return <section className={styles.reviews} aria-label={t("Recipe choice")}><h3>{t("Recipe choice")}</h3>
    <ul>{run.recipe_review.map((item, index) => {
      const name = run.recipe_candidates?.find(candidate => candidate.recipe === item.recipe)?.name || item.recipe.replace(/^recipe:\/\//, "").split("@")[0];
      const alreadyShown = item.decision === "selected" && item.recipe === run.plan.recipe;
      return <li key={`${item.recipe}:${index}`}>{!alreadyShown && <div><Link href={`/recipes/${encodeURIComponent(name)}`}>{name}</Link><span>{t(item.decision === "selected" ? "Used this Recipe" : "Did not use this Recipe")}</span></div>}<p>{item.reason}</p></li>;
    })}</ul>
  </section>;
}

export function RunProcedure({ run, detailed = false }: { run: Run; detailed?: boolean }) {
  const ref = run.plan.recipe;
  if (!ref) return <><span className={styles.direct} title="등록된 Recipe를 사용하지 않고 Method를 선택한 분석"><Compass size={13} aria-hidden="true" />{detailed ? "탐색 분석" : "탐색"}</span>{detailed && <RecipeReviews run={run} />}</>;
  const identity = ref.replace(/^recipe:\/\//, "");
  const separator = identity.lastIndexOf("@");
  const name = run.recipe_snapshot?.name ?? (separator < 0 ? identity : identity.slice(0, separator));
  const version = separator < 0 ? run.recipe_snapshot?.version : identity.slice(separator + 1);
  const label = run.preview ? "Recipe 미리보기" : "Recipe로 실행";
  if (!detailed) return <span className={styles.summary} aria-label={`${label}: ${name}${version ? `, 버전 ${version}` : ""}`} title={`${name}${version ? ` (v${version})` : ""}`}><span className={styles.recipeBadge}><BookOpen size={12} aria-hidden="true" />{run.preview ? "미리보기" : "Recipe"}</span><span className={styles.name}>{name}</span></span>;
  return <><div className={styles.detail} aria-label="사용한 분석 절차">
    <span className={styles.label}><BookOpen size={15} aria-hidden="true" />{label}</span>
    <Link href={`/recipes/${encodeURIComponent(name)}`}>{name}<ArrowUpRight size={14} aria-hidden="true" /></Link>
    {version && <span className={styles.version}>실행 당시 버전 {version}</span>}
  </div><RecipeReviews run={run} /></>;
}
