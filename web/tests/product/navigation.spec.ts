import { test, expect } from "@playwright/test";

test("source settings stays reachable across pages and while scrolling", async ({ page }) => {
  await page.route("**/api/**", route => route.fulfill({ status: 503, json: {
    error: { code: "SOURCE_UNAVAILABLE", message: "Source unavailable for navigation test" },
  } }));
  for (const path of ["/", "/catalog", "/methods", "/methods/query.drilldown", "/recipes", "/recipes/new", "/runs", "/runs/missing", "/sources"]) {
    await page.goto(path);
    const settings = page.locator(".app-sidebar").getByRole("link", { name: /Source settings|연결 설정/, exact: true });
    await expect(settings).toBeInViewport();
    await page.locator("main").evaluate(element => { element.style.minHeight = "2400px"; });
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await expect(settings).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await settings.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/sources$/);
  }
});
