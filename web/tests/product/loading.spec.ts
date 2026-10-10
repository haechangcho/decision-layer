import { expect, test } from "@playwright/test";

for (const path of ["/recipes", "/runs", "/methods", "/recipes/loading-test", "/runs/loading-test", "/methods/loading-test"]) {
  test(`shared SVG loading state: ${path}`, async ({ page }, info) => {
    let release!: () => void;
    const pending = new Promise<void>(resolve => { release = resolve; });
    await page.route("**/api/**", async route => {
      const url = new URL(route.request().url());
      if (url.pathname === `/api${path}`) {
        await pending;
        await route.fulfill(path.split("/").length === 2
          ? { json: [] }
          : { status: 404, json: { error: { code: "NOT_FOUND", message: "Test item not found" } } });
      } else {
        await route.fulfill({ json: url.pathname.includes("catalog") ? { objects: [] } : url.pathname.includes("readiness") ? { metrics: [] } : [] });
      }
    });
    try {
      await page.goto(path);
      const loader = page.locator(".dl-loading-state");
      await expect(loader).toBeVisible();
      await expect(loader).toHaveAttribute("role", "status");
      await expect(loader.locator("svg rect")).toHaveCount(8);
      await expect(loader.locator("svg")).toHaveAttribute("aria-hidden", "true");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`${path.replaceAll("/", "-")}-loading.png`) });
      await page.emulateMedia({ reducedMotion: "reduce" });
      await expect(loader.locator("rect").first()).toHaveCSS("animation-name", "none");
      release();
      await expect(loader).toBeHidden();
    } finally {
      release();
    }
  });
}
