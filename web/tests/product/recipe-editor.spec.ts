import { test, expect, type Page } from "@playwright/test";
import type { Recipe } from "../../lib/api";

const metric = "cube://local/fact_payment/total_payment_amt";
const alternateMetric = "cube://local/fact_payment/claim_count";
const dimension = "cube://local/fact_payment/payment_type";
const methods = [
  { name: "query.trend", version: "1.0.0", description: "시간에 따른 변화", roles: { metric: { kind: "measure", required: true }, related: { kind: "measure", required: false, multiple: true } }, parameters: { granularity: { type: "enum", enum: ["day", "month"], default: "month", ui_group: "basic" }, vs_previous: { type: "boolean", default: false, ui_group: "basic" } } },
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

test("write a two-step Recipe with purpose, metric and dimensions only", async ({ page }, info) => {
  const state = await mockApi(page);
  await page.goto("/recipes/new");
  await expect(page.getByRole("group", { name: "Recipe 실행 방식" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "목적과 지표" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "초안 저장", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "지표 선택", exact: true }).click();
  await expect(page.getByLabel("분석할 지표", { exact: true })).toBeFocused();
  await page.getByLabel("어떤 분석인가요?").fill("보험금 지급액 변화를 확인하고 지급 유형별로 분석");
  await page.getByLabel("분석할 지표", { exact: true }).selectOption(metric);
  await page.getByText("고급 설정", { exact: true }).click();
  await page.getByLabel("Recipe ID").fill("insurance-review");
  await page.getByText("고급 설정", { exact: true }).click();
  await page.getByRole("button", { name: "첫 분석 추가" }).click();
  await page.getByRole("button", { name: /시간에 따른 변화/ }).click();
  await expect(page.getByText("Recipe 지표 사용", { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "분석 지표" })).toHaveCount(0);
  await expect(page.getByLabel("함께 볼 지표")).not.toBeVisible();
  await page.getByLabel("직전 같은 길이와 비교").check();
  await expect(page.getByText("월별 추이 · 직전 기간 비교")).toBeVisible();
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
  expect(recipe.steps[0].params).toEqual({ vs_previous: true });
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

test("step metric override lives in advanced settings and can return to the Recipe metric", async ({ page }) => {
  const state = await mockApi(page, existing());
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await expect(page.getByText("Recipe 지표 사용", { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "분석 지표" })).toHaveCount(0);
  await page.getByText("고급 설정", { exact: true }).click();
  await page.locator('[class*="refField"]').filter({ hasText: "이 단계에서 사용할 지표" }).getByRole("button", { name: "직접 선택" }).click();
  await page.getByRole("combobox", { name: "이 단계에서 사용할 지표" }).selectOption(alternateMetric);
  await expect(page.locator('[class*="inherited"]').getByText("청구 건수", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Recipe 지표 사용" }).click();
  await expect(page.locator('[class*="inherited"]').getByText("지급액", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "초안 저장", exact: true })).toHaveCount(0);
  await page.locator('[class*="refField"]').filter({ hasText: "이 단계에서 사용할 지표" }).getByRole("button", { name: "직접 선택" }).click();
  await page.getByRole("combobox", { name: "이 단계에서 사용할 지표" }).selectOption(alternateMetric);
  await save(page);
  await expect.poll(() => state.submission()?.recipe.steps[0].bindings.metric).toBe(alternateMetric);
});

test("Recipe-fixed parameters remain visible and locked while editing", async ({ page }) => {
  const locked: Recipe = { ...existing(), method_parameters: { "query.drilldown": { fixed: { top_n: 7 }, runtime_allowed: ["drill_path"] } } };
  const state = await mockApi(page, locked);
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await expect(page.getByText("Recipe 실행 정책")).toBeVisible();
  await expect(page.getByText("고정값: top_n=7")).toBeVisible();
  await page.getByText("고급 설정", { exact: true }).click();
  await expect(page.getByLabel("표시할 그룹 수")).toBeDisabled();
  await page.getByRole("button", { name: "분석 절차 정보" }).click();
  await page.getByLabel("어떤 분석인가요?").fill("보험금 지급액 분석 절차");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.method_parameters?.["query.drilldown"].fixed.top_n).toBe(7);
});

test("an expert can fix a Method value and restrict runtime changes", async ({ page }) => {
  const state = await mockApi(page, existing());
  await page.goto("/recipes/insurance-review/edit");
  await page.getByText("고급 설정", { exact: true }).click();
  await page.getByText("실행 정책", { exact: true }).click();
  await page.getByLabel("항목별로 나눠 보기 top_n 고정").check();
  await expect(page.getByLabel("표시할 그룹 수")).toHaveValue("7");
  await page.getByLabel("항목별로 나눠 보기 실행 중 변경 제한").check();
  await page.getByLabel("항목별로 나눠 보기 min_count 실행 중 허용").check();
  await save(page);
  await expect.poll(() => state.submission()?.recipe.method_parameters?.["query.drilldown"]?.fixed.top_n).toBe(7);
  expect(state.submission()?.recipe.method_parameters?.["query.drilldown"]?.runtime_allowed).toEqual(["min_count"]);
  expect(state.submission()?.recipe.steps[0].params.top_n).toBeUndefined();
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
  await page.getByText("YAML 편집", { exact: true }).click();
  await expect(page.getByLabel("Recipe YAML")).toContainText("description: 보험금 지급액 분석");
  await page.getByLabel("Recipe YAML").fill("name: insurance-review\ndescription: 새 분석 절차\n");
  await page.getByRole("button", { name: "YAML 적용" }).click();
  await expect(page.getByLabel("어떤 분석인가요?")).toHaveValue("새 분석 절차");
  await expect(page.locator('.react-flow__node[data-id="scope"]')).toContainText("새 분석 절차");
  await page.getByLabel("어떤 분석인가요?").fill("그래프에서 수정");
  await expect(page.getByLabel("Recipe YAML")).toContainText("description: 그래프에서 수정");
  await page.getByLabel("Recipe YAML").fill("name: insurance-review\ndescription: 덮어쓰기 시도\n");
  await page.getByLabel("어떤 분석인가요?").fill("더 최근 그래프 변경");
  await page.getByRole("button", { name: "YAML 적용" }).click();
  await expect(page.getByText("그래프가 변경되었습니다. YAML을 새로고침한 뒤 다시 편집해 주세요.")).toBeVisible();
  await expect(page.getByLabel("어떤 분석인가요?")).toHaveValue("더 최근 그래프 변경");
});

test("a save error opens and focuses the exact advanced input", async ({ page }, info) => {
  await mockApi(page, existing());
  await page.route("**/api/recipes:validate?live=true", route => route.fulfill({ status: 422, json: {
    error: { code: "INVALID_RECIPE_EDIT", message: "top_n must be at least 1.", details: { field: "steps[0].params.top_n" } },
  } }));
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await page.getByText("고급 설정", { exact: true }).click();
  await page.getByLabel("표시할 그룹 수").fill("0");
  await save(page);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByLabel("표시할 그룹 수")).toBeVisible();
  await expect(page.getByLabel("표시할 그룹 수")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByLabel("표시할 그룹 수")).toBeFocused();
  await expect(page.getByText("top_n must be at least 1.").last()).toBeVisible();
  await page.screenshot({ path: info.outputPath("recipe-field-error.png"), fullPage: true });
});

test("save review summarizes changed fields without raw JSON", async ({ page }, info) => {
  await mockApi(page, existing());
  await page.goto("/recipes/insurance-review/edit");
  await page.getByLabel("어떤 분석인가요?").fill("지급액 변화 확인");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await page.getByText("고급 설정", { exact: true }).click();
  await page.getByLabel("표시할 그룹 수").fill("8");
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
  await page.getByLabel("미리보기 기간 지정").check();
  await page.getByLabel("미리보기 날짜 기준").selectOption("cube://local/fact_accident/payment_dt");
  await page.getByLabel("미리보기 시작일").fill("2026-06-01");
  await page.getByLabel("미리보기 종료일").fill("2026-06-30");
  await page.getByRole("button", { name: "이 단계까지 미리보기" }).click();
  await expect(page.getByRole("status").filter({ hasText: "단계 실행 중" })).toBeVisible();
  await expect(page.getByText("미리보기 결과")).toBeVisible();
  expect(submitted?.step_index).toBe(0);
  expect((submitted?.scope as { date_range: string[] }).date_range).toEqual(["2026-06-01", "2026-06-30"]);
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
  await page.getByLabel("미리보기 날짜 기준").selectOption("cube://local/fact_accident/payment_dt");
  await page.getByRole("button", { name: "이 단계까지 미리보기" }).click();
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
  await expect(page.getByText("이 단계에서만 사용")).toBeVisible();
  await page.getByRole("button", { name: "분석 절차 정보" }).click();
  await page.getByLabel("어떤 분석인가요?").fill("수정한 분석 목적");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.steps[0].bindings.metric).toBe(alternateMetric);
});

test("editing purpose preserves hidden options, scope and procedure", async ({ page }) => {
  const before = existing();
  const state = await mockApi(page, before);
  await page.goto("/recipes/insurance-review/edit");
  await page.getByLabel("어떤 분석인가요?").fill("수정한 분석 목적");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.version).toBe("1.0.1");
  expect(state.submission()).toEqual({ recipe: { ...before, description: "수정한 분석 목적", version: "1.0.1", status: "draft" }, base_version: "1.0.0" });
});

test("restore one advanced default without clearing other explicit values", async ({ page }) => {
  const state = await mockApi(page, existing());
  await page.goto("/recipes/insurance-review/edit");
  await page.locator('.react-flow__node[data-id="step:0"]').click();
  await page.getByText("고급 설정", { exact: true }).click();
  const setting = page.getByLabel("표시할 그룹 수").locator("../..");
  await setting.getByRole("button", { name: "기본값 사용" }).click();
  await expect(page.getByLabel("표시할 그룹 수")).toHaveValue("10");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.version).toBe("1.0.1");
  expect(state.submission()!.recipe.steps[0].params).toEqual({ min_count: 47, rank_by: "count", drill_path: [] });
});

test("existing investigation stays editable without a destructive mode switch", async ({ page }) => {
  const before = { ...existing(), mode: "investigation" as const, steps: [], allowed_methods: ["query.trend", "query.drilldown"] };
  const state = await mockApi(page, before);
  await page.goto("/recipes/insurance-review/edit");
  await expect(page.getByRole("group", { name: "Recipe 실행 방식" })).toHaveCount(0);
  await page.getByLabel("어떤 분석인가요?").fill("MCP 보험 분석");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.version).toBe("1.0.1");
  expect(state.submission()!.recipe).toEqual({ ...before, version: "1.0.1", status: "draft", description: "MCP 보험 분석" });
});
