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
  await expect(page.locator("main details")).toHaveCount(0);
  await page.getByRole("tab", {name:"쿼리 0개"}).click();
  await expect(page.getByText("아직 실행한 쿼리가 없습니다.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "결론 저장하고 완료" })).toHaveCount(0);
  queries = [{ id: "wrong_period", purpose: "기간 거부 기록 확인", status: "failed", started_at: stamp,
    spec: { measures: [ref], time: { date_range: ["2000-01-01", "2000-12-31"] } },
    error: { code: "INVALID_BINDING", message: "Query dates must equal the Run period." } }];
  await expect(page.getByRole("button", {name:/기간 거부 기록 확인.*wrong_period/})).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole("region", { name: "Skill 실행 로그" }).getByRole("alert")).toContainText("Query dates must equal the Run period");
  await page.getByRole("tab",{name:"출처",exact:true}).click();
  await page.getByRole("button",{name:"실행 당시 지침 보기"}).click();
  await expect(page.getByText(guide.markdown)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("skill-query-log.png"), fullPage: true });
});

test("query-executing Skill can be selected for a Recipe while its prose remains advisory", async ({ page }) => {
  await page.route("**/api/methods/analysis.drilldown", route => route.fulfill({ json: manifest }));
  await page.route("**/api/methods/analysis.drilldown/guide", route => route.fulfill({ json: guide }));
  const content = `---\nname: ${guide.name}\nversion: ${guide.version}\ndescription: Inspect metric groups\nquery_execution: true\n---\n${guide.markdown}`;
  await page.route("**/api/methods/analysis.drilldown/source", route => route.fulfill({json:{
    implementation:"skill",version:guide.version,content,permissions:{edit:false,publish:false},history:[],
  }}));
  await page.goto("/methods/analysis.drilldown");
  await expect(page.getByRole("link", { name: "분석 절차 만들기" })).toBeVisible();
  await page.getByRole("tab",{name:"분석 지침",exact:true}).click();
  await expect(page.getByLabel("Skill Markdown 원본")).toHaveText(content);
});

test("query inspection preserves errors, results and snapshot evidence without stacked disclosures", async ({ page }) => {
  const finished = run([
    {id:"ok", purpose:"정상 범위 조회", status:"success", started_at:stamp, spec:{marker:"first-query"}, result:{...result,status:"success",primary:{type:"table",title:"원래 결과",data:[{group:"A",amount:42}]},validation:[],warnings:["일부 범위만 조회했습니다."]}},
    {id:"bad",purpose:"거절된 범위 조회",status:"failed",started_at:stamp,spec:{marker:"second-query"},error:{code:"INVALID_BINDING",message:"선택한 기간과 다릅니다."}},
  ]);
  finished.active_skill_step = "";
  await page.route("**/api/runs/skill-runtime", route => route.fulfill({ json: finished }));
  await page.goto("/runs/skill-runtime");
  await expect(page.locator("main details")).toHaveCount(0);
  await expect(page.getByRole("alert").filter({hasText:"선택한 기간과 다릅니다."})).toBeVisible();
  await page.getByRole("button",{name:"실패한 조회 확인"}).click();
  const inspector = page.getByRole("region",{name:"조회 상세"});
  await expect(inspector).toContainText("INVALID_BINDING");
  await page.getByRole("button",{name:/정상 범위 조회.*ok/}).click();
  await expect(inspector.getByRole("cell",{name:"42",exact:true})).toBeVisible();
  await expect(inspector.getByRole("heading",{name:"정상 범위 조회",exact:true})).toHaveCount(1);
  await expect(inspector).toContainText("일부 범위만 조회했습니다.");
  const raw = inspector.getByRole("button",{name:"요청 원문"});
  await raw.click();
  const dialog = page.getByRole("dialog",{name:"조회 요청 원문"});
  await expect(dialog).toContainText("first-query");
  await expect(dialog).not.toContainText("second-query");
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(raw).toBeFocused();
  await page.getByRole("tab",{name:"출처",exact:true}).click();
  await page.getByRole("button",{name:"실행 당시 지침 보기"}).click();
  await expect(page.getByRole("dialog",{name:"실행 당시 Skill 지침"})).toContainText(guide.sha256);
  await expect(page.getByRole("dialog",{name:"실행 당시 Skill 지침"})).toContainText(guide.markdown);
  await page.getByRole("dialog",{name:"실행 당시 Skill 지침"}).getByRole("button",{name:"닫기"}).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
