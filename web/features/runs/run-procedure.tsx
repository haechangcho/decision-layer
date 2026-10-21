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
  const t = useT();
  const ref = run.plan.recipe;
  if (!ref) return <><span className={styles.direct} title={t("Analysis that chose Methods without a registered Recipe")}><Compass size={13} aria-hidden="true" />{t(detailed ? "Exploratory analysis" : "Exploratory")}</span>{detailed && <RecipeReviews run={run} />}</>;
  const identity = ref.replace(/^recipe:\/\//, "");
  const separator = identity.lastIndexOf("@");
  const name = run.recipe_snapshot?.name ?? (separator < 0 ? identity : identity.slice(0, separator));
  const version = separator < 0 ? run.recipe_snapshot?.version : identity.slice(separator + 1);
  const label = t(run.preview ? "Recipe preview" : "Run with Recipe");
  if (!detailed) return <span className={styles.summary} aria-label={`${label}: ${name}${version ? `, ${t("version {version}", { version })}` : ""}`} title={`${name}${version ? ` (v${version})` : ""}`}><span className={styles.recipeBadge}><BookOpen size={12} aria-hidden="true" />{run.preview ? t("Preview") : "Recipe"}</span><span className={styles.name}>{name}</span></span>;
  return <><div className={styles.detail} aria-label={t("Analysis procedure used")}>
    <span className={styles.label}><BookOpen size={15} aria-hidden="true" />{label}</span>
    <Link href={`/recipes/${encodeURIComponent(name)}`}>{name}<ArrowUpRight size={14} aria-hidden="true" /></Link>
    {version && <span className={styles.version}>{t("Version at run time {version}", { version })}</span>}
  </div><RecipeReviews run={run} /></>;
}
