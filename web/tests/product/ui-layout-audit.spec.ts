import { test, expect } from "@playwright/test";

const metric = "cube://poc/transactions/receipts";
const date = "cube://poc/transactions/date";
const object = { ref: metric, kind: "measure", data_type: "number", public: true, title: "거래 수취액", description: "선택한 기간에 발생한 거래의 수취액 합계", metric_kind: "additive" };
const method = { name: "analysis.metric_lookup", version: "2.2.0", implementation: "skill", agent_executable: true, kind: "query", description: "지표와 기간을 선택해 조회합니다.", roles: {}, parameters: {}, outputs: ["table"], execution: "agent_guided", interpretation: "association" };
const recipe = { name: "layout-audit", version: "1.0.0", description: "기간별 거래 수취액 확인", status: "published", mode: "pipeline", routing: { use_for: [], do_not_use_for: [] }, semantic_scope: { primary_metric: metric, related_metrics: [], preferred_dimensions: [], required_filters: [] }, steps: [{ id: "read", method: method.name, bindings: { metric }, params: {}, purpose: "선택한 기간의 수취액 확인" }], allowed_methods: [], validators: [], limits: { max_steps: 12, max_queries: 30 } };
const result = { status: "success", primary: { type: "table", title: "조회 결과", data: [{ receipts: 42 }] }, artifacts: [], validation: [], warnings: [], provenance: { semantic_refs: [metric], queries: [{ provider: "cube", instance: "poc", native_query: { measures: ["transactions.receipts"], _view: "transactions" }, compiled_sql: `SELECT sum(receipts) FROM transaction_data WHERE ${"transaction_date >= $1 AND ".repeat(40)}transaction_date <= $2`, rows: 1, elapsed_ms: 12 }] } };
const run = { id: "layout-audit", origin: "mcp", status: "completed", created_at: "2026-11-03T00:00:00Z", plan: { question: "Decision Layer MCP로 전체 기간의 수취액 합계를 조회하고 Run 링크를 알려줘.", scope: { date_range: ["2000-01-01", "2000-12-31"], time_dimension: date } }, caller: { subject: "joe", groups: [] }, shared_with: [], validation: [], steps: [{ step: recipe.steps[0], result, skill: { guide: { name: method.name, version: method.version, markdown: "기록된 지표를 조회합니다.", sha256: "a".repeat(64), enforcement: "advisory", suggested_methods: [] }, status: "completed", queries: [{ id: "read", purpose: "거래 수취액 확인", status: "success", started_at: "2026-11-03T00:00:00Z", spec: {}, result }] } }] };
const source = { deployment_mode: "shared", provider: "cube", instance: "poc", api_url: "http://heartcube:4000/cubejs-api/v1", auth_method: "token", service_groups: [], environment_overrides: {}, editable: false, admin_configured: false, admin_required: true };

async function contained(page: import("@playwright/test").Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  const badButtons = await page.locator("main button:visible, main input:visible, main select:visible").evaluateAll(elements => elements.filter(element => {
    const rect = element.getBoundingClientRect();
    // Code/table/graph scroll areas may scroll horizontally within their own box.
    return !element.closest(".react-flow") && (rect.left < -1 || rect.right > innerWidth + 1);
  }).map(element => element.getAttribute("aria-label") || element.textContent));
  expect(badButtons).toEqual([]);
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale", "ko"));
  await page.route("**/api/**", route => {
    const path = new URL(route.request().url()).pathname.replace(/^\/api/, "");
    const data = path === "/sources/current" ? source : path === "/me" ? { subject: "joe", name: "joe", authentication: "login", role: "admin" }
      : path === "/project" ? { name: "customer_poc", path: "/project/customer_poc" }
      : path === "/semantic/catalog" ? { provider: "cube", instance: "poc", objects: [object, { ref: date, title: "거래일", kind: "time_dimension", data_type: "time", public: true }], hierarchies: {} }
      : path === "/sources/current/readiness" ? { metrics: [{ metric: object, checks: { time: { status: "ready", dimensions: [date] }, decomposition: { status: "not_applicable" } } }] }
      : path === "/methods" ? [method] : path === `/methods/${method.name}` ? method
      : path.endsWith("/source") ? { version: method.version, implementation: "skill", content: "조회 지침", permissions: { edit: false, publish: false }, history: [] }
      : path === "/recipes" ? [recipe] : path === "/recipes:drafts" ? [] : path.startsWith("/recipes/layout-audit") ? recipe
      : path === "/runs" ? [run] : path === "/runs/layout-audit" ? run : null;
    return data === null ? route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "Audit fixture not found" } } }) : route.fulfill({ json: data });
  });
});

test("main pages and details keep usable controls inside the viewport", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  for (const path of ["/recipes", "/catalog", "/methods", `/methods/${method.name}`, "/runs", "/runs/layout-audit", "/sources", "/recipes/layout-audit"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expect(page.getByLabel("joe 계정으로 로그인됨")).toBeVisible();
    await contained(page);
    if (path === "/runs" && page.viewportSize()!.width <= 1000) {
      const row = page.getByRole("link", { name: new RegExp(run.plan.question.replaceAll(".", "\\.")) });
      const fraction = await row.evaluate(element => element.querySelector("strong")!.getBoundingClientRect().width / element.getBoundingClientRect().width);
      expect(fraction).toBeGreaterThan(0.7);
    }
    await page.screenshot({ path: info.outputPath(`layout-${path.replaceAll("/", "-")}.png`), fullPage: true });
  }
  expect(errors).toEqual([]);
});

test("query and SQL headings share padded alignment and code scrolls locally", async ({ page }, info) => {
  await page.goto("/runs/layout-audit");
  await page.getByRole("tab", { name: "쿼리 1개" }).click();
  const evidence = page.getByRole("region", { name: "기록된 조회 근거" });
  for (const title of ["Cube 쿼리", "컴파일 SQL"]) {
    const block = evidence.getByRole("region", { name: title, exact: true });
    const geometry = await block.evaluate(element => {
      const block = element.getBoundingClientRect();
      const card = element.parentElement!.getBoundingClientRect();
      const heading = element.querySelector("h4")!.getBoundingClientRect();
      const code = element.querySelector("pre")!.getBoundingClientRect();
      return { inset: heading.left - card.left, alignment: Math.abs(heading.left - code.left), contained: code.right <= block.right };
    });
    expect(geometry.inset).toBeGreaterThanOrEqual(16);
    expect(geometry.alignment).toBeLessThan(1);
    expect(geometry.contained).toBe(true);
  }
  const sql = evidence.getByLabel("컴파일 SQL 1", { exact: true });
  expect(await sql.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true);
  await contained(page);
  await page.screenshot({ path: info.outputPath("query-evidence-insets.png"), fullPage: true });
});

test("query copy reports success and SQL copy failures provide recovery", async ({ page }) => {
  await page.goto("/runs/layout-audit");
  await page.getByRole("tab", { name: "쿼리 1개" }).click();
  await page.evaluate(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async (text: string) => { if (text.includes("_view")) throw new Error("Routing metadata leaked"); } } }));
  await page.getByRole("button", { name: "쿼리 1 복사" }).click();
  await expect(page.getByRole("status")).toHaveText("복사했습니다");
  await page.evaluate(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async () => { throw new Error("Clipboard unavailable"); } } }));
  await page.getByRole("button", { name: "SQL 1 복사" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "복사하지 못했습니다" })).toBeVisible();
  await expect(page.getByLabel("컴파일 SQL 1", { exact: true })).toBeVisible();
});

test("long account and project names do not displace navigation or dialog close", async ({ page }) => {
  const name = "verylongidentity".repeat(12);
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "joe", name, role: "admin", authentication: "login" } }));
  await page.route("**/api/project", route => route.fulfill({ json: { name, path: "/project/" + name } }));
  await page.goto("/sources");
  await expect(page.getByLabel(`${name} 계정으로 로그인됨`)).toBeVisible();
  await expect(page.getByLabel(`프로젝트 ${name}`)).toBeVisible();
  await contained(page);
  const widths = await page.locator(".app-topbar").evaluate(header => [...header.children].filter(child => child.getBoundingClientRect().width > 0).map(child => ({ left: child.getBoundingClientRect().left, right: child.getBoundingClientRect().right })));
  expect(widths.every((box, i) => i === 0 || box.left >= widths[i - 1].right - 1)).toBe(true);
});

test("compact catalog details have modal keyboard behavior and restore focus", async ({ page }) => {
  await page.goto("/catalog");
  const trigger = page.getByRole("button", { name: /거래 수취액/ });
  await trigger.click();
  if (page.viewportSize()!.width <= 1000) {
    const dialog = page.getByRole("dialog", { name: object.title, exact: true });
    await expect(dialog).toBeVisible();
    const close = dialog.getByRole("button", { name: "닫기", exact: true });
    await expect(close).toBeInViewport();
    await close.focus(); await page.keyboard.press("Tab");
    expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await expect(trigger).toBeFocused();
  } else {
    const detail = page.getByRole("complementary", { name: "지표 상세" });
    await expect(detail).toBeVisible();
    expect((await detail.boundingBox())!.y).toBeGreaterThanOrEqual(64);
  }
  // Closing the nested technical dialog must not close the parent inspector.
  if (page.viewportSize()!.width <= 1000) {
    await trigger.click();
    const outer = page.getByRole("dialog", { name: object.title, exact: true });
    await outer.getByRole("button", { name: "기술 정보 보기" }).click();
    await page.getByRole("dialog", { name: "지표 기술 정보" }).getByRole("button", { name: "닫기", exact: true }).click();
    await expect(outer).toBeVisible();
    await outer.getByRole("button", { name: "닫기", exact: true }).click();
  }
  await page.getByLabel("지표 검색").fill("없는지표");
  await expect(page.getByText("0개 지표", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "검색 초기화" })).toBeVisible();
  await contained(page);
});
