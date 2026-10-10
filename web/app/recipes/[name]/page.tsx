"use client";
import { LoadingState } from "@/components/loading-indicator";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, CalendarDays, Play } from "lucide-react";

import { api, ApiError, type Recipe, type Run, type SemanticObject, type SourceReadiness } from "@/lib/api";
import { RecipeEditor } from "@/features/recipes/recipe-editor";
import { RecipeDelete } from "@/features/recipes/recipe-delete";
import { RecipeRuntimeInputs } from "@/features/recipes/recipe-runtime-inputs";
import { suggestedDateRange, suggestedTimeDimension } from "@/lib/semantic-dates";
import { useApi, useCatalog } from "@/lib/hooks";
import styles from "../../library.module.css";
import { methodName } from "@/lib/method-name";

function formatDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function datePreset(preset: "month" | "quarter" | "year", referenceDate?: string): [string, string] {
  const today = referenceDate ? new Date(`${referenceDate}T12:00:00`) : new Date();
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
  return objects.find((object) => object.ref === ref)?.title ?? "이름 확인 필요";
}

export default function RecipePage() {
  const { name } = useParams<{ name: string }>();
  const router = useRouter();
  const { data: recipe, error, loading } = useApi<Recipe>(name === "new" ? null : `/recipes/${encodeURIComponent(name)}`);
  const { data: readiness } = useApi<SourceReadiness>(name === "new" ? null : "/sources/current/readiness");
  const { data: policy } = useApi<{ allow_all: boolean }>("/execution-policy");
  const { objects } = useCatalog();
  const [dates, setDates] = useState<[string, string]>(() => datePreset("month"));
  const datesTouched = useRef(false);
  function chooseDates(value: [string, string]) { datesTouched.current = true; setDates(value); }
  const [timeDimension, setTimeDimension] = useState("");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [runError, setRunError] = useState<Error | null>(null);
  const [allDates, setAllDates] = useState(false);
  const [inputs, setInputs] = useState<Record<string, unknown>>({});
  useEffect(() => {
    if (recipe?.default_scope == null || datesTouched.current) return;
    setDates(recipe.default_scope.date_range ?? recipe.default_scope.period?.date_range ?? ["", ""]);
    setAllDates(recipe.default_scope.period?.mode === "all");
    setTimeDimension(recipe.default_scope.time_dimension ?? "");
  }, [recipe]);

  const timeDimensions = useMemo(() => {
    if (!recipe) return [];
    const prepared = readiness?.metrics.find((item) => item.metric.ref === recipe.semantic_scope.primary_metric)?.checks.time.dimensions;
    const metricEntity = objects.find((object) => object.ref === recipe.semantic_scope.primary_metric)?.entity;
    const all = objects.filter((object) => object.kind === "time_dimension");
    if (prepared?.length) return all.filter((object) => prepared.includes(object.ref));
    const sameEntity = all.filter((object) => !!metricEntity && object.entity === metricEntity);
    return sameEntity.length ? sameEntity : all;
  }, [objects, readiness, recipe]);
  const recommendedTime = readiness?.metrics.find((item) => item.metric.ref === recipe?.semantic_scope.primary_metric)?.checks.time.dimensions.length;
  const selectedTime = timeDimensions.some((object) => object.ref === timeDimension) ? timeDimension : (timeDimensions.length === 1 ? timeDimensions[0].ref : suggestedTimeDimension(objects, recipe?.semantic_scope.primary_metric ?? "")?.ref ?? "");
  const recommendedPeriod = suggestedDateRange(timeDimensions.find(object => object.ref === selectedTime));
  const recommendedPeriodKey = recommendedPeriod?.join("/");
  useEffect(() => {
    if (!recipe || recipe.default_scope != null || datesTouched.current || !recommendedPeriod) return;
    setDates(recommendedPeriod);
  }, [recipe, selectedTime, recommendedPeriodKey]);
  const needsTime = !!recipe && (recipe.mode === "pipeline"
    ? recipe.steps.some((step) => step.method === "query.trend" || step.params.vs_previous === true)
    : recipe.allowed_methods.includes("query.trend"));
  const useAllDates = allDates && !needsTime;
  const usePeriodRule = !datesTouched.current && recipe?.default_scope?.period?.mode === "relative";
  const missingPeriod = !usePeriodRule && !useAllDates && ((needsTime && (!dates[0] || !dates[1] || !selectedTime)) || (timeDimensions.length > 0 && !!dates[0] && !!dates[1] && !selectedTime));
  const metric = recipe ? titleFor(recipe.semantic_scope.primary_metric, objects) : "";

  async function run() {
    if (!recipe) return;
    setBusy(true);
    setRunError(null);
    try {
      const result = await api<Run | { run_id: string }>("/runs", { body: {
        recipe: `${recipe.name}@${recipe.version}`,
        question: question.trim() || null,
        scope: { ...(usePeriodRule ? { period: recipe.default_scope?.period } : useAllDates ? { period: { mode: "all" } } : selectedTime && dates[0] && dates[1] ? { date_range: dates } : { period: { mode: "unresolved" } }), time_dimension: selectedTime || null, inputs },
      } });
      const runId = "id" in result ? result.id : result.run_id;
      router.push(`/runs/${runId}`);
    } catch (cause) {
      setRunError(cause instanceof Error ? cause : new Error("분석을 시작하지 못했습니다."));
      setBusy(false);
    }
  }

  if (error) return <div className={styles.page}><p className={styles.error} role="alert">Recipe를 불러오지 못했습니다. {error.message}</p><Link className={styles.back} href="/recipes"><ArrowLeft size={15} />Recipe 목록</Link></div>;
  if (name === "new") return <RecipeEditor />;
  if (loading || !recipe) return <div className={styles.page}><LoadingState /></div>;

  return <div className={styles.page}>
    <Link className={styles.back} href="/recipes"><ArrowLeft size={15} />Recipe 목록</Link>
    <div className={styles.heading}><div><p className={styles.eyebrow}>분석 절차 · v{recipe.version}</p><h1>{recipe.description || recipe.name}</h1></div><div className={styles.recipeActions}><Link className={styles.secondaryLink} href={`/recipes/${encodeURIComponent(recipe.name)}/edit`}>Recipe 편집 <ArrowRight size={15} /></Link><RecipeDelete recipe={recipe} onDeleted={() => router.push("/recipes")} /></div></div>
    {recipe.mode === "investigation" && <p className={styles.runNotice}>이 Recipe는 결과를 보고 다음 단계를 정하는 탐색형 절차입니다. Claude·Codex에서는 Recipe 이름 <strong>{recipe.name}</strong>을 지정해 사용할 수 있습니다. 웹에서는 아래에서 직접 단계를 선택하며 진행합니다.</p>}
    <div className={styles.recipeRunGrid}>
      <section className={styles.recipeRunPanel}>
        <h2>분석 조건</h2>
        <dl className={styles.meta}><div className={styles.metaRow}><dt>중심 지표</dt><dd>{metric}</dd></div></dl>
        <RecipeRuntimeInputs specs={recipe.inputs ?? {}} values={inputs} onChange={setInputs} objects={objects} />
        {needsTime && timeDimensions.length === 0 && <p className={styles.error} role="alert">이 지표와 연결된 날짜 기준을 찾지 못했습니다. 시맨틱 모델의 시간 차원을 확인하거나 <Link href="/catalog">다른 지표를 선택하세요.</Link></p>}
        {!needsTime && policy?.allow_all && <label className="check"><input type="checkbox" checked={allDates} onChange={event => { setAllDates(event.target.checked); if (!event.target.checked && !dates[0]) chooseDates(recommendedPeriod ?? datePreset("month")); }} />전체 기간</label>}
        {!useAllDates && timeDimensions.length > 0 && <label className={styles.runField}>날짜 기준
          <select aria-label="날짜 기준" value={selectedTime} onChange={(event) => setTimeDimension(event.target.value)}><option value="">날짜 기준 선택</option>{timeDimensions.map((object) => <option key={object.ref} value={object.ref}>{object.title}</option>)}</select>
        </label>}
        {needsTime && timeDimensions.length > 1 && recommendedTime === 0 && <p className="hint">연결된 메타데이터만으로 관련 날짜를 확인할 수 없어 직접 선택해야 합니다.</p>}
        {!useAllDates && (timeDimensions.length > 0 || needsTime) && <><div className={styles.fieldHeading}><label htmlFor="run-start">분석 기간</label><CalendarDays size={15} /></div>
        <div className={styles.datePresets} role="group" aria-label="기간 빠른 선택">
          {recommendedPeriod && <button type="button" onClick={() => chooseDates(recommendedPeriod)}>추천 기간</button>}
          <button type="button" onClick={() => chooseDates(datePreset("month", recommendedPeriod?.[1]))}>{recommendedPeriod ? "최근 월" : "이번 달"}</button>
          <button type="button" onClick={() => chooseDates(datePreset("quarter", recommendedPeriod?.[1]))}>지난 분기</button>
          <button type="button" onClick={() => chooseDates(datePreset("year", recommendedPeriod?.[1]))}>{recommendedPeriod ? `${recommendedPeriod[1].slice(0, 4)}년` : "올해"}</button>
        </div>
        <div className={styles.dateFields}><label className={styles.runField} htmlFor="run-start">시작일<input id="run-start" type="date" value={dates[0]} onChange={(event) => chooseDates([event.target.value, dates[1]])} /></label><label className={styles.runField} htmlFor="run-end">종료일<input id="run-end" type="date" value={dates[1]} onChange={(event) => chooseDates([dates[0], event.target.value])} /></label></div></>}
        {!useAllDates && recommendedPeriod && <p className="hint">추천 분석 기간: {recommendedPeriod.join(" ~ ")}{timeDimensions.find(object => object.ref === selectedTime)?.metadata?.calendarType === "mapped" ? " · 변환된 달력" : ""}</p>}
        {dates[0] > dates[1] && <p className={styles.error} role="alert">종료일은 시작일보다 늦어야 합니다. 날짜를 다시 선택하세요.</p>}
        {needsTime && !selectedTime && timeDimensions.length > 0 && <p className="hint">분석을 시작하려면 날짜 기준을 선택하세요.</p>}
        <label className={styles.runField} htmlFor="run-question">분석 메모 <span>선택</span><input id="run-question" value={question} onChange={(event) => setQuestion(event.target.value)} /></label>
        {recipe.semantic_scope.preferred_dimensions.length > 0 && <div className={styles.runContext}><strong>살펴보는 분류</strong><p>{recipe.semantic_scope.preferred_dimensions.map((ref) => titleFor(ref, objects)).join(" · ")}</p></div>}
        {runError && <div className={styles.error} role="alert"><strong>분석을 시작하지 못했습니다.</strong> {runError.message}<br />
          {runError instanceof ApiError && (runError.status === 401 || runError.status === 403)
            ? <><Link href="/sources">연결 확인</Link> · <Link href="/catalog">접근 가능한 지표 확인</Link></>
            : runError instanceof ApiError && runError.status === 422
              ? "분석 조건을 확인하고 다시 실행하세요."
              : "잠시 후 다시 시도하세요."}
        </div>}
        <button className={styles.runPrimary} type="button" disabled={busy || (needsTime && timeDimensions.length === 0) || missingPeriod || dates[0] > dates[1]} onClick={run}><Play size={16} />{busy ? "분석을 시작하는 중…" : recipe.mode === "investigation" ? "웹에서 탐색 시작" : "이 Recipe로 분석"}</button>
      </section>
      <aside className={styles.recipeRunAside}>
        <h2>이 분석이 확인하는 내용</h2>
        <p>{recipe.routing.objective || (recipe.routing.use_for.length ? recipe.routing.use_for.join(" · ") :
          recipe.origin_runs?.length ? recipe.steps.map(step => methodName(step.method)).join(" → ") : recipe.description)}</p>
        {!!recipe.origin_runs?.length && <div className={styles.runContext}><strong>처음 분석한 질문</strong><p>{recipe.source_question || recipe.description}</p></div>}
        <div className={styles.runContext}><strong>이번 실행 조건</strong><p>위에서 선택한 기간으로 실행합니다. 단계에 고정된 비교 기간이나 조건이 있다면 그대로 적용됩니다.</p></div>
        {recipe.routing.do_not_use_for.length > 0 && <div className={styles.runContext}><strong>다른 절차가 필요한 질문</strong><p>{recipe.routing.do_not_use_for.join(" · ")}</p></div>}
        <Link href="/runs">최근 실행 기록 보기 <ArrowRight size={14} /></Link>
      </aside>
    </div>
  </div>;
}
