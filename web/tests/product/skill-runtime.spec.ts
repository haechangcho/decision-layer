import { expect, test } from "@playwright/test";

const ref = "cube://journey/campaign_household_outcomes/post_sales_mean";
const stamp = "2026-10-15T10:00:00Z";
const manifest = { name: "analysis.drilldown", version: "1.0.0", implementation: "skill", agent_executable: true,
  kind: "query", description: "Inspect metric groups", interpretation: "association", execution: "agent_guided",
  roles: {}, parameters: {}, outputs: ["table"] };
const guide = { name: manifest.name, version: "1.0.0", sha256: "a".repeat(64), enforcement: "advisory",
  markdown: "Query actual groups; never infer causation.", suggested_methods: [] };
const result = { status: "needs_input", primary: null, artifacts: [], warnings: [], validation: [],
  provenance: { method: "method://analysis.drilldown@1.0.0", semantic_refs: [], queries: [] } };
function run(queries: unknown[] = []) {
  return { id: "skill-runtime", origin: "mcp", status: "open", active_skill_step: "groups", created_at: stamp,
    plan: { question: "캠페인별 차이를 조사해줘", scope: {} }, caller: { subject: "alice", groups: [] },
    shared_with: [], validation: [], steps: [{ step: { id: "groups", method: manifest.name, bindings: { metric: ref }, params: {} },
      method: result.provenance.method, result, started_at: stamp,
      skill: { guide, status: "awaiting_agent", queries } }] };
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale", "ko"));
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [], hierarchies: {} } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [manifest] }));
});

test("waiting Skill refreshes recorded failures without offering premature completion", async ({ page }, info) => {
  let queries: unknown[] = [];
  await page.route("**/api/runs/skill-runtime", route => route.fulfill({ json: run(queries) }));
  await page.goto("/runs/skill-runtime");
  await expect(page.getByRole("status")).toContainText("Skill 단계에서 AI 실행을 기다립니다");
  await expect(page.getByText("아직 실행한 쿼리가 없습니다.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "결론 저장하고 완료" })).toHaveCount(0);
  queries = [{ id: "wrong_period", purpose: "기간 거부 기록 확인", status: "failed", started_at: stamp,
    spec: { measures: [ref], time: { date_range: ["2000-01-01", "2000-12-31"] } },
    error: { code: "INVALID_BINDING", message: "Query dates must equal the Run period." } }];
  await expect(page.getByText("wrong_period · 조회 실패 · 기간 거부 기록 확인")).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole("region", { name: "Skill 실행 로그" }).getByRole("alert")).toContainText("Query dates must equal the Run period");
  await page.getByText("실행 당시 지침과 해시").click();
  await expect(page.getByText(guide.markdown)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("skill-query-log.png"), fullPage: true });
});

test("query-executing Skill can be selected for a Recipe while its prose remains advisory", async ({ page }) => {
  await page.route("**/api/methods/analysis.drilldown", route => route.fulfill({ json: manifest }));
  await page.route("**/api/methods/analysis.drilldown/guide", route => route.fulfill({ json: guide }));
  await page.goto("/methods/analysis.drilldown");
  await expect(page.getByRole("link", { name: "분석 절차 만들기" })).toBeVisible();
  await expect(page.getByText(guide.markdown)).toBeVisible();
});
