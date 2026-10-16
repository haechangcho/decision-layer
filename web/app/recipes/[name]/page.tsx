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
import { type Translate, useT } from "@/lib/i18n";
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

function titleFor(ref: string, objects: SemanticObject[], t: Translate) {
  return objects.find((object) => object.ref === ref)?.title ?? t("Name needs checking");
}

export default function RecipePage() {
  const t = useT();
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
  const metric = recipe ? titleFor(recipe.semantic_scope.primary_metric, objects, t) : "";

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
      setRunError(cause instanceof Error ? cause : new Error(t("Could not start the analysis.")));
      setBusy(false);
    }
  }

  if (error) return <div className={styles.page}><p className={styles.error} role="alert">{t("Could not load the Recipe.")} {error.message}</p><Link className={styles.back} href="/recipes"><ArrowLeft size={15} />{t("Recipe list")}</Link></div>;
  if (name === "new") return <RecipeEditor />;
  if (loading || !recipe) return <div className={styles.page}><LoadingState /></div>;

  return <div className={styles.page}>
    <Link className={styles.back} href="/recipes"><ArrowLeft size={15} />{t("Recipe list")}</Link>
    <div className={styles.heading}><div><p className={styles.eyebrow}>{t("Analysis procedure")} · v{recipe.version}</p><h1>{recipe.description || recipe.name}</h1></div><div className={styles.recipeActions}><Link className={styles.secondaryLink} href={`/recipes/${encodeURIComponent(recipe.name)}/edit`}>{t("Edit Recipe")} <ArrowRight size={15} /></Link><RecipeDelete recipe={recipe} onDeleted={() => router.push("/recipes")} /></div></div>
    {recipe.mode === "investigation" && <p className={styles.runNotice}>{t("This Recipe is an exploratory procedure that picks the next step from each result. In Claude or Codex, use it by naming the Recipe {name}. On the web, choose each step below.", { name: recipe.name })}</p>}
    <div className={styles.recipeRunGrid}>
      <section className={styles.recipeRunPanel}>
        <h2>{t("Analysis conditions")}</h2>
        <dl className={styles.meta}><div className={styles.metaRow}><dt>{t("Primary metric")}</dt><dd>{metric}</dd></div></dl>
        <RecipeRuntimeInputs specs={recipe.inputs ?? {}} values={inputs} onChange={setInputs} objects={objects} />
        {needsTime && timeDimensions.length === 0 && <p className={styles.error} role="alert">{t("No date dimension linked to this metric was found. Check the time dimensions in the semantic model or")} <Link href="/catalog">{t("choose another metric.")}</Link></p>}
        {!needsTime && policy?.allow_all && <label className="check"><input type="checkbox" checked={allDates} onChange={event => { setAllDates(event.target.checked); if (!event.target.checked && !dates[0]) chooseDates(recommendedPeriod ?? datePreset("month")); }} />{t("All periods")}</label>}
        {!useAllDates && timeDimensions.length > 0 && <label className={styles.runField}>{t("Date dimension")}
          <select aria-label={t("Date dimension")} value={selectedTime} onChange={(event) => setTimeDimension(event.target.value)}><option value="">{t("Choose a date dimension")}</option>{timeDimensions.map((object) => <option key={object.ref} value={object.ref}>{object.title}</option>)}</select>
        </label>}
        {needsTime && timeDimensions.length > 1 && recommendedTime === 0 && <p className="hint">{t("The connected metadata cannot identify the relevant date, so choose one.")}</p>}
        {!useAllDates && (timeDimensions.length > 0 || needsTime) && <><div className={styles.fieldHeading}><label htmlFor="run-start">{t("Analysis period")}</label><CalendarDays size={15} /></div>
        <div className={styles.datePresets} role="group" aria-label={t("Quick period choices")}>
          {recommendedPeriod && <button type="button" onClick={() => chooseDates(recommendedPeriod)}>{t("Suggested period")}</button>}
          <button type="button" onClick={() => chooseDates(datePreset("month", recommendedPeriod?.[1]))}>{t(recommendedPeriod ? "Latest month" : "This month")}</button>
          <button type="button" onClick={() => chooseDates(datePreset("quarter", recommendedPeriod?.[1]))}>{t("Last quarter")}</button>
          <button type="button" onClick={() => chooseDates(datePreset("year", recommendedPeriod?.[1]))}>{recommendedPeriod ? t("Year {year}", { year: recommendedPeriod[1].slice(0, 4) }) : t("This year")}</button>
        </div>
        <div className={styles.dateFields}><label className={styles.runField} htmlFor="run-start">{t("Start date")}<input id="run-start" type="date" value={dates[0]} onChange={(event) => chooseDates([event.target.value, dates[1]])} /></label><label className={styles.runField} htmlFor="run-end">{t("End date")}<input id="run-end" type="date" value={dates[1]} onChange={(event) => chooseDates([dates[0], event.target.value])} /></label></div></>}
        {!useAllDates && recommendedPeriod && <p className="hint">{t("Suggested analysis period: {period}", { period: recommendedPeriod.join(" ~ ") })}{timeDimensions.find(object => object.ref === selectedTime)?.metadata?.calendarType === "mapped" ? ` · ${t("mapped calendar")}` : ""}</p>}
        {dates[0] > dates[1] && <p className={styles.error} role="alert">{t("The end date must be after the start date. Choose the dates again.")}</p>}
        {needsTime && !selectedTime && timeDimensions.length > 0 && <p className="hint">{t("Choose a date dimension to start the analysis.")}</p>}
        <label className={styles.runField} htmlFor="run-question">{t("Analysis note")} <span>{t("optional")}</span><input id="run-question" value={question} onChange={(event) => setQuestion(event.target.value)} /></label>
        {recipe.semantic_scope.preferred_dimensions.length > 0 && <div className={styles.runContext}><strong>{t("Categories examined")}</strong><p>{recipe.semantic_scope.preferred_dimensions.map((ref) => titleFor(ref, objects, t)).join(" · ")}</p></div>}
        {runError && <div className={styles.error} role="alert"><strong>{t("Could not start the analysis.")}</strong> {runError.message}<br />
          {runError instanceof ApiError && (runError.status === 401 || runError.status === 403)
            ? <><Link href="/sources">{t("Check connection")}</Link> · <Link href="/catalog">{t("Check accessible metrics")}</Link></>
            : runError instanceof ApiError && runError.status === 422
              ? t("Check the analysis conditions and run again.")
              : t("Try again in a moment.")}
        </div>}
        <button className={styles.runPrimary} type="button" disabled={busy || (needsTime && timeDimensions.length === 0) || missingPeriod || dates[0] > dates[1]} onClick={run}><Play size={16} />{t(busy ? "Starting analysis…" : recipe.mode === "investigation" ? "Start exploring on the web" : "Analyze with this Recipe")}</button>
      </section>
      <aside className={styles.recipeRunAside}>
        <h2>{t("What this analysis checks")}</h2>
        <p>{recipe.routing.objective || (recipe.routing.use_for.length ? recipe.routing.use_for.join(" · ") :
          recipe.origin_runs?.length ? recipe.steps.map(step => methodName(step.method, t)).join(" → ") : recipe.description)}</p>
        {!!recipe.origin_runs?.length && <div className={styles.runContext}><strong>{t("Original question")}</strong><p>{recipe.source_question || recipe.description}</p></div>}
        <div className={styles.runContext}><strong>{t("Conditions for this run")}</strong><p>{t("Runs with the period chosen above. Comparison periods or conditions fixed in a step still apply.")}</p></div>
        {recipe.routing.do_not_use_for.length > 0 && <div className={styles.runContext}><strong>{t("Questions that need another procedure")}</strong><p>{recipe.routing.do_not_use_for.join(" · ")}</p></div>}
        <Link href="/runs">{t("View recent runs")} <ArrowRight size={14} /></Link>
      </aside>
    </div>
  </div>;
}
