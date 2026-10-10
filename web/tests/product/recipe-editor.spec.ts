import { test, expect, type Page } from "@playwright/test";
import type { Recipe } from "../../lib/api";

const metric = "cube://local/fact_payment/total_payment_amt";
const alternateMetric = "cube://local/fact_payment/claim_count";
const dimension = "cube://local/fact_payment/payment_type";
const methods = [
  { name: "query.trend", version: "1.0.0", requires_period: true, description: "시간에 따른 변화", roles: { metric: { kind: "measure", required: true }, related: { kind: "measure", required: false, multiple: true } }, parameters: { granularity: { type: "enum", enum: ["day", "month"], default: "month", ui_group: "basic" }, vs_previous: { type: "boolean", default: false, ui_group: "options" } } },
  { name: "query.drilldown", version: "2.0.0", description: "항목별 분석", roles: { metric: { kind: "measure", required: true }, dimensions: { kind: "dimension", required: true, multiple: true } }, parameters: { top_n: { type: "integer", default: 10, ui_group: "advanced" }, min_count: { type: "integer", default: 30, ui_group: "advanced" }, rank_by: { type: "enum", enum: ["value", "count"], default: "value", ui_group: "advanced" } } },
];
const existing = (): Recipe => ({
  name: "insurance-review", version: "1.0.0", description: "보험금 지급액 분석",
  mode: "pipeline", routing: { use_for: ["지급액 변화"], do_not_use_for: ["인과 추론"] },
  semantic_scope: { primary_metric: metric, preferred_dimensions: [dimension], related_metrics: [], required_filters: [] },
  steps: [{ id: "by_type", method: "query.drilldown", bindings: { metric: "$scope.primary_metric", dimensions: "$scope.preferred_dimensions" }, params: { top_n: 7, min_count: 47, rank_by: "count", drill_path: [] } }],
  allowed_methods: [], validators: [{ name: "complete_period" }], limits: { max_steps: 8, max_queries: 15 }, instructions: "Keep the reporting scope.",
});

async function mockApi(page: Page, initial?: Recipe) {
  let saved = initial;
  let submitted: { recipe: Recipe; base_version: string | null } | undefined;
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [
    { ref: metric, kind: "measure", title: "지급액", public: true },
    { ref: alternateMetric, kind: "measure", title: "청구 건수", public: true },
    { ref: dimension, kind: "dimension", title: "지급 유형", public: true },
    { ref: "cube://local/fact_accident/payment_dt", kind: "time_dimension", title: "지급일", public: true },
    { ref: "cube://local/fact_accident/claim_dt", kind: "time_dimension", title: "청구일", public: true },
  ] } }));
  await page.route("**/api/methods", route => route.fulfill({ json: methods }));
  await page.route("**/api/recipes:format", route => route.fulfill({ json: { yaml: JSON.stringify(route.request().postDataJSON()) } }));
  await page.route("**/api/recipes:parse", route => route.fulfill({ json: JSON.parse(route.request().postDataJSON().yaml) }));
  await page.route("**/api/recipes:configure-step", route => {
    const body = route.request().postDataJSON();
    const next = body.recipe;
    next.steps[body.step_index].bindings.metric = "$scope.primary_metric";
    return route.fulfill({ json: next });
  });
  await page.route("**/api/sources/current/readiness", route => route.fulfill({ json: { metrics: [{ metric: { ref: metric }, checks: { time: { dimensions: ["cube://local/fact_accident/payment_dt"] } } }] } }));
  await page.route("**/api/recipes:validate?live=true", route => route.fulfill({ json: { valid: true, semantic_checked: true } }));
  await page.route("**/api/recipes/insurance-review/edit", route => route.fulfill({ json: saved }));
  await page.route("**/api/recipes/insurance-review/publish", route => {
    saved = { ...saved!, status: "published", version: "1.0.1" };
    return route.fulfill({ json: saved });
  });
  await page.route("**/api/recipes/insurance-review", async route => {
    if (route.request().method() === "PUT") {
      submitted = route.request().postDataJSON();
      expect(route.request().headers()["x-recipe-admin-key"]).toBeUndefined();
      saved = submitted!.recipe;
    }
    await route.fulfill({ json: saved });
  });
  return { submission: () => submitted };
}

async function save(page: Page) {
  await page.getByRole("button", { name: "초안 저장", exact: true }).click();
  await expect(page.getByLabel("Recipe 편집 키")).toHaveCount(0);
  await page.getByRole("button", { name: "초안 버전 저장" }).click();
}

async function codeEdit(page: Page, update: (recipe: Recipe) => void) {
  if (await page.getByRole("button", { name: "코드 보기", exact: true }).count()) await page.getByRole("button", { name: "코드 보기", exact: true }).click();
  await expect(page.getByLabel("Recipe YAML")).toContainText('"steps"');
  const recipe = JSON.parse(await page.getByLabel("Recipe YAML").inputValue()) as Recipe;
  update(recipe);
  await page.getByLabel("Recipe YAML").fill(JSON.stringify(recipe));
  await page.getByRole("button", { name: "YAML 적용", exact: true }).click();
  await page.getByRole("button", { name: "코드 닫기", exact: true }).click();
}

test("comparison groups use generic typed controls and reset on criterion changes", async ({ page }, info) => {
  const initial = existing();
  const flag = "cube://local/fact_payment/flag";
  const score = "cube://local/fact_payment/score";
  initial.steps = [{ id: "match", method: "example.match", bindings: { metric: "$scope.primary_metric", assignment: flag, covariates: [dimension] }, params: { retention: 0.73 } }];
  const state = await mockApi(page, initial);
  await page.route("**/api/methods", route => route.fulfill({ json: [{ name: "example.match", version: "1.0.0", roles: {
    metric: { kind: "measure", required: true },
    assignment: { kind: "dimension", required: false, label: "그룹을 나누는 기준", exclusive_group: "split" },
    score: { kind: "measure", required: false, label: "그룹을 나누는 기준", exclusive_group: "split" },
    covariates: { kind: "dimension", required: true, multiple: true, label: "맞출 조건" },
  }, parameters: {
    exposed: { type: "group", label: "대상 그룹", ui_group: "basic", semantic_role: "assignment", meaning: "comparison_subject" },
    controls: { type: "group", label: "비교 그룹", ui_group: "basic", semantic_role: "assignment", meaning: "comparison_population" },
    retention: { type: "number", default: 0.5, ui_group: "hidden" },
  } }] }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [
    { ref: metric, kind: "measure", title: "평균 지급액", data_type: "number" },
    { ref: flag, kind: "dimension", title: "대상 여부", data_type: "boolean" },
    { ref: dimension, kind: "dimension", title: "지급 유형", data_type: "string" },
    { ref: score, kind: "measure", title: "이전 구매금액", data_type: "number" },
  ] } }));
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await expect(page.getByLabel("대상 그룹", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("비교 그룹", { exact: true })).toContainText("아니요 · 반대 그룹");
  const targetBox = await page.getByLabel("대상 그룹", { exact: true }).boundingBox();
  const comparisonBox = await page.getByLabel("비교 그룹", { exact: true }).boundingBox();
  expect(targetBox && comparisonBox && comparisonBox.x > targetBox.x && Math.abs(comparisonBox.y - targetBox.y) < 2).toBe(true);
  await page.getByLabel("대상 그룹", { exact: true }).selectOption("false");
  await expect(page.getByLabel("비교 그룹", { exact: true })).toContainText("예 · 반대 그룹");
  await page.getByLabel("비교 그룹", { exact: true }).selectOption("true");
  await page.screenshot({ path: info.outputPath("boolean-groups.png"), fullPage: true });
  await page.getByLabel("그룹을 나누는 기준", { exact: true }).selectOption(dimension);
  await expect(page.getByLabel("대상 그룹 정의")).toHaveValue("values");
  await expect(page.getByLabel("대상 그룹 값", { exact: true })).toHaveValue("");
  await page.getByLabel("대상 그룹 정의").selectOption("values");
  await page.getByLabel("대상 그룹 값", { exact: true }).fill("A");
  await page.getByRole("button", { name: "대상 그룹 값 추가", exact: true }).click();
  await page.getByLabel("비교 그룹 정의").selectOption("exclude");
  await page.getByLabel("비교 그룹 값", { exact: true }).fill("A");
  await page.getByRole("button", { name: "비교 그룹 값 추가", exact: true }).click();
  await page.getByLabel("그룹을 나누는 기준", { exact: true }).selectOption(score);
  await expect(page.getByLabel("대상 그룹 정의")).toHaveValue("auto");
  await page.getByLabel("대상 그룹 정의").selectOption("range");
  await page.getByLabel("대상 그룹 이상", { exact: true }).fill("100");
  await expect(page.getByLabel("비교 그룹 정의")).toContainText("100 미만 · 반대 범위");
  await page.getByLabel("비교 그룹 정의").selectOption("range");
  await page.getByLabel("비교 그룹 미만", { exact: true }).fill("100");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.steps[0].bindings).toEqual({ metric: "$scope.primary_metric", score, covariates: [dimension] });
  await expect.poll(() => state.submission()?.recipe.steps[0].params).toEqual({ retention: 0.73, exposed: { gte: 100 }, controls: { lt: 100 } });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

for (const automatic of [true, false]) test(`average count connection is ${automatic ? "automatic" : "requested only when ambiguous"}`, async ({ page }) => {
  const initial = existing();
  const count = "cube://local/fact_payment/rows";
  const entity = "cube://local/fact_payment/id";
  initial.steps = [{ id: "average", method: "example.average", bindings: { metric: "$scope.primary_metric" }, params: {} }];
  const state = await mockApi(page, initial);
  await page.route("**/api/methods", route => route.fulfill({ json: [{ name: "example.average", version: "1.0.0", roles: {
    metric: { kind: "measure", required: true },
    sample: { kind: "measure", required: false, label: "표본 건수 지표", default_binding: "unit_count", metric_kinds: ["count"], ui_group: "options" },
  }, parameters: {} }] }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [
    { ref: metric, kind: "measure", title: "평균 판매금액", data_type: "number", metric_kind: "average", entity },
    { ref: count, kind: "measure", title: "관측 건수", data_type: "number", metric_kind: "count", count_measure: count, entity },
  ] } }));
  await page.route("**/api/recipes:configure-step", route => {
    const recipe = route.request().postDataJSON().recipe;
    if (automatic) recipe.steps[0].bindings.sample = count;
    return route.fulfill({ json: recipe });
  });
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await expect(page.getByLabel("표본 건수 지표", { exact: true })).toHaveCount(0);
  if (!automatic) {
    await expect(page.getByText(/자동으로 확인할 수 없어 연결이 필요합니다/)).toBeVisible();
    await page.getByLabel("분석 단위의 건수 확인").selectOption(count);
  }
  await expect(page.getByLabel("분석 단위의 건수 확인")).toHaveCount(0);
  await save(page);
  await expect.poll(() => state.submission()?.recipe.steps[0].bindings.sample).toBe(count);
});

test("write a two-step Recipe with purpose, metric and dimensions only", async ({ page }, info) => {
  const state = await mockApi(page);
  await page.goto("/recipes/new");
  await expect(page.getByRole("group", { name: "Recipe 실행 방식" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "목적과 지표" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "초안 저장", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "지표 선택", exact: true }).click();
  await expect(page.getByLabel("분석할 지표", { exact: true })).toBeFocused();
  await page.getByLabel("어떤 질문에 사용하는 분석인가요?").fill("보험금 지급액 변화를 확인하고 지급 유형별로 분석");
  await page.getByLabel("분석할 지표", { exact: true }).selectOption(metric);
  await page.getByRole("button", { name: "코드 보기", exact: true }).click();
  await page.getByLabel("Recipe ID").fill("insurance-review");
  await page.getByRole("button", { name: "코드 닫기", exact: true }).click();
  await page.getByRole("button", { name: "첫 분석 추가" }).click();
  await page.getByRole("button", { name: /시간에 따른 변화/ }).click();
  await expect(page.getByRole("button", { name: "지표 변경", exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "분석 지표" })).toHaveCount(0);
  await expect(page.getByLabel("함께 볼 지표")).not.toBeVisible();
  await expect(page.getByLabel("직전 같은 길이와 비교")).toHaveCount(0);
  await expect(page.getByText("월별 추이", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "분석 단계 추가" }).click();
  await page.getByRole("button", { name: /항목별로 나눠 보기/ }).click();
  await page.getByLabel("나눠 볼 순서", { exact: true }).selectOption(dimension);
  await expect(page.getByLabel("표시할 그룹 수")).not.toBeVisible();
  await expect(page.getByLabel("최소 그룹 건수")).not.toBeVisible();
  await expect(page.getByLabel("정렬 기준")).not.toBeVisible();
  await expect.poll(async () => page.locator('[aria-label="Recipe 그래프"]').evaluate(canvas => {
    const frame = canvas.getBoundingClientRect();
    return [...canvas.querySelectorAll('.react-flow__node')].every(node => {
      const bounds = node.getBoundingClientRect();
      return bounds.top >= frame.top && bounds.bottom <= frame.bottom;
    });
  })).toBe(true);
  await page.screenshot({ path: info.outputPath("recipe-simple.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await save(page);
  await expect.poll(() => state.submission()?.recipe.steps.length).toBe(2);
  const recipe = state.submission()!.recipe;
  expect(recipe.steps[0].params).toEqual({});
  expect(recipe.steps[0].bindings.metric).toBe("$scope.primary_metric");
  expect(recipe.steps[1].bindings.dimensions).toEqual([dimension]);
  expect(recipe.steps[1].params).toEqual({});
  await expect(page.getByText("v1.0.0 · 초안")).toBeVisible();
  await page.getByRole("button", { name: "발행 검토" }).click();
  await page.getByRole("button", { name: "검증하고 발행" }).click();
  await expect(page).toHaveURL(/\/recipes\/insurance-review$/);
  await page.goto("/recipes/insurance-review/edit");
  await page.getByRole("button", { name: "분석 실행", exact: true }).click();
  await expect(page).toHaveURL(/\/recipes\/insurance-review$/);
  await expect(page.getByLabel("날짜 기준")).toHaveValue("cube://local/fact_accident/payment_dt");
  await expect(page.getByLabel("날짜 기준").locator("option")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "이 Recipe로 분석" })).toBeEnabled();
});

test("step metric override is deliberate and can return to the Recipe metric", async ({ page }) => {
  const state = await mockApi(page, existing());
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await expect(page.getByRole("button", { name: "지표 변경", exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "분석 지표" })).toHaveCount(0);
  await page.getByRole("button", { name: "지표 변경", exact: true }).click();
  await page.locator('[class*="refField"]').filter({ hasText: "이 단계에서 사용할 지표" }).getByRole("button", { name: "직접 선택" }).click();
  await page.getByRole("combobox", { name: "이 단계에서 사용할 지표" }).selectOption(alternateMetric);
  await expect(page.locator('[class*="inherited"]').getByText("청구 건수", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Recipe 지표 사용" }).click();
  await expect(page.locator('[class*="inherited"]').getByText("지급액", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "초안 저장", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "지표 변경", exact: true }).click();
  await page.locator('[class*="refField"]').filter({ hasText: "이 단계에서 사용할 지표" }).getByRole("button", { name: "직접 선택" }).click();
  await page.getByRole("combobox", { name: "이 단계에서 사용할 지표" }).selectOption(alternateMetric);
  await save(page);
  await expect.poll(() => state.submission()?.recipe.steps[0].bindings.metric).toBe(alternateMetric);
});

test("Recipe-fixed parameters stay preserved outside basic editing", async ({ page }) => {
  const locked: Recipe = { ...existing(), method_parameters: { "query.drilldown": { fixed: { top_n: 7 }, runtime_allowed: ["drill_path"] } } };
  const state = await mockApi(page, locked);
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await expect(page.getByText(/이 절차에 지정된 실행 제약/)).toBeVisible();
  await expect(page.getByLabel("표시할 그룹 수")).toHaveCount(0);
  await page.getByRole("button", { name: "분석 절차 정보" }).click();
  await page.getByLabel("어떤 질문에 사용하는 분석인가요?").fill("보험금 지급액 분석 절차");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.method_parameters?.["query.drilldown"].fixed.top_n).toBe(7);
});

test("technical configuration is separate from general Recipe information", async ({ page }) => {
  await mockApi(page, existing());
  await page.goto("/recipes/insurance-review/edit");
  await expect(page.getByText("실행 정책", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("입력 ID")).toHaveCount(0);
  await expect(page.getByLabel("최대 쿼리")).toHaveCount(0);
  await expect(page.getByLabel("Recipe YAML")).toHaveCount(0);
  await page.getByRole("button", { name: "코드 보기", exact: true }).click();
  await expect(page.getByLabel("Recipe YAML")).toBeVisible();
});

test("YAML edits update the graph and graph edits refresh YAML", async ({ page }) => {
  await mockApi(page, existing());
  await page.route("**/api/recipes:format", route => {
    const recipe = route.request().postDataJSON() as Recipe;
    return route.fulfill({ json: { yaml: `name: ${recipe.name}\ndescription: ${recipe.description}\n` } });
  });
  await page.route("**/api/recipes:parse", route => {
    const yaml = (route.request().postDataJSON() as { yaml: string }).yaml;
    return route.fulfill({ json: { ...existing(), description: yaml.includes("새 분석 절차") ? "새 분석 절차" : "보험금 지급액 분석" } });
  });
  await page.goto("/recipes/insurance-review/edit");
  await page.getByRole("button", { name: "코드 보기", exact: true }).click();
  await expect(page.getByLabel("Recipe YAML")).toContainText("description: 보험금 지급액 분석");
  await page.getByLabel("Recipe YAML").fill("name: insurance-review\ndescription: 새 분석 절차\n");
  await page.getByRole("button", { name: "YAML 적용" }).click();
  await expect(page.getByLabel("어떤 질문에 사용하는 분석인가요?")).toHaveValue("새 분석 절차");
  await expect(page.locator('.react-flow__node[data-id="scope"]')).toContainText("새 분석 절차");
  await page.getByLabel("어떤 질문에 사용하는 분석인가요?").fill("그래프에서 수정");
  await expect(page.getByLabel("Recipe YAML")).toContainText("description: 그래프에서 수정");
  await page.getByLabel("Recipe YAML").fill("name: insurance-review\ndescription: 덮어쓰기 시도\n");
  await page.getByLabel("어떤 질문에 사용하는 분석인가요?").fill("더 최근 그래프 변경");
  await page.getByRole("button", { name: "YAML 적용" }).click();
  await expect(page.getByText("그래프가 변경되었습니다. YAML을 새로고침한 뒤 다시 편집해 주세요.")).toBeVisible();
  await expect(page.getByLabel("어떤 질문에 사용하는 분석인가요?")).toHaveValue("더 최근 그래프 변경");
});

test("a hidden-setting save error opens code for repair", async ({ page }, info) => {
  await mockApi(page, existing());
  await page.route("**/api/recipes:validate?live=true", route => route.fulfill({ status: 422, json: {
    error: { code: "INVALID_RECIPE_EDIT", message: "top_n must be at least 1.", details: { field: "steps[0].params.top_n" } },
  } }));
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await codeEdit(page, recipe => { recipe.steps[0].params.top_n = 0; });
  await save(page);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByLabel("Recipe YAML")).toBeVisible();
  await expect(page.getByLabel("표시할 그룹 수")).toHaveCount(0);
  await expect(page.getByText("top_n must be at least 1.").last()).toBeVisible();
  await page.screenshot({ path: info.outputPath("recipe-field-error.png"), fullPage: true });
});

test("save review summarizes changed fields without raw JSON", async ({ page }, info) => {
  await mockApi(page, existing());
  await page.goto("/recipes/insurance-review/edit");
  await page.getByLabel("어떤 질문에 사용하는 분석인가요?").fill("지급액 변화 확인");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await codeEdit(page, recipe => { recipe.steps[0].params.top_n = 8; });
  await page.getByRole("button", { name: "초안 저장", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("분석 목적 · 보험금 지급액 분석 → 지급액 변화 확인")).toBeVisible();
  await expect(dialog.getByText("1단계 표시할 그룹 수 · 7 → 8")).toBeVisible();
  await expect(dialog.locator("pre")).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("recipe-save-review.png"), fullPage: true });
});

test("preview an unsaved step, poll a 202 job, and inspect its result", async ({ page }, info) => {
  await mockApi(page, existing());
  let submitted: Record<string, unknown> | undefined;
  await page.route("**/api/recipes:preview", route => {
    submitted = route.request().postDataJSON();
    return route.fulfill({ status: 202, json: { id: "preview-run", preview: true, status: "open", running: { kind: "preview", started_at: new Date().toISOString() },
      steps: [], validation: [], created_at: new Date().toISOString() } });
  });
  await page.route("**/api/runs/preview-run", route => route.fulfill({ json: {
    id: "preview-run", preview: true, status: "completed", running: null, validation: [], created_at: new Date().toISOString(),
    steps: [{ step: existing().steps[0], method: "method://query.drilldown@2.0.0", result: {
      status: "success", interpretation: "descriptive", warnings: ["일부 그룹만 표시"], validation: [],
      primary: { type: "breakdown_table", title: "미리보기 결과", data: { rows: [{ value: "외래", metric: 42, count: 100 }] } }, artifacts: [],
      provenance: { method: "method://query.drilldown@2.0.0", semantic_refs: [metric, dimension], queries: [{ native_query: { measures: [metric] }, rows: 1, elapsed_ms: 5 }] },
      run_id: "preview-run",
    } }],
  } }));
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await expect(page.getByLabel("미리보기 시작일")).not.toBeVisible();
  await expect(page.getByLabel("미리보기 기간 지정")).toHaveCount(0);
  await page.getByRole("button", { name: "결과 확인", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "단계 실행 중" })).toBeVisible();
  await expect(page.getByText("미리보기 결과")).toBeVisible();
  expect(submitted?.step_index).toBe(0);
  expect((submitted?.scope as { date_range: string[] | null }).date_range).toBeNull();
  expect((submitted?.recipe as Recipe).steps[0].params.top_n).toBe(7);
  await expect(page.getByText("일부 그룹만 표시")).toBeVisible();
  await page.locator("summary").filter({ hasText: /실행 근거/ }).click();
  await expect(page.getByText(/"measures"/)).toBeVisible();
  await page.screenshot({ path: info.outputPath("recipe-preview.png"), fullPage: true });
});

test("a preview stopped by an earlier step returns to that step", async ({ page }) => {
  const before = existing();
  before.steps.push({ id: "trend", method: "query.trend", bindings: { metric: "$scope.primary_metric" }, params: {} });
  await mockApi(page, before);
  await page.route("**/api/recipes:preview", route => route.fulfill({ json: {
    id: "stopped-preview", preview: true, status: "completed", running: null, validation: [], created_at: new Date().toISOString(),
    steps: [{ step: before.steps[0], method: "method://query.drilldown@2.0.0", result: {
      status: "needs_input", interpretation: "descriptive", warnings: [], validation: [], primary: null, artifacts: [],
      provenance: { semantic_refs: [metric], queries: [] }, needs_input: { question: "분류 기준을 선택하세요", field: "dimensions", candidates: [] },
    } }],
  } }));
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:1"]').click();
  await expect(page.getByLabel("미리보기 시작일")).toHaveCount(0);
  await page.getByRole("button", { name: "결과 확인", exact: true }).click();
  await page.getByRole("button", { name: "이 조건으로 확인", exact: true }).click();
  await expect(page.getByText("1단계에서 미리보기가 멈췄습니다.")).toBeVisible();
  await page.getByRole("button", { name: "1단계 설정 확인" }).click();
  await expect(page.locator('.react-flow__node[data-id="step:0"]')).toHaveClass(/selected/);
});

test("editing an existing step-specific metric preserves its override", async ({ page }) => {
  const before = existing();
  before.steps[0].bindings.metric = alternateMetric;
  const state = await mockApi(page, before);
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await expect(page.locator('[class*="inherited"]').getByText("청구 건수", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "지표 변경", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "분석 절차 정보" }).click();
  await page.getByLabel("어떤 질문에 사용하는 분석인가요?").fill("수정한 분석 목적");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.steps[0].bindings.metric).toBe(alternateMetric);
});

test("editing purpose preserves hidden options, scope and procedure", async ({ page }) => {
  const before = existing();
  const state = await mockApi(page, before);
  await page.goto("/recipes/insurance-review/edit");
  await page.getByLabel("어떤 질문에 사용하는 분석인가요?").fill("수정한 분석 목적");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.version).toBe("1.0.1");
  expect(state.submission()).toEqual({ recipe: { ...before, description: "수정한 분석 목적", routing: { ...before.routing, objective: "수정한 분석 목적" }, version: "1.0.1", status: "draft" }, base_version: "1.0.0" });
});

test("restore one advanced default without clearing other explicit values", async ({ page }) => {
  const state = await mockApi(page, existing());
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await codeEdit(page, recipe => { delete recipe.steps[0].params.top_n; });
  await save(page);
  await expect.poll(() => state.submission()?.recipe.version).toBe("1.0.1");
  expect(state.submission()!.recipe.steps[0].params).toEqual({ min_count: 47, rank_by: "count", drill_path: [] });
});

test("a contributed Method generates labels, catalog inputs and conditional options without custom UI", async ({ page }, info) => {
  const contributed = { ...existing(), steps: [{ id: "custom", method: "example.review", bindings: { metric: "$scope.primary_metric" }, params: {} }] };
  await mockApi(page, contributed);
  await page.route("**/api/methods", route => route.fulfill({ json: [{
    name: "example.review", version: "1.0.0", label: "집단 검토", roles: { metric: { kind: "measure", required: true, label: "분석 지표" } }, parameters: {
      territory: { type: "string", label: "나눠 볼 영역", semantic_kind: "dimension", ui_group: "basic" },
      strategy: { type: "enum", label: "검토 방식", enum: ["automatic", "manual"], default: "automatic", ui_group: "basic" },
      threshold: { type: "number", label: "허용 차이", default: 0.1, ui_group: "basic", visible_when: { parameter: "strategy", equals: "manual" } },
    },
  }] }));
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await expect(page.getByLabel("허용 차이")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "집단 검토", exact: true })).toBeVisible();
  await page.getByLabel("나눠 볼 영역", { exact: true }).selectOption(dimension);
  await page.getByLabel("검토 방식", { exact: true }).selectOption("manual");
  await expect(page.getByLabel("허용 차이")).toHaveValue("0.1");
  await expect(page.getByLabel("나눠 볼 영역", { exact: true }).locator("option").filter({ hasText: "지급액" })).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("declarative-method-editor.png"), fullPage: true });
});

test("drilldown exposes one effective dimension, not engine options", async ({ page }, info) => {
  const state = await mockApi(page, existing());
  await page.route("**/api/methods", route => route.fulfill({ json: methods.map(method => method.name === "query.drilldown" ? { ...method, roles: { ...method.roles, dimensions: { kind: "dimension", required: true, multiple: true, label: "나눠 볼 항목", editor_parameter: "next_dimension" } }, parameters: { ...method.parameters, next_dimension: { type: "string", semantic_kind: "dimension", semantic_role: "dimensions", ui_group: "hidden" } } } : method) }));
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  const inspector = page.locator("aside").last();
  await expect(inspector.getByRole("combobox")).toHaveCount(1);
  await expect(page.getByLabel("나눠 볼 항목", { exact: true })).toHaveValue(dimension);
  await expect(page.getByText("추가 옵션", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("정렬 기준")).toHaveCount(0);
  await expect(page.getByLabel("미리보기 기간 지정")).toHaveCount(0);
  await page.getByLabel("이 단계에서 확인할 내용").fill("지급 유형별 차이 확인");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.steps[0].params.top_n).toBe(7);
  expect(state.submission()?.recipe.steps[0].params.rank_by).toBe("count");
  await page.screenshot({ path: info.outputPath("drilldown-essential-inputs.png"), fullPage: true });
});

test("existing investigation stays editable without a destructive mode switch", async ({ page }) => {
  const before = { ...existing(), mode: "investigation" as const, steps: [], allowed_methods: ["query.trend", "query.drilldown"] };
  const state = await mockApi(page, before);
  await page.goto("/recipes/insurance-review/edit");
  await expect(page.getByRole("group", { name: "Recipe 실행 방식" })).toHaveCount(0);
  await page.getByLabel("어떤 질문에 사용하는 분석인가요?").fill("MCP 보험 분석");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.version).toBe("1.0.1");
  expect(state.submission()!.recipe).toEqual({ ...before, version: "1.0.1", status: "draft", description: "MCP 보험 분석", routing: { ...before.routing, objective: "MCP 보험 분석" } });
});
