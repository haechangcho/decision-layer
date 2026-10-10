import { expect, test } from "@playwright/test";

const run = { id: "coverage-run", origin: "mcp", plan: { question: "비공개 고객의 판매 변화와 예측", scope: {} },
  goals: [
    { id: "sales", description: "판매 변화 확인", semantic_refs: [], required_capabilities: [], interpretation: "descriptive" },
    { id: "forecast", description: "다음 기간 예측", semantic_refs: [], required_capabilities: ["forecast"], interpretation: "descriptive" },
  ], steps: [], caller: { subject: "alice", groups: [] }, shared_with: [], validation: [], status: "completed",
  conclusion: { answer: "판매만 확인했습니다. 예측 방법은 등록되지 않았습니다.", findings: [], limitations: [], goal_outcomes: [
    { goal_id: "sales", status: "supported", step_indices: [], reason: "" },
    { goal_id: "forecast", status: "unsupported", step_indices: [], reason: "등록된 예측 방법이 없습니다.", reason_code: "method_missing" },
  ] }, created_at: "2026-10-07T00:00:00Z" };

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale", "ko"));
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [], hierarchies: {} } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [] }));
  await page.route("**/api/runs/coverage-run", route => route.fulfill({ json: run }));
});

test("unresolved questions remain visible and public proposals never prefill private Run text", async ({ page }, info) => {
  let submitted: Record<string, string> | undefined;
  await page.route("**/api/runs/coverage-run/method-proposal", route => {
    submitted = route.request().postDataJSON();
    return route.fulfill({ json: { body: "Public forecast example", url: "https://github.com/haechangcho/decision-layer/issues/new?title=forecast",
      existing_issues_url: "https://github.com/haechangcho/decision-layer/issues?q=forecast", submitted: false } });
  });
  await page.goto("/runs/coverage-run");
  const unresolved = page.getByRole("region", { name: "아직 답하지 못한 질문" });
  await expect(unresolved).toContainText("다음 기간 예측");
  await expect(unresolved).not.toContainText("판매 변화 확인");
  await expect(page.getByText("등록된 예측 방법이 없습니다.")).toBeVisible();
  await page.getByRole("button", { name: "분석 방법 제안" }).click();
  const dialog = page.getByRole("dialog");
  for (const textbox of await dialog.getByRole("textbox").all()) await expect(textbox).toHaveValue("");
  await dialog.getByRole("textbox").nth(0).fill("Forecast Method");
  await dialog.getByRole("textbox").nth(1).fill("Public monthly sales forecast");
  await dialog.getByRole("textbox").nth(2).fill("Predicted sales with uncertainty");
  await dialog.getByRole("button", { name: "공개 초안 만들기" }).click();
  await expect(dialog.getByRole("link", { name: "GitHub에서 검토" })).toBeVisible();
  expect(submitted?.goal_id).toBe("forecast");
  expect(JSON.stringify(submitted)).not.toContain("비공개");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("public-proposal.png"), fullPage: true });
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await page.screenshot({ path: info.outputPath("question-coverage.png"), fullPage: true });
});

test("fully answered questions do not duplicate the conclusion and graph", async ({ page }) => {
  await page.route("**/api/runs/coverage-run", route => route.fulfill({ json: { ...run,
    conclusion: { ...run.conclusion, goal_outcomes: run.goals.map(goal => ({
      goal_id: goal.id, status: "supported", step_indices: [], reason: "" })),
    },
  } }));
  await page.goto("/runs/coverage-run");
  await expect(page.getByRole("region", { name: "아직 답하지 못한 질문" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "분석 답변" })).toBeVisible();
});

test("missing outcomes are not silently treated as answered", async ({ page }) => {
  await page.route("**/api/runs/coverage-run", route => route.fulfill({ json: { ...run,
    conclusion: { ...run.conclusion, goal_outcomes: [] },
  } }));
  await page.goto("/runs/coverage-run");
  await expect(page.getByRole("region", { name: "아직 답하지 못한 질문" })).toContainText("판매 변화 확인");
  await expect(page.getByRole("region", { name: "아직 답하지 못한 질문" })).toContainText("다음 기간 예측");
});

test("graph distinguishes the Recipe invocation from following analysis", async ({ page }, info) => {
  const ref = "cube://sample/orders/sales";
  const result = { status: "success", interpretation: "descriptive", provides: ["metric_lookup"],
    primary: { type: "table", data: [{ [ref]: 10 }] }, artifacts: [], warnings: [], validation: [],
    provenance: { method: "method://query/aggregate@1.0.0", semantic_refs: [ref], queries: [] } };
  await page.route("**/api/runs/coverage-run", route => route.fulfill({ json: { ...run,
    recipe_snapshot: { name: "sales-review", version: "1.0.0", mode: "pipeline",
      semantic_scope: { primary_metric: ref, related_metrics: [] } },
    recipe_invocation: { id: "recipe_1", completed: true, recipe: "recipe://sales-review@1.0.0", goal_ids: ["sales"], step_ids: ["first"] },
    steps: [
      { step: { id: "first", method: "query.aggregate", bindings: { metric: ref }, params: {}, purpose: "정해진 판매 조회" }, result, invocation_id: "recipe_1" },
      { step: { id: "second", method: "query.aggregate", bindings: { metric: ref }, params: {}, purpose: "후속 확인", exploration: true }, result },
    ] } }));
  await page.goto("/runs/coverage-run");
  const graph = page.getByRole("region", { name: "실행 그래프" });
  await expect(graph).toContainText("Recipe에 포함된 단계");
  await expect(graph).toContainText("추가 분석");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("invocation-and-exploration.png"), fullPage: true });
});
