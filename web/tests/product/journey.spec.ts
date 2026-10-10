import { test, expect } from "@playwright/test";

const objects = [
  { ref: "cube://local/ecom_order/return_rate", title: "반품률", description: "전체 주문 중 반품된 주문 비율", kind: "measure", data_type: "number", metric_kind: "ratio", ratio_parts: ["cube://local/ecom_order/returned_orders", "cube://local/ecom_order/orders"], entity: "cube://local/ecom_order/order_id", public: true },
  { ref: "cube://local/ecom_order/revenue", title: "매출", description: "완료 주문의 총 결제 금액", kind: "measure", data_type: "number", metric_kind: "additive", entity: "cube://local/ecom_order/order_id", public: true },
  { ref: "cube://local/ecom_order/shipping_days", title: "배송 소요일", kind: "measure", data_type: "number", metric_kind: "average", entity: "cube://local/ecom_order/order_id", public: true },
  { ref: "cube://local/ecom_order/category", title: "상품 카테고리", kind: "dimension", data_type: "string", public: true },
  { ref: "cube://local/ecom_order/created_at", title: "주문일", kind: "time_dimension", data_type: "time", public: true },
];

const readiness = {
  provider: "cube", instance: "local", note: "Readiness follows Cube metadata.",
  metrics: objects.filter((object) => object.kind === "measure").map((metric) => ({
    metric,
    checks: {
      decomposition: { status: metric.metric_kind === "ratio" ? "ready" : "not_applicable", parts: metric.ratio_parts ?? [], impact: null },
      time: { status: metric.title === "배송 소요일" ? "missing" : "ready", dimensions: metric.title === "배송 소요일" ? [] : ["cube://local/ecom_order/created_at"], impact: metric.title === "배송 소요일" ? "시간 추이 분석을 사용할 수 없습니다." : null },
      entity_key: { status: "ready", ref: metric.entity, impact: null },
    },
  })),
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/semantic/catalog", (route) => route.fulfill({ json: { provider: "cube", instance: "local", objects, hierarchies: {}, discovered_at: new Date().toISOString() } }));
  await page.route("**/api/sources/current/readiness", (route) => route.fulfill({ json: readiness }));
  await page.route("**/api/methods/query.*", async (route) => {
    const name = new URL(route.request().url()).pathname.split("/").at(-1) ?? "query.trend";
    await route.fulfill({ json: { name, version: "1.0.0", kind: "query", description: "Metric analysis", roles: { metric: { kind: "measure", required: true, multiple: false, description: "Metric to analyze" } }, parameters: {}, execution: "semantic_pushdown", interpretation: "descriptive", outputs: ["time_series"] } });
  });
});

test("root opens Recipes and a catalog metric starts a prefilled Recipe", async ({ page }, info) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/recipes$/);
  await expect(page.getByRole("heading", { name: /Recipes|레시피/ })).toBeVisible();
  await page.goto("/catalog");
  await expect(page.getByRole("heading", { name: "지표 탐색" })).toBeVisible();
  await page.screenshot({ path: info.outputPath("catalog.png"), fullPage: true });
  await expect(page.getByRole("button", { name: /반품률/ })).toBeVisible();
  await page.getByLabel("지표 검색").fill("배송");
  await expect(page.getByRole("button", { name: /배송 소요일/ })).toBeVisible();
  await page.getByRole("button", { name: /배송 소요일/ }).click();
  await expect(page.getByText("확인되지 않음", { exact: true })).toBeVisible();
  if (info.project.name === "mobile") await page.getByRole("button", { name: "닫기", exact: true }).click();
  await page.getByLabel("지표 검색").fill("");
  await page.getByRole("button", { name: /반품률/ }).click();
  await expect(page.getByText(objects[0].ref, { exact: true })).not.toBeVisible();
  await page.getByText("기술 정보", { exact: true }).click();
  await expect(page.getByText(objects[0].ref, { exact: true })).toBeVisible();
  await expect(page.getByRole("list").getByText("분자 / 분모", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Recipe 만들기" }).click();
  await expect(page).toHaveURL(/\/recipes\/new\?method=query\.trend&metric=/);
  await expect(page.getByLabel("분석할 지표", { exact: true })).toHaveValue(objects[0].ref);
});

test("drafts are separate from the executable analysis library", async ({ page }) => {
  const draft = { name: "review-draft", version: "1.0.0", description: "반품 분석 초안", status: "draft",
    semantic_scope: { primary_metric: objects[0].ref, related_metrics: [], preferred_dimensions: [], required_filters: [] },
    routing: { use_for: [], do_not_use_for: [] }, mode: "pipeline", steps: [{ id: "trend", method: "query.trend", bindings: { metric: "$scope.primary_metric" }, params: {} }],
    allowed_methods: [], validators: [], limits: { max_steps: 12, max_queries: 30 } };
  await page.route("**/api/recipes", route => route.fulfill({ json: [] }));
  await page.route("**/api/recipes:drafts", route => route.fulfill({ json: [draft] }));
  await page.goto("/recipes");
  await expect(page.getByRole("region", { name: "작성 중인 초안" })).toContainText("반품 분석 초안");
  await expect(page.getByRole("region", { name: "Recipes" })).not.toContainText("반품 분석 초안");
  await page.getByRole("region", { name: "작성 중인 초안" }).getByRole("link", { name: /반품 분석 초안/ }).click();
  await expect(page).toHaveURL(/\/recipes\/review-draft\/edit$/);
});

test("catalog permission errors explain the next step", async ({ page }) => {
  await page.route("**/api/semantic/catalog", (route) => route.fulfill({ status: 401, json: { error: { code: "UNAUTHENTICATED", message: "A Cube user token is required." } } }));
  await page.goto("/catalog");
  await expect(page.getByRole("heading", { name: "카탈로그에 연결할 수 없습니다" })).toBeVisible();
  await expect(page.getByText("Cube 주소와 사용자 토큰을 확인한 다음 다시 시도해 주세요.")).toBeVisible();
  await page.getByRole("link", { name: "연결 설정 열기" }).click();
  await expect(page.getByRole("heading", { name: /Cube 연결|Cube connection/ })).toBeVisible();
});

test("workspace token is used by the catalog and kept for this browser session", async ({ page }) => {
  await page.route("**/api/sources/current", route => route.fulfill({ json: { auth_method: "token" } }));
  const authHeaders: string[] = [];
  await page.route("**/api/semantic/catalog", async (route) => {
    authHeaders.push(route.request().headers().authorization ?? "");
    await route.fulfill({ json: { provider: "cube", instance: "local", objects, hierarchies: {}, discovered_at: new Date().toISOString() } });
  });
  await page.goto("/catalog");
  await page.getByRole("button", { name: /Cube user token required/ }).click();
  await page.getByLabel("Cube user token").fill("cube-user-token");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("heading", { name: "지표 탐색" })).toBeVisible();
  await expect.poll(() => authHeaders).toContain("Bearer cube-user-token");
  await page.reload();
  await expect(page.getByRole("button", { name: /Using a token/ })).toBeVisible();
  await expect.poll(() => authHeaders.at(-1)).toBe("Bearer cube-user-token");
});

test("token-free local Cube does not ask for a user token", async ({ page }) => {
  await page.route("**/api/sources/current", route => route.fulfill({ json: { auth_method: "none" } }));
  await page.goto("/catalog");
  await expect(page.getByRole("button", { name: /Cube user token required/ })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Cube connection" })).toBeVisible();
});

test("legacy design route returns to the product entry and mobile has no overflow", async ({ page }) => {
  await page.goto("/design");
  await expect(page).toHaveURL(/\/recipes$/);
  await expect(page.getByRole("heading", { name: /Recipes|레시피/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("find a Recipe, run it with its recommended time dimension, and inspect evidence", async ({ page }) => {
  const recipe = {
    name: "revenue-review", version: "1.0.0", description: "매출 변화를 살펴보기", mode: "pipeline",
    routing: { use_for: ["매출 변화"], do_not_use_for: [] },
    semantic_scope: { primary_metric: objects[1].ref, related_metrics: [], preferred_dimensions: [], required_filters: [] },
    steps: [{ id: "trend", method: "query.trend", bindings: { metric: "$scope.primary_metric" }, params: {} }],
    allowed_methods: [], validators: [], limits: { max_steps: 4, max_queries: 10 },
  };
  await page.route("**/api/recipes/revenue-review", route => route.fulfill({ json: recipe }));
  await page.route("**/api/recipes", route => route.fulfill({ json: [recipe] }));
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "analyst" } }));
  let requestScope: Record<string, unknown> | undefined;
  await page.route("**/api/runs", route => {
    requestScope = route.request().postDataJSON().scope;
    return route.fulfill({ json: { run_id: "journey-run" } });
  });
  await page.route("**/api/runs/journey-run", route => route.fulfill({ json: {
    id: "journey-run", status: "completed", plan: { scope: requestScope ?? {} }, recipe_snapshot: recipe,
    caller: { subject: "analyst", groups: [] }, shared_with: [], created_at: new Date().toISOString(), validation: [],
    steps: [{ step: { id: "trend", method: "query.trend", bindings: { metric: objects[1].ref }, params: { granularity: "month" } },
      method: "method://query.trend@1.0.0", result: { status: "success", interpretation: "descriptive", warnings: [], validation: [],
        primary: { type: "table", title: "매출 추이", data: [{ month: "2026-09", revenue: 140 }] }, artifacts: [],
        provenance: { method: "method://query.trend@1.0.0", semantic_refs: [objects[1].ref], queries: [{ native_query: "SELECT revenue", rows: 1, elapsed_ms: 4 }] } },
      started_at: new Date().toISOString(), finished_at: new Date().toISOString() }],
  } }));

  await page.goto("/recipes");
  await page.getByRole("textbox", { name: /Search analyses|분석 절차 검색/ }).fill("매출");
  await page.getByRole("link", { name: /매출 변화를 살펴보기/ }).click();
  await expect(page.getByLabel("날짜 기준")).toHaveValue("cube://local/ecom_order/created_at");
  await expect(page.getByLabel("날짜 기준").locator("option")).toHaveCount(2);
  await page.getByRole("button", { name: "이 Recipe로 분석" }).click();
  await expect(page).toHaveURL(/\/runs\/journey-run$/);
  await expect(page.getByRole("region", { name: "실행 그래프" }).getByText("매출 추이")).toBeVisible();
  await page.getByRole("tab", { name: /쿼리/ }).click();
  await expect(page.getByText("SELECT revenue")).toBeVisible();
  expect(requestScope?.time_dimension).toBe("cube://local/ecom_order/created_at");
});

test("invalid dates and missing Cube permission show a recovery action", async ({ page }) => {
  const recipe = {
    name: "revenue-review", version: "1.0.0", description: "매출 변화를 살펴보기", mode: "pipeline",
    routing: { use_for: [], do_not_use_for: [] },
    semantic_scope: { primary_metric: objects[1].ref, related_metrics: [], preferred_dimensions: [], required_filters: [] },
    steps: [{ id: "trend", method: "query.trend", bindings: { metric: "$scope.primary_metric" }, params: {} }],
    allowed_methods: [], validators: [], limits: { max_steps: 4, max_queries: 10 },
  };
  await page.route("**/api/recipes/revenue-review", route => route.fulfill({ json: recipe }));
  await page.route("**/api/runs", route => route.fulfill({ status: 403, json: { error: { code: "FORBIDDEN", message: "Metric access denied." } } }));
  await page.goto("/recipes/revenue-review");
  await page.getByLabel("시작일").fill("2026-10-20");
  await page.getByLabel("종료일").fill("2026-10-01");
  await expect(page.getByText("종료일은 시작일보다 늦어야 합니다.")).toBeVisible();
  await expect(page.getByRole("button", { name: "이 Recipe로 분석" })).toBeDisabled();
  await page.getByLabel("종료일").fill("2026-10-31");
  await page.getByRole("button", { name: "이 Recipe로 분석" }).click();
  await expect(page.getByRole("alert").getByText("Metric access denied.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Cube 연결 확인" })).toBeVisible();
  await expect(page.getByRole("link", { name: "접근 가능한 지표 확인" })).toBeVisible();
});
