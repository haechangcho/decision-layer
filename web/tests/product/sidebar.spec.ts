import { test, expect } from "@playwright/test";

test("sidebar collapses, preserves navigation and remembers preference", async ({ page }, info) => {
  await page.route("**/api/sources/current", route => route.fulfill({ json: {
    provider: "cube", instance: "local", api_url: "http://cube:4000/cubejs-api/v1",
    auth_method: "none", service_groups: [], service_credentials_allowed: true,
    api_secret_configured: false, editable: true, environment_overrides: {},
  } }));
  await page.goto("/sources");
  const sidebar = page.locator("#app-sidebar");
  if (info.project.name === "mobile") {
    await expect(page.getByRole("button", { name: "Collapse sidebar" })).toBeHidden();
    await expect(sidebar.getByRole("link", { name: "Source settings" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    return;
  }
  const expanded = await sidebar.boundingBox();
  const collapse = page.getByRole("button", { name: "Collapse sidebar" });
  const collapseBox = await collapse.boundingBox();
  const brandBox = await page.getByRole("link", { name: "Decision Layer home" }).boundingBox();
  expect(collapseBox!.x).toBeGreaterThan(brandBox!.x + brandBox!.width);
  expect(collapseBox!.x + collapseBox!.width).toBeLessThanOrEqual(expanded!.x + expanded!.width);
  await page.screenshot({ path: info.outputPath("sidebar-expanded.png"), fullPage: true });
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await expect(sidebar).toHaveClass(/app-sidebar-collapsed/);
  expect((await sidebar.boundingBox())!.width).toBeLessThan(expanded!.width);
  await expect(sidebar.getByRole("link", { name: "Source settings" })).toBeVisible();
  await expect(sidebar.getByRole("link", { name: "Recipes", exact: true })).toHaveAttribute("title", "Recipes");
  await sidebar.getByRole("link", { name: "Methods", exact: true }).click();
  await expect(page).toHaveURL(/\/methods$/);
  await page.reload();
  await expect(sidebar).toHaveClass(/app-sidebar-collapsed/);
  await page.screenshot({ path: info.outputPath("sidebar-collapsed.png"), fullPage: true });
  const toggle = page.getByRole("button", { name: "Expand sidebar" });
  const toggleBox = await toggle.boundingBox();
  expect(toggleBox!.x + toggleBox!.width).toBeLessThanOrEqual((await sidebar.boundingBox())!.width);
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(sidebar).not.toHaveClass(/app-sidebar-collapsed/);
  await expect(sidebar.locator(".app-nav-label-full").first()).toBeVisible();
});
