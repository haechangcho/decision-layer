"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, CalendarDays, Play } from "lucide-react";

import { api, type Recipe, type Run, type SemanticObject } from "@/lib/api";
import { RecipeEditor } from "@/components/recipe-editor";
import { useApi, useCatalog } from "@/lib/hooks";
import styles from "../../library.module.css";

function formatDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function datePreset(preset: "month" | "quarter" | "year"): [string, string] {
  const today = new Date();
  let start = new Date(today.getFullYear(), today.getMonth(), 1);
  let end = today;
  if (preset === "quarter") {
    const quarterStart = Math.floor(today.getMonth() / 3) * 3;
    end = new Date(today.getFullYear(), quarterStart, 0);
    start = new Date(end.getFullYear(), end.getMonth() - 2, 1);
  } else if (preset === "year") start = new Date(today.getFullYear(), 0, 1);
  return [formatDate(start), formatDate(end)];
}

function titleFor(ref: string, objects: SemanticObject[]) {
  return objects.find((object) => object.ref === ref)?.title ?? ref;
}

export default function RecipePage() {
  const { name } = useParams<{ name: string }>();
  const router = useRouter();
  const { data: recipe, error, loading } = useApi<Recipe>(name === "new" ? null : `/recipes/${encodeURIComponent(name)}`);
  const { objects } = useCatalog();
  const [dates, setDates] = useState<[string, string]>(() => datePreset("month"));
  const [timeDimension, setTimeDimension] = useState("");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [runError, setRunError] = useState("");

  const timeDimensions = useMemo(() => objects.filter((object) => object.kind === "time_dimension"), [objects]);
  const selectedTime = timeDimension || timeDimensions[0]?.ref || "";
  const needsTime = !!recipe && (recipe.mode === "pipeline"
    ? recipe.steps.some((step) => step.method === "query.trend")
    : recipe.allowed_methods.includes("query.trend"));
  const missingPeriod = needsTime && (!dates[0] || !dates[1] || !selectedTime);
  const metric = recipe ? titleFor(recipe.semantic_scope.primary_metric, objects) : "";

  async function run() {
    if (!recipe) return;
    setBusy(true);
    setRunError("");
    try {
      const result = await api<Run | { run_id: string }>("/runs", { body: {
        recipe: `${recipe.name}@${recipe.version}`,
        question: question.trim() || null,
        scope: { date_range: dates[0] && dates[1] ? dates : null, time_dimension: selectedTime || null },
      } });
      const runId = "id" in result ? result.id : result.run_id;
      router.push(`/runs/${runId}`);
    } catch (cause) {
      setRunError(cause instanceof Error ? cause.message : "분석을 시작하지 못했습니다.");
      setBusy(false);
    }
  }

  if (error) return <div className={styles.page}><p className={styles.error} role="alert">Recipe를 불러오지 못했습니다. {error.message}</p><Link className={styles.back} href="/recipes"><ArrowLeft size={15} />Recipe 목록</Link></div>;
  if (name === "new") return <RecipeEditor />;
  if (loading || !recipe) return <div className={styles.page}><div className={styles.skeleton} role="status" aria-label="불러오는 중" /></div>;

  return <div className={styles.page}>
    <Link className={styles.back} href="/recipes"><ArrowLeft size={15} />Recipe 목록</Link>
    <div className={styles.heading}><div><p className={styles.eyebrow}>분석 절차 · v{recipe.version}</p><h1>{recipe.name}</h1><p className={styles.intro}>{recipe.description}</p></div><Link className={styles.secondaryLink} href={`/recipes/${encodeURIComponent(recipe.name)}/edit`}>Recipe 편집 <ArrowRight size={15} /></Link></div>
    <div className={styles.recipeRunGrid}>
      <section className={styles.recipeRunPanel}>
        <h2>분석 조건</h2>
        <dl className={styles.meta}><div className={styles.metaRow}><dt>중심 지표</dt><dd>{metric}</dd></div></dl>
        {needsTime && timeDimensions.length === 0 && <p className={styles.error} role="alert">이 Recipe에는 시간 분석이 있지만 Cube에서 시간 차원을 찾지 못했습니다. Sources 설정과 Cube 모델을 확인해 주세요.</p>}
        {timeDimensions.length > 0 && <label className={styles.runField}>날짜 기준
          <select aria-label="날짜 기준" value={selectedTime} onChange={(event) => setTimeDimension(event.target.value)}>{timeDimensions.map((object) => <option key={object.ref} value={object.ref}>{object.title}</option>)}</select>
        </label>}
        <div className={styles.fieldHeading}><label htmlFor="run-start">분석 기간</label><CalendarDays size={15} /></div>
        <div className={styles.datePresets} role="group" aria-label="기간 빠른 선택">
          <button type="button" onClick={() => setDates(datePreset("month"))}>이번 달</button>
          <button type="button" onClick={() => setDates(datePreset("quarter"))}>지난 분기</button>
          <button type="button" onClick={() => setDates(datePreset("year"))}>올해</button>
        </div>
        <div className={styles.dateFields}><label className={styles.runField} htmlFor="run-start">시작일<input id="run-start" type="date" value={dates[0]} onChange={(event) => setDates([event.target.value, dates[1]])} /></label><label className={styles.runField} htmlFor="run-end">종료일<input id="run-end" type="date" value={dates[1]} onChange={(event) => setDates([dates[0], event.target.value])} /></label></div>
        {needsTime && <p className="hint">시간 분석에는 분석 기간과 날짜 기준이 필요합니다.</p>}
        <label className={styles.runField} htmlFor="run-question">분석 메모 <span>선택</span><input id="run-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="예: 지난 분기 반품률이 오른 이유" /></label>
        {recipe.semantic_scope.preferred_dimensions.length > 0 && <div className={styles.runContext}><strong>살펴보는 분류</strong><p>{recipe.semantic_scope.preferred_dimensions.map((ref) => titleFor(ref, objects)).join(" · ")}</p></div>}
        {runError && <p className={styles.error} role="alert">{runError}<br />연결 상태와 분석 권한을 확인한 뒤 다시 시도하세요.</p>}
        <button className={styles.runPrimary} type="button" disabled={busy || (needsTime && timeDimensions.length === 0) || missingPeriod || dates[0] > dates[1]} onClick={run}><Play size={16} />{busy ? "분석을 시작하는 중…" : "이 Recipe로 분석"}</button>
      </section>
      <aside className={styles.recipeRunAside}>
        <h2>이 분석이 확인하는 내용</h2>
        <p>{recipe.routing.use_for.length ? recipe.routing.use_for.join(" · ") : recipe.description}</p>
        {recipe.routing.do_not_use_for.length > 0 && <div className={styles.runContext}><strong>다른 절차가 필요한 질문</strong><p>{recipe.routing.do_not_use_for.join(" · ")}</p></div>}
        <Link href="/runs">최근 실행 기록 보기 <ArrowRight size={14} /></Link>
      </aside>
    </div>
  </div>;
}
