import { test, expect } from "@playwright/test";

test("missing entity metadata does not imply matching is unavailable", async ({ page }) => {
  const metric = { ref: "dbt://production/metrics/receipts", title: "수취액", kind: "measure", data_type: "number", metric_kind: "additive", public: true };
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [metric] } }));
  await page.route("**/api/sources/current/readiness", route => route.fulfill({ json: { metrics: [{ metric, checks: {
    time: { status: "ready", dimensions: ["dbt://production/dimensions/metric_time"], impact: null },
    decomposition: { status: "not_applicable", parts: [], impact: null },
    entity_key: { status: "missing", ref: null, impact: "Matched/entity-level comparisons may be unavailable." },
  } }] } }));
  await page.goto("/catalog");
  await expect(page.getByRole("group", { name: "준비 상태 필터" })).toHaveCount(0);
  await expect(page.getByText("분석 준비됨", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: /수취액/ }).click();
  await expect(page.getByText("Matched/entity-level comparisons may be unavailable.")).toHaveCount(0);
  await expect(page.getByText("기본 키", { exact: true })).toHaveCount(0);
  await expect(page.getByText("일부 제한", { exact: true })).toHaveCount(0);
  await expect(page.getByText("모델에서 확인한 정보")).toBeVisible();
  await expect(page.getByText("등록됨", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Recipe 만들기" })).toBeVisible();
});

for (const status of ["ready", "unknown", "missing"] as const) {
  test(`catalog reports metadata, not execution readiness: ${status}`, async ({ page }) => {
    const metric = { ref: "cube://local/orders/rate", title: "반품률", kind: "measure", metric_kind: "ratio", public: true };
    await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [metric] } }));
    await page.route("**/api/sources/current/readiness", route => route.fulfill({ json: { metrics: [{ metric, checks: {
      time: { status, dimensions: [], impact: "Time-series analysis is unavailable." },
      decomposition: { status: status === "ready" ? "ready" : "missing", parts: [], impact: "This ratio cannot be decomposed." },
      entity_key: { status: "missing", ref: null, impact: null },
    } }] } }));
    await page.goto("/catalog");
    await page.getByRole("button", { name: /반품률/ }).click();
    await expect(page.getByText("모델에서 확인한 정보")).toBeVisible();
    await expect(page.getByText(status === "ready" ? "등록됨" : "확인되지 않음", { exact: true })).toHaveCount(2);
    await expect(page.getByText("Time-series analysis is unavailable.")).toHaveCount(0);
    await expect(page.getByText("분석 준비됨", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Recipe 만들기" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
