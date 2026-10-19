import { test, expect } from "@playwright/test";

test("initial release offers Cube only and saves its connection", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale", "ko"));
  const cube = { provider: "cube", instance: "local", api_url: "http://cube/cubejs-api/v1", auth_method: "none", service_groups: [], environment_overrides: {}, editable: true, admin_configured: true, admin_required: false, service_credentials_allowed: true };
  let saved: Record<string, unknown> | undefined;
  await page.route("**/api/sources/current", async route => {
    if (route.request().method() === "PUT") saved = route.request().postDataJSON();
    await route.fulfill({ json: { ...cube, ...saved } });
  });
  await page.route("**/api/sources/current:test", async route => {
    expect(route.request().postDataJSON()).toMatchObject({ provider: "cube", api_url: cube.api_url });
    expect(route.request().postDataJSON()).not.toHaveProperty("environment_id");
    await route.fulfill({ json: { status: "connected", provider: "cube", instance: "local", measures: 5, dimensions: 4, time_dimensions: 1 } });
  });
  await page.goto("/sources");
  await expect(page.getByText("Cube", { exact: true })).toBeVisible();
  await expect(page.getByText(/dbt|BigQuery/)).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "환경 ID", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "연결 테스트", exact: true }).click();
  await page.getByRole("button", { name: "설정 저장", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("저장");
  expect(saved).toMatchObject({ provider: "cube" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
