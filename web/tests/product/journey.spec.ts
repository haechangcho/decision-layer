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
      time: { status: metric.title === "배송 소요일" ? "missing" : "ready", dimensions: [], impact: metric.title === "배송 소요일" ? "시간 추이 분석을 사용할 수 없습니다." : null },
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

test("root is the real catalog and a metric opens a prefilled Method", async ({ page }, info) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "지표 탐색" })).toBeVisible();
  await page.screenshot({ path: info.outputPath("catalog.png"), fullPage: true });
  await expect(page.getByRole("button", { name: /반품률/ })).toBeVisible();
  await page.getByLabel("지표 검색").fill("배송");
  await expect(page.getByRole("button", { name: /배송 소요일/ })).toBeVisible();
  await page.getByRole("button", { name: "확인 필요 1" }).click();
  await expect(page.getByRole("button", { name: /배송 소요일/ })).toBeVisible();
  await page.getByRole("button", { name: /배송 소요일/ }).click();
  await expect(page.getByText("시간 추이 분석을 사용할 수 없습니다.")).toBeVisible();
  await page.getByLabel("지표 검색").fill("");
  await page.getByRole("button", { name: "전체 3" }).click();
  await page.getByRole("button", { name: /반품률/ }).click();
  await expect(page.getByText("분자 / 분모")).toBeVisible();
  await page.getByRole("link", { name: "Recipe 만들기" }).click();
  await expect(page).toHaveURL(/\/recipes\/new\?method=query\.trend&metric=/);
  await expect(page.getByText("공통 지표 · 반품률", { exact: true })).toBeVisible();
});

test("catalog permission errors explain the next step", async ({ page }) => {
  await page.route("**/api/semantic/catalog", (route) => route.fulfill({ status: 401, json: { error: { code: "UNAUTHENTICATED", message: "A Cube user token is required." } } }));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "카탈로그에 연결할 수 없습니다" })).toBeVisible();
  await expect(page.getByText("Cube 주소와 사용자 토큰을 확인한 다음 다시 시도해 주세요.")).toBeVisible();
  await page.getByRole("link", { name: "연결 설정 열기" }).click();
  await expect(page.getByRole("heading", { name: "Cube 연결" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "서버 관리자 확인" })).toBeVisible();
});

test("workspace token is used by the catalog and kept for this browser session", async ({ page }) => {
  const authHeaders: string[] = [];
  await page.route("**/api/semantic/catalog", async (route) => {
    authHeaders.push(route.request().headers().authorization ?? "");
    await route.fulfill({ json: { provider: "cube", instance: "local", objects, hierarchies: {}, discovered_at: new Date().toISOString() } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: /Cube user token required/ }).click();
  await page.getByLabel("Cube user token").fill("cube-user-token");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("heading", { name: "지표 탐색" })).toBeVisible();
  await expect.poll(() => authHeaders).toContain("Bearer cube-user-token");
  await page.reload();
  await expect(page.getByRole("button", { name: /Using a token/ })).toBeVisible();
  await expect.poll(() => authHeaders.at(-1)).toBe("Bearer cube-user-token");
});

test("legacy design route returns to the product entry and mobile has no overflow", async ({ page }) => {
  await page.goto("/design");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "지표 탐색" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
