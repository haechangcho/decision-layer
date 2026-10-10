import { test, expect } from "@playwright/test";

test("only official semantic APIs are offered", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale", "ko"));
  const cube = { provider: "cube", instance: "local", api_url: "http://cube/cubejs-api/v1", auth_method: "none", service_groups: [], environment_overrides: {}, editable: true, admin_required: false, service_credentials_allowed: true };
  await page.route("**/api/sources/current", route => route.fulfill({ json: cube }));
  await page.goto("/sources");
  const select = page.getByRole("combobox", { name: "시맨틱 레이어", exact: true });
  await expect(select.locator("option")).toHaveText(["Cube", "dbt Semantic Layer"]);
});

test("official dbt connection takes an environment ID and bearer token on desktop and mobile", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale", "ko"));
  const cube = { provider: "cube", instance: "local", api_url: "http://cube/cubejs-api/v1", auth_method: "none", service_groups: [], environment_overrides: {}, editable: true, admin_required: false, service_credentials_allowed: true };
  const dbt = { ...cube, provider: "dbt", instance: "production", api_url: "https://semantic-layer.cloud.getdbt.com/api/graphql", auth_method: "token", environment_id: null };
  let current: Record<string, unknown> = cube;
  await page.route("**/api/sources/providers", route => route.fulfill({ json: [cube, dbt] }));
  await page.route("**/api/sources/current", async route => {
    if (route.request().method() === "PUT") current = { ...cube, ...route.request().postDataJSON() };
    await route.fulfill({ json: current });
  });
  await page.route("**/api/sources/current:test", async route => {
    expect(route.request().postDataJSON()).toMatchObject({ provider: "dbt", environment_id: 123, api_url: dbt.api_url, auth_method: "token" });
    expect(route.request().headers()["authorization"]).toBe("Bearer test-dbt-token");
    await route.fulfill({ json: { status: "connected", provider: "dbt", instance: "production", measures: 5, dimensions: 4, time_dimensions: 1 } });
  });
  await page.goto("/sources");
  await page.getByRole("combobox", { name: "시맨틱 레이어", exact: true }).selectOption("dbt");
  await expect(page.getByRole("button", { name: "연결 테스트", exact: true })).toBeDisabled();
  await page.getByRole("textbox", { name: "환경 ID", exact: true }).fill("123");
  await page.getByLabel("접근 토큰", { exact: true }).fill("test-dbt-token");
  await page.getByRole("button", { name: "연결 테스트", exact: true }).click();
  await page.getByRole("button", { name: "설정 저장", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("저장");
  expect(current).toMatchObject({ provider: "dbt", environment_id: 123 });
  expect(JSON.stringify(current)).not.toContain("test-dbt-token");
  await page.screenshot({ path: `test-results/dbt-source-${test.info().project.name}.png`, fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
