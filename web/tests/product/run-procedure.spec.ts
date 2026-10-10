import { expect, test } from "@playwright/test";

const base = { id: "recipe-run", origin: "mcp", plan: { question: "어느 부문의 매출이 가장 높은가?", scope: {} },
  steps: [], caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [],
  created_at: "2026-10-01T10:00:00Z" };
const recipeRun = { ...base, plan: { ...base.plan, recipe: "recipe://department-analysis@1.2.0" },
  recipe_snapshot: { name: "상품 부문별 매출 비교", version: "1.2.0", semantic_scope: {} } };

test("list distinguishes Recipe execution from direct analysis and searches by Recipe name", async ({ page }) => {
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: [recipeRun, { ...base, id: "direct-run" }] }));
  await page.goto("/runs");
  await expect(page.getByLabel("Recipe로 실행: 상품 부문별 매출 비교, 버전 1.2.0")).toBeVisible();
  await expect(page.getByText("탐색", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "실행 기록 검색" }).fill("상품 부문별 매출 비교");
  await expect(page.getByText("탐색", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Recipe로 실행: 상품 부문별 매출 비교, 버전 1.2.0")).toBeVisible();
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
  await expect(page.getByLabel("Recipe 미리보기: department-analysis, 버전 1.2.0")).toBeVisible();
  await expect(page.getByText("미리보기", { exact: true })).toBeVisible();
  await expect(page.getByText("v1.2.0", { exact: true })).toHaveCount(0);
});

test("long Recipe names stay compact without obscuring the question and answer", async ({ page }, testInfo) => {
  const longName = "analysis-from-run_01m4aextcdbckgsbz5ygh2kz23";
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: [{ ...recipeRun,
    recipe_snapshot: { ...recipeRun.recipe_snapshot, name: longName },
    conclusion: { source: "caller", answer: "식료품 부문의 매출이 가장 높습니다." },
  }, { ...base, id: "direct-run" }] }));
  await page.goto("/runs");
  await expect(page.getByText("식료품 부문의 매출이 가장 높습니다.")).toBeVisible();
  await expect(page.getByText("Recipe", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("run-list.png"), fullPage: true });
});

test("detail explains why an available Recipe was skipped", async ({ page }, info) => {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale", "ko"));
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [], hierarchies: {} } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [] }));
  await page.route("**/api/runs/recipe-run", route => route.fulfill({ json: { ...base,
    recipe_candidates: [{ recipe: "recipe://department-analysis@1.2.0", name: "department-analysis" }],
    recipe_review: [{ recipe: "recipe://department-analysis@1.2.0", decision: "skipped", reason: "이번 질문은 순위가 아니라 월별 추이를 확인합니다." }],
  } }));
  await page.goto("/runs/recipe-run");
  const review = page.getByRole("region", { name: "Recipe 선택 이유" });
  await expect(review).toContainText("사용하지 않음");
  await expect(review).toContainText("이번 질문은 순위가 아니라 월별 추이를 확인합니다.");
  await expect(review.getByRole("link")).toHaveAttribute("href", "/recipes/department-analysis");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("recipe-choice.png"), fullPage: true });
});
