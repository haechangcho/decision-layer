import { test, expect, type Page } from "@playwright/test";
import type { Recipe } from "../../lib/api";

const metric = "cube://local/fact_payment/total_payment_amt";
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
    { ref: dimension, kind: "dimension", title: "지급 유형", public: true },
    { ref: "cube://local/fact_accident/payment_dt", kind: "time_dimension", title: "지급일", public: true },
    { ref: "cube://local/fact_accident/claim_dt", kind: "time_dimension", title: "청구일", public: true },
  ] } }));
  await page.route("**/api/methods", route => route.fulfill({ json: methods }));
  await page.route("**/api/recipes:validate?live=true", route => route.fulfill({ json: { valid: true, semantic_checked: true } }));
  await page.route("**/api/recipes/insurance-review", async route => {
    if (route.request().method() === "PUT") {
      submitted = route.request().postDataJSON();
      expect(route.request().headers()["x-recipe-admin-key"]).toBe("test-editor-key");
      saved = submitted!.recipe;
    }
    await route.fulfill({ json: saved });
  });
  return { submission: () => submitted };
}

async function save(page: Page) {
  await page.getByRole("button", { name: "Recipe 저장", exact: true }).click();
  await page.getByLabel("Recipe 편집 키").fill("test-editor-key");
  await page.getByRole("button", { name: "새 버전 저장" }).click();
}

test("write a two-step Recipe with purpose, metric and dimensions only", async ({ page }, info) => {
  const state = await mockApi(page);
  await page.goto("/recipes/new");
  await expect(page.getByRole("group", { name: "Recipe 실행 방식" })).toHaveCount(0);
  await page.getByLabel("어떤 분석인가요?").fill("보험금 지급액 변화를 확인하고 지급 유형별로 분석");
  await page.getByLabel("분석할 지표", { exact: true }).selectOption(metric);
  await page.getByText("고급 설정", { exact: true }).click();
  await page.getByLabel("Recipe ID").fill("insurance-review");
  await page.getByText("고급 설정", { exact: true }).click();
  await page.getByRole("button", { name: "분석 절차 구성" }).click();
  await page.getByRole("button", { name: /시간에 따른 변화/ }).click();
  await expect(page.getByLabel("함께 볼 지표")).not.toBeVisible();
  await page.getByLabel("직전 같은 길이와 비교").check();
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
  expect(recipe.steps[1].bindings.dimensions).toEqual([dimension]);
  expect(recipe.steps[1].params).toEqual({});
  await expect(page.getByText("v1.0.0 · 저장됨")).toBeVisible();
  await page.getByRole("button", { name: "Recipe 실행", exact: true }).click();
  await expect(page).toHaveURL(/\/recipes\/insurance-review$/);
  await expect(page.getByLabel("날짜 기준")).toHaveValue("");
  await expect(page.getByRole("button", { name: "이 Recipe로 분석" })).toBeDisabled();
  await page.getByLabel("날짜 기준").selectOption("cube://local/fact_accident/payment_dt");
  await expect(page.getByRole("button", { name: "이 Recipe로 분석" })).toBeEnabled();
});

test("editing purpose preserves hidden options, scope and procedure", async ({ page }) => {
  const before = existing();
  const state = await mockApi(page, before);
  await page.goto("/recipes/insurance-review/edit");
  await page.getByLabel("어떤 분석인가요?").fill("수정한 분석 목적");
  await save(page);
  await expect.poll(() => state.submission()?.recipe.version).toBe("1.0.1");
  expect(state.submission()).toEqual({ recipe: { ...before, description: "수정한 분석 목적", version: "1.0.1" }, base_version: "1.0.0" });
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
  expect(state.submission()!.recipe).toEqual({ ...before, version: "1.0.1", description: "MCP 보험 분석" });
});
