import { expect, test } from "@playwright/test";

const step = { id: "compare", method: "query.peer_comparison", purpose: "7~9월 최고 집단을 비교한다.",
  bindings: { metric: "cube://sample/operations/rate" }, params: {} };
const result = { status: "success", interpretation: "descriptive", primary: { type: "breakdown_table", title: "집단 비교",
  data: { metric: step.bindings.metric, subject: [{ member: "cube://sample/operations/team", value: "A" }],
    benchmark_aggregation: "semantic_provider", statistical_judgement: "not_tested", rows: [
      { value: "대상", metric: 10, count: 100, difference_from_subject: 0 },
      { value: "동료 집단 (대상 제외)", metric: 8, count: 500, difference_from_subject: 2 },
      { value: "전체 집단 (대상 제외)", metric: 7, count: 1000, difference_from_subject: 3 },
    ] } }, artifacts: [], warnings: [], validation: [], provenance: { queries: [], semantic_refs: [] } };
const run = { id: "context-run", plan: { recipe: "recipe://comparison@1.0.0", question: "4~6월 집단 비교", scope: { date_range: ["2001-04-01", "2001-06-30"] } },
  recipe_snapshot: { name: "comparison", version: "1.0.0", origin_runs: ["original"], semantic_scope: {}, mode: "pipeline" },
  steps: [{ step, result, method: "method://query/peer_comparison@1.0.0" }],
  caller: { subject: "alice", groups: [] }, shared_with: [], validation: [], status: "completed", created_at: "2026-10-07T00:00:00Z" };

test.beforeEach(async ({ page }) => {
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [], hierarchies: {} } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [] }));
});

test("historical original purpose is separated from current scope and comparison meaning", async ({ page }, info) => {
  await page.route("**/api/runs/context-run", route => route.fulfill({ json: run }));
  await page.goto("/runs/context-run");
  const graph = page.getByRole("region", { name: "실행 그래프" });
  await expect(graph).not.toContainText(step.purpose);
  await expect(page.getByText("등록 당시 단계 설명", { exact: true })).toBeVisible();
  await expect(page.getByText("이번 실행 기간", { exact: true })).toBeVisible();
  await expect(page.getByText(/구성원별 값의 단순 평균이 아닙니다/)).toBeVisible();
  await expect(page.getByText(/표본 건수가 있더라도 이 Method는 유의성을 검정하지 않습니다/)).toBeVisible();
  await expect(page.getByRole("cell", { name: "비교 집단 (대상 제외)", exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath("comparison-context.png"), fullPage: true });
});

test("explicit procedural purposes are not treated as historical intent", async ({ page }) => {
  await page.route("**/api/runs/context-run", route => route.fulfill({ json: { ...run, steps: [{ ...run.steps[0],
    step: { ...step, purpose: "선택한 집단을 비교 집단과 비교", purpose_context: "procedure" } }] } }));
  await page.goto("/runs/context-run");
  await expect(page.getByRole("region", { name: "실행 그래프" })).toContainText("선택한 집단을 비교 집단과 비교");
  await expect(page.getByText("등록 당시 단계 설명", { exact: true })).toHaveCount(0);
});
