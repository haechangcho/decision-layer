import { expect, test } from "@playwright/test";

const metric = "cube://test/orders/revenue";
const category = "cube://test/products/category";
const store = "cube://test/orders/store";
const path = [{ member: category, value: "Alpha" }];
const target = [{ member: store, value: "42" }];
const source = (step_id: string, project: string) => ({ source: "step", step_id, output: "ranked_groups", select: "first", project });
const methods = [{ name: "query.drilldown", version: "2.0.0", kind: "query", description: "", roles: { metric: { kind: "measure", required: true }, dimensions: { kind: "dimension", required: true, multiple: true } }, parameters: { drill_path: { type: "drill_path", default: [], required: false }, top_n: { type: "integer", default: 10, required: false } }, selection_outputs: ["ranked_groups"] },
  { name: "query.peer_comparison", version: "1.0.0", kind: "query", description: "", roles: { metric: { kind: "measure", required: true } }, parameters: { subject: { type: "drill_path", required: true, ui_group: "basic" }, peers: { type: "drill_path", default: [], required: false, ui_group: "basic" } } }];
const steps = [
  { id: "groups", method: "query.drilldown", purpose: "최고 부문 찾기", bindings: { metric, dimensions: [category, store] }, params: { drill_path: [] } },
  { id: "members", method: "query.drilldown", purpose: "선택한 부문의 최고 매장 찾기", bindings: { metric, dimensions: [category, store] }, params: { drill_path: path } },
  { id: "compare", method: "query.peer_comparison", purpose: "선택한 매장 비교", bindings: { metric }, params: { subject: target, peers: path } },
];
const recipe = { name: "rule-test", version: "1.0.0", description: "최고 부문과 매장을 찾아 비교", status: "draft", routing: { use_for: [], do_not_use_for: [] }, semantic_scope: { primary_metric: metric, related_metrics: [], preferred_dimensions: [], required_filters: [] }, mode: "pipeline", steps, allowed_methods: [], validators: [], limits: { max_steps: 12, max_queries: 30 } };
const result = { status: "success", primary: null, artifacts: [], validation: [], warnings: [], provenance: { semantic_refs: [], queries: [] } };

test.beforeEach(async ({ page }) => {
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/methods", route => route.fulfill({ json: methods }));
  await page.route("**/api/sources/current/readiness", route => route.fulfill({ json: { metrics: [] } }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [{ ref: metric, kind: "measure", title: "매출" }, { ref: category, kind: "dimension", data_type: "string", title: "부문" }, { ref: store, kind: "dimension", data_type: "string", title: "매장" }], hierarchies: {} } }));
  await page.route("**/api/runs/rules-test", route => route.fulfill({ json: { id: "rules-test", plan: { question: "최고 부문과 매장을 비교해줘", scope: { date_range: ["2026-01-01", "2026-01-31"] } }, steps: steps.map(step => ({ step, method: `method://${step.method}@1.0.0`, result, started_at: "2026-01-01T10:00:00Z", finished_at: "2026-01-01T10:00:01Z" })), caller: { subject: "alice" }, shared_with: [], status: "completed", validation: [], created_at: "2026-01-01T10:00:00Z" } }));
  await page.route("**/api/runs/rules-test/recipe-candidate?*", route => route.fulfill({ json: { recipe, source_run_id: "rules-test", selected_steps: [0, 1, 2], review_notes: ["Fixed groups require review"] } }));
});

test("one click registers a runtime procedure without opening a review popup", async ({ page }, info) => {
  let requests = 0;
  await page.route("**/api/runs/rules-test/recipe", async route => {
    expect(route.request().postDataJSON()).toEqual({});
    requests++;
    await route.fulfill({ json: { ...recipe, name: "runtime-rules", status: "published" } });
  });
  await page.goto("/runs/rules-test");
  await page.getByRole("button", { name: "Recipe로 등록", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recipe로 등록했습니다" })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Recipe 보기", exact: true })).toHaveAttribute("href", "/recipes/runtime-rules");
  await page.screenshot({ path: info.outputPath("recipe-one-click.png"), fullPage: true });
  expect(requests).toBe(1);
});

test("editor preserves a selected source and prevents removing its upstream step", async ({ page }, info) => {
  const dynamic = { ...recipe, status: "published", steps: steps.map((step, i) => i === 1 ? { ...step, params: { drill_path: source("groups", "path") } } : step) };
  await page.route("**/api/recipes/rule-test/edit", route => route.fulfill({ json: dynamic }));
  await page.goto("/recipes/rule-test/edit");
  const nodes = page.locator(".react-flow__node-recipe");
  await expect(nodes).toHaveCount(4);
  await nodes.nth(2).click();
  await expect(page.getByLabel("분석 범위 설정 방식")).toHaveCount(0);
  await expect(page.getByText(/1단계에서 찾은 대상 안에서 분석/)).toBeVisible();
  await nodes.nth(1).click();
  await page.getByRole("button", { name: "단계 삭제", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "이전 결과를 사용하는 단계" })).toBeVisible();
  await expect(nodes).toHaveCount(4);
  await page.screenshot({ path: info.outputPath("recipe-source-editor.png"), fullPage: true });
});

test("nested source summaries describe the selected member and its parent population", async ({ page }) => {
  const dynamic = { ...recipe, status: "published", steps: steps.map((step, index) => index === 1 ? { ...step, params: { drill_path: source("groups", "path") } } : index === 2 ? { ...step, params: { subject: source("members", "condition"), peers: source("members", "parents") } } : step) };
  await page.route("**/api/recipes/rule-test/edit", route => route.fulfill({ json: dynamic }));
  await page.goto("/recipes/rule-test/edit");
  await page.locator('.react-flow__node[data-id="step:2"]').click();
  await expect(page.getByText(/2단계에서 이 단계의 정렬 기준으로 선택한 매장 · 실행마다/)).toBeVisible();
  await expect(page.getByText(/선택한 매장과 같은 부문 · 실행마다/)).toBeVisible();
  await expect(page.getByLabel("비교 대상 설정 방식")).toHaveCount(0);
});
