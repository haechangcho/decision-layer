import { test, expect } from "@playwright/test";

const base = {
  provider: "cube", instance: "local", api_url: "http://cube:4000/cubejs-api/v1", auth_method: "api_secret",
  api_secret_configured: true, service_groups: ["ecommerce"], service_credentials_allowed: true,
  admin_configured: false, admin_required: false, editable: true, encryption_configured: false,
};

// 1. Connection fixed by environment variables: status only, no edit form, no admin key.
test("env-managed connection shows status and a test button only", async ({ page }, info) => {
  page.on("pageerror", error => console.error(error.message));
  const source = { ...base, editable: false,
    environment_overrides: { api_url: true, instance: true, auth_method: true, api_secret: true, service_groups: true } };
  await page.route("**/api/sources/current", route => route.fulfill({ json: source }));
  await page.route("**/api/sources/current:test", route => route.fulfill({
    json: { status: "connected", provider: "cube", instance: "local", measures: 17, dimensions: 27, time_dimensions: 7, objects: 51 } }));
  await page.route("**/api/sources/current/readiness", route => route.fulfill({ json: { metrics: [{ metric: {
    ref: "cube://local/dim_customer/count", title: "고객 수" }, checks: { decomposition: { status: "not_applicable" }, time: { status: "ready" }, entity_key: { status: "ready" } } }] } }));
  await page.goto("/sources");
  await expect(page.getByRole("heading", { name: "Semantic layer connection" })).toBeVisible();
  // the real URL is shown, with the env var that fixes it
  await expect(page.getByText("http://cube:4000/cubejs-api/v1")).toBeVisible();
  await expect(page.getByText("CUBE_API_URL")).toBeVisible();
  await expect(page.getByText("Managed by environment variables").first()).toBeVisible();
  // no editable inputs, no admin key prompt
  await expect(page.getByLabel("API URL", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Server administrator key")).toHaveCount(0);
  // the test button works
  await page.getByRole("button", { name: "Test connection" }).click();
  await expect(page.getByText(/Catalog access verified/)).toBeVisible();
  await expect(page.getByRole("link", { name: /Explore metrics/ })).toBeVisible();
  await page.getByRole("button", { name: "Check readiness" }).click();
  await expect(page.getByText("고객 수")).toBeVisible();
  await expect(page.getByText("cube://local/dim_customer/count")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("source-env.png"), fullPage: true });
});

// 2. Local install (no admin token, nothing env-fixed): edit a token connection without a key.
test("local install edits a token connection without an admin key", async ({ page }) => {
  page.on("pageerror", error => console.error(error.message));
  let saved: Record<string, unknown> | null = null;
  const source = { ...base, auth_method: "token", api_secret_configured: false, environment_overrides: {} };
  await page.route("**/api/sources/current", async route => {
    if (route.request().method() === "PUT") { saved = route.request().postDataJSON(); return route.fulfill({ json: { ...source, api_url: saved!.api_url as string } }); }
    return route.fulfill({ json: source });
  });
  await page.route("**/api/sources/current:test", route => {
    expect(route.request().headers()["x-decision-layer-admin-key"]).toBeFalsy();     // no admin key on a local install
    expect(route.request().headers().authorization).toBe("Bearer my-token");
    return route.fulfill({ json: { status: "connected", provider: "cube", instance: "local", measures: 3, dimensions: 2, time_dimensions: 1, objects: 6 } });
  });
  await page.goto("/sources");
  await expect(page.getByText("Server administrator key")).toHaveCount(0);           // not asked on local
  await page.getByLabel("API URL", { exact: true }).fill("https://chosen.example/cubejs-api/v1");
  await page.getByPlaceholder("Enter without the Bearer prefix").fill("my-token");
  await expect(page.getByLabel("Instance")).toBeHidden();
  const inputBox = await page.getByLabel("API URL", { exact: true }).boundingBox();
  const testBox = await page.getByRole("button", { name: "Test connection" }).boundingBox();
  expect(testBox!.y).toBeGreaterThan(inputBox!.y);
  const save = page.getByRole("button", { name: "Save settings" });
  await expect(save).toBeDisabled();                                                 // must test first
  await page.getByRole("button", { name: "Test connection" }).click();
  await expect(save).toBeEnabled();
  await page.getByLabel("API URL", { exact: true }).fill("https://revised.example/cubejs-api/v1");
  await expect(save).toBeDisabled();
  await expect(page.getByText(/Catalog access verified/)).toHaveCount(0);
  await page.getByLabel("API URL", { exact: true }).fill("https://chosen.example/cubejs-api/v1");
  await page.getByRole("button", { name: "Test connection" }).click();
  await save.click();
  await expect(page.getByRole("status")).toContainText("Connection settings saved");
  expect(saved!.api_url).toBe("https://chosen.example/cubejs-api/v1");
});

test("a failed settings load offers a working retry", async ({ page }) => {
  let failed = true;
  await page.route("**/api/sources/current", route => failed
    ? route.fulfill({ status: 503, json: { detail: "Connection settings unavailable" } })
    : route.fulfill({ json: { ...base, environment_overrides: {} } }));
  await page.goto("/sources");
  await expect(page.getByRole("button", { name: "Retry", exact: true })).toBeVisible();
  failed = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByLabel("API URL", { exact: true })).toHaveValue(base.api_url);
});

// 3. Shared deployment (admin token configured): editing is gated by the admin key.
test("shared deployment requires the admin key before editing", async ({ page }) => {
  page.on("pageerror", error => console.error(error.message));
  const source = { ...base, auth_method: "token", api_secret_configured: false, admin_configured: true, admin_required: true, environment_overrides: {} };
  const adminKeys: (string | undefined)[] = [];
  await page.route("**/api/sources/current", async route => {
    adminKeys.push(route.request().headers()["x-decision-layer-admin-key"]);
    return route.fulfill({ json: source });
  });
  await page.goto("/sources");
  await expect(page.getByRole("heading", { name: "Server administrator key" })).toBeVisible();
  await expect(page.getByLabel("API URL", { exact: true })).toHaveCount(0);                       // locked until unlocked
  await page.getByLabel("Server administrator key").fill("secret-admin-key");
  await page.getByRole("button", { name: "Open settings" }).click();
  await expect(page.getByLabel("API URL", { exact: true })).toBeVisible();                        // now editable
  expect(adminKeys).toContain("secret-admin-key");                                    // the key was sent on reload
});
