"use client";
import { LoadingState } from "@/components/loading-indicator";

import Link from "next/link";
import { useParams } from "next/navigation";

import { RecipeEditor } from "@/features/recipes/recipe-editor";
import type { Recipe } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import styles from "../../../library.module.css";

export default function RecipeEditPage() {
  const t = useT();
  const { name } = useParams<{ name: string }>();
  const { data, error } = useApi<Recipe>(`/recipes/${encodeURIComponent(name)}/edit`);
  if (error) return <div className={styles.page}><p className={styles.error} role="alert">{t("Could not load the Recipe.")} {error.message}</p><Link href="/recipes">{t("Recipe list")}</Link></div>;
  if (!data) return <div className={styles.page}><LoadingState /></div>;
  return <RecipeEditor key={name} initial={data} />;
}
