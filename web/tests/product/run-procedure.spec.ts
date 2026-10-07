import { expect, test } from "@playwright/test";

const base = { id: "recipe-run", origin: "mcp", plan: { question: "어느 부문의 매출이 가장 높은가?", scope: {} },
  steps: [], caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [],
  created_at: "2026-10-01T10:00:00Z" };
const recipeRun = { ...base, plan: { ...base.plan, recipe: "recipe://department-analysis@1.2.0" },
  recipe_snapshot: { name: "상품 부문별 매출 비교", version: "1.2.0", semantic_scope: {} } };

test("list distinguishes Recipe execution from direct analysis and searches by Recipe name", async ({ page }) => {
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: [recipeRun, { ...base, id: "direct-run" }] }));
  await page.goto("/runs");
  await expect(page.getByText("Recipe로 실행: 상품 부문별 매출 비교")).toBeVisible();
  await expect(page.getByText("Recipe 없이 분석")).toBeVisible();
  await page.getByRole("textbox", { name: "실행 기록 검색" }).fill("상품 부문별 매출 비교");
  await expect(page.getByText("Recipe 없이 분석")).toHaveCount(0);
  await expect(page.getByText("Recipe로 실행: 상품 부문별 매출 비교")).toBeVisible();
});

test("detail shows the executed Recipe version and link even if its current definition changes", async ({ page }, testInfo) => {
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [], hierarchies: {} } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [] }));
  await page.route("**/api/runs/recipe-run", route => route.fulfill({ json: recipeRun }));
  await page.goto("/runs/recipe-run");
  const procedure = page.getByLabel("사용한 분석 절차");
  await expect(procedure).toContainText("Recipe로 실행");
  await expect(procedure).toContainText("실행 당시 버전 1.2.0");
  await expect(procedure.getByRole("link")).toHaveAttribute("href", `/recipes/${encodeURIComponent(recipeRun.recipe_snapshot.name)}`);
  await page.screenshot({ path: testInfo.outputPath("recipe-execution.png"), fullPage: true });
});

test("historical Recipe runs without a snapshot retain reference and preview identity", async ({ page }) => {
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: [
    { ...base, preview: true, plan: recipeRun.plan },
  ] }));
  await page.goto("/runs");
  await expect(page.getByText("Recipe 미리보기: department-analysis")).toBeVisible();
  await expect(page.getByText("v1.2.0", { exact: true })).toBeVisible();
  await expect(page.getByText("Recipe로 실행:")).toHaveCount(0);
});
