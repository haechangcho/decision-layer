import { expect, test } from "@playwright/test";
import korean from "../../../src/decision_layer/i18n/ko.json";

const ref = "cube://journey/campaign_household_outcomes/post_sales_mean";
const stamp = "2026-10-15T10:00:00Z";
const manifest = { name: "analysis.drilldown", version: "1.0.0", implementation: "skill", agent_executable: true,
  kind: "query", description: "Inspect metric groups",  execution: "agent_guided",
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
  await expect(page.getByRole("status")).toContainText("AI 실행 대기 중입니다");
  await expect(page.locator("main details")).toHaveCount(0);
  await page.getByRole("tab", {name:"쿼리 0개"}).click();
  await expect(page.getByText("아직 실행한 쿼리가 없습니다.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "결론 저장하고 완료" })).toHaveCount(0);
  queries = [{ id: "wrong_period", purpose: "기간 거부 기록 확인", status: "failed", started_at: stamp,
    spec: { measures: [ref], time: { date_range: ["2000-01-01", "2000-12-31"] } },
    error: { code: "INVALID_BINDING", message: "Query dates must equal the Run period." } }];
  await expect(page.getByRole("heading", {name:"기간 거부 기록 확인",exact:true})).toBeVisible({ timeout: 10000 });
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


test("routine notices stay off the working view while raw evidence remains available", async ({ page }) => {
  const validation = { validator: "skill_query", status: "pass", code: "QUERY_CHECKED", message: "Bound metrics, period, inherited population and provider query checks executed." };
  const warning = "Returned rows are a bounded query result, not proof of complete population, appropriate peers or causal validity.";
  const queryResult = { ...result, status: "success", validation: [validation], warnings: [warning],
    primary: { type: "table", title: "Agent title stays unchanged", data: [{ receipts: 42 }] },
    provenance: { ...result.provenance, queries: [{ provider: "cube", instance: "journey", rows: 1, elapsed_ms: 15,
      native_query: { measures: ["retail_transactions.receipts"], _view: "retail_transactions" },
      compiled_sql: "SELECT sum(sales_value) FROM journey.transaction_data WHERE transaction_date >= $1" }] } };
  const finished = run([{ id: "read", purpose: "기록된 거래 조회", status: "success", started_at: stamp, spec: {}, result: queryResult }]);
  finished.active_skill_step = "";
  Object.assign(finished.steps[0], { result: { ...queryResult, warnings: ["Skill adherence, peer suitability, source completeness and causal assumptions are not verified. Only recorded query checks executed."] } });
  await page.route("**/api/runs/skill-runtime", route => route.fulfill({ json: finished }));
  await page.goto("/runs/skill-runtime");
  await page.getByRole("tab", { name: "쿼리 1개" }).click();
  const inspector = page.getByRole("region", { name: "조회 상세" });
  await expect(inspector.getByRole("heading", { name: "Cube 쿼리", exact: true })).toBeVisible();
  await expect(inspector.getByRole("heading", { name: "컴파일 SQL", exact: true })).toBeVisible();
  await expect(inspector.getByRole("region", { name: "기록된 조회 근거" }).locator("pre").filter({ hasText: "SELECT sum" })).toContainText("$1");
  await expect(inspector.getByLabel("쿼리 1 원본 요청")).not.toContainText("_view");
  await expect(inspector.getByText(warning, { exact: true })).not.toBeVisible();
  await expect(inspector.getByText(validation.message, { exact: true })).not.toBeVisible();
  await expect(inspector.getByRole("heading", { name: "조회 검사" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /기록된 거래 조회.*read/ })).toHaveCount(0);
  await expect(inspector.getByText("선택한 지표, 기간, 상속된 분석 대상과 시맨틱 레이어 조회 조건을 확인했습니다.")).not.toBeVisible();
  await expect(page.getByText("이 분석 절차를 Recipe로 저장", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "공유 설정", exact: true })).toHaveCount(1);
  await page.getByLabel("language").selectOption("en");
  const english = page.getByRole("region", { name: "Query details" });
  await expect(english.getByText(warning, { exact: true })).not.toBeVisible();
  await english.getByRole("button", { name: "Original request" }).click();
  const raw = page.getByRole("dialog", { name: "Original query request" });
  await expect(raw).toContainText(warning);
  await expect(raw).toContainText(validation.message);
  await expect(raw).toContainText("_view");
});


for (const language of ["en", "ko"] as const) {
  test(`concise Skill view preserves concrete issues and raw evidence (${language} record)`, async ({ page }) => {
    const messages = korean as Record<string, string>;
    const local = (message: string) => language === "ko" ? messages[message] : message;
    const routineWarning = local("Returned rows are a bounded query result, not proof of complete population, appropriate peers or causal validity.");
    const routineCheck = local("Bound metrics, period, inherited population and provider query checks executed.");
    const primary = { type: "table", title: "거래 수취액", data: [{ receipts: 42 }] };
    const evidence = { ...result, status: "success", primary, warnings: [routineWarning, "일부 거래일 데이터가 누락됐습니다."],
      validation: [{ validator: "skill.query_scope@1", code: "QUERY_SCOPE", status: "pass", message: routineCheck },
        { validator: "freshness", code: "DATA_STALE", status: "warning", message: "마지막 거래일을 확인하세요." }] };
    const finished = run([{ id: "read", purpose: "거래 조회", status: "success", started_at: stamp, spec: {}, result: evidence }]);
    finished.active_skill_step = "";
    Object.assign(finished.steps[0], { result: { ...evidence, artifacts: [primary] } });
    finished.steps[0].skill.status = "completed";
    await page.route("**/api/runs/skill-runtime", route => route.fulfill({ json: finished }));
    await page.goto("/runs/skill-runtime");
    await expect(page.getByRole("tab", { name: "실행 검증", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "검증·추가 결과 1개" })).toHaveCount(0);
    await page.getByRole("tab", { name: "쿼리 1개" }).click();
    const inspector = page.getByRole("region", { name: "조회 상세" });
    await expect(inspector.getByText("일부 거래일 데이터가 누락됐습니다.", { exact: true })).toBeVisible();
    await expect(inspector.locator("p").filter({ hasText: "마지막 거래일을 확인하세요." })).toBeVisible();
    await expect(inspector.getByText(routineWarning, { exact: true })).not.toBeVisible();
    await expect(inspector.getByText(routineCheck, { exact: true })).not.toBeVisible();
    await expect(page.getByLabel("조회 목록", { exact: true })).toHaveCount(0);
    const actions = page.getByRole("region", { name: "Recipe 등록", exact: true });
    await expect(actions.getByRole("button", { name: "공유 설정", exact: true })).toBeVisible();
    await expect(actions.getByRole("heading")).toHaveCount(0);
    await inspector.getByRole("button", { name: "요청 원문" }).click();
    const raw = page.getByRole("dialog", { name: "조회 요청 원문" });
    await expect(raw).toContainText(routineWarning);
    await expect(raw).toContainText(routineCheck);
  });
}
