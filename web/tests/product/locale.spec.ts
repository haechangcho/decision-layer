import { expect, test, type Page } from "@playwright/test";

// Run the same checks against Next or the console bundled in the Python wheel.
const prefix = process.env.DL_TEST_UI_PREFIX || "";
const stamp = "2026-02-01T00:00:00Z";
const metric = { ref: "cube://shop/customers/revenue", kind: "measure", title: "Revenue", data_type: "number", public: true };
const python = { name: "stats.regression_adjustment", version: "2.0.0", kind: "stats", implementation: "python", execution: "dataframe", interpretation: "association", description: "Analyze observed relationships.",
  roles: {}, parameters: {}, outputs: ["estimate"], data_inputs: { data: { measures: ["outcome"], dimensions: [], entity: "entity_id", columns: {}, column_args: ["outcome"], format: "dataframe", minimum_rows: 10, period_role: "current" } } };
const skill = { ...python, name: "analysis.drilldown", implementation: "skill", agent_executable: true, data_inputs: {} };
const guide = { name: skill.name, version: "2.0.0", sha256: "a".repeat(64), enforcement: "advisory", markdown: "# Review groups\nQuery the governed metric.", suggested_methods: [] };
const source = "def analyze(data):\n    return data\n";

async function setup(page: Page) {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale", "en"));
  await page.route("**/api/**", route => {
    const path = new URL(route.request().url()).pathname.replace(/^.*\/api/, "");
    const payload = path === "/methods" ? [skill, python]
      : path === `/methods/${python.name}` ? python
      : path === `/methods/${skill.name}` ? skill
      : path.endsWith("/guide") ? guide
      : path.endsWith("/source") ? { implementation: "python", version: "2.0.0", content: source, code: { available: true, authoring_content: source, files: [] }, permissions: { edit: true, publish: true }, history: [] }
      : path === "/me" ? { subject: "alice" }
      : path === "/project" ? { name: "my_team", path: "/projects/my_team" }
      : path === "/sources/current" ? { provider: "cube", instance: "shop", api_url: "http://localhost:4000", auth_method: "none", service_groups: [], editable: true, environment_overrides: {} }
      : path === "/semantic/catalog" ? { objects: [metric], hierarchies: {} }
      : path === "/sources/current/readiness" ? { metrics: [] }
      : [];
    return route.fulfill({ json: payload });
  });
}
async function language(page: Page, locale: string) {
  await page.getByRole("combobox", { name: "language", exact: true }).selectOption(locale);
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
}
async function noKoreanUI(page: Page) {
  await expect(page.locator("main")).not.toContainText(/[가-힣]/);
}

test("language switching updates libraries, catalog, project navigation and API headers", async ({ page }) => {
  await setup(page);
  await page.goto(`${prefix}/methods`);
  await expect(page.getByRole("heading", { name: "Methods", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Python Methods" })).toContainText("OLS regression");
  await page.getByRole("textbox", { name: "Search Methods", exact: true }).fill("OLS regression");
  const reloaded = page.waitForRequest(request => request.url().endsWith("/api/methods") && request.headers()["accept-language"] === "ko");
  await language(page, "ko");
  await reloaded;
  // Search includes localized fallback labels and is recomputed on locale changes.
  await expect(page.getByRole("region", { name: "Python 분석 방법" })).toHaveCount(0);
  await page.getByRole("textbox", { name: "분석 방법 검색", exact: true }).fill("");
  await expect(page.getByRole("region", { name: "Python 분석 방법" })).toContainText("OLS 회귀분석");
  await language(page, "en");
  await noKoreanUI(page);
  const project = page.locator(".app-project summary");
  if (await project.count()) {
    await project.click();
    await expect(page.getByText("Current project", { exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
  }
  for (const [path, english, korean] of [
    ["/recipes", "Recipes", "레시피"], ["/runs", "Runs", "실행 기록"],
    ["/catalog", "Metric catalog", "지표 탐색"], ["/sources", "Semantic layer connection", "시맨틱 레이어 연결"],
  ]) {
    await page.goto(`${prefix}${path}`);
    await expect(page.getByRole("heading", { name: english, exact: true }).first()).toBeVisible();
    await noKoreanUI(page);
    await language(page, "ko");
    await expect(page.getByRole("heading", { name: korean, exact: true }).first()).toBeVisible();
    await language(page, "en");
    await noKoreanUI(page);
  }
});

test("Method inputs, source diff and editor localize without losing unsaved code", async ({ page }) => {
  await setup(page);
  await page.goto(`${prefix}/methods/${python.name}`);
  await expect(page.getByRole("region", { name: "data", exact: true })).toContainText("Minimum 10 rows.");
  await noKoreanUI(page);
  await page.getByRole("tab", { name: "Python code", exact: true }).click();
  await page.getByRole("button", { name: "Edit Python", exact: true }).click();
  const changed = `${source}# unsaved edit\n`;
  await page.getByRole("textbox", { name: "Authorable Python code", exact: true }).fill(changed);
  await language(page, "ko");
  const editor = page.getByRole("textbox", { name: "Python 작성 코드", exact: true });
  await expect(editor).toContainText("# unsaved edit");
  await page.getByRole("tab", { name: "변경 비교", exact: true }).click();
  await expect(page.getByRole("heading", { name: "게시 v2.0.0", exact: true })).toBeVisible();
  await language(page, "en");
  await expect(page.getByRole("heading", { name: "Published v2.0.0", exact: true })).toBeVisible();
  await noKoreanUI(page);
  await page.getByRole("tab", { name: "Edit", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Authorable Python code", exact: true })).toContainText("# unsaved edit");
});

test("Skill query inspection localizes statuses and dialogs while retaining recorded evidence", async ({ page }) => {
  await setup(page);
  const result = { status: "needs_input", primary: null, artifacts: [], warnings: [], validation: [], provenance: { method: "method://analysis/drilldown@2.0.0", semantic_refs: [], queries: [] } };
  await page.route("**/api/runs/locale-run", route => route.fulfill({ json: {
    id: "locale-run", origin: "mcp", status: "open", created_at: stamp, caller: { subject: "alice", groups: [] }, shared_with: [], validation: [],
    plan: { question: "Inspect revenue groups", scope: {} }, steps: [{ step: { id: "groups", method: skill.name, bindings: {}, params: {} }, method: result.provenance.method, started_at: stamp, result,
      skill: { guide, status: "refused", queries: [{ id: "wrong-period", purpose: "Inspect the rejected query", status: "failed", started_at: stamp, spec: { marker: "recorded-evidence" }, error: { code: "INVALID_BINDING", message: "Query dates do not match the Run." } }] } }],
  } }));
  await page.goto(`${prefix}/runs/locale-run`);
  await page.getByRole("button", { name: "Inspect failed queries", exact: true }).click();
  await expect(page.getByRole("region", { name: "Query details" })).toContainText("Query failed");
  await page.getByRole("button", { name: "Original request", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Original query request" })).toContainText("recorded-evidence");
  await page.keyboard.press("Escape");
  await language(page, "ko");
  await expect(page.getByRole("region", { name: "조회 상세" })).toContainText("조회 실패");
  await page.getByRole("button", { name: "요청 원문", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "조회 요청 원문" })).toContainText("recorded-evidence");
});
