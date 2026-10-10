"use client";
import { LoadingState } from "@/components/loading-indicator";

import Link from "next/link";
import { useParams } from "next/navigation";

import { RecipeEditor } from "@/features/recipes/recipe-editor";
import type { Recipe } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import styles from "../../../library.module.css";

export default function RecipeEditPage() {
  const { name } = useParams<{ name: string }>();
  const { data, error } = useApi<Recipe>(`/recipes/${encodeURIComponent(name)}/edit`);
  if (error) return <div className={styles.page}><p className={styles.error} role="alert">Recipe를 불러오지 못했습니다. {error.message}</p><Link href="/recipes">Recipe 목록</Link></div>;
  if (!data) return <div className={styles.page}><LoadingState /></div>;
  return <RecipeEditor key={name} initial={data} />;
}
