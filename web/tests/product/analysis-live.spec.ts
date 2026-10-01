import { test, expect } from "@playwright/test";

test("a saved Recipe graph runs end to end on local hc-cube", async ({ page }, info) => {
  test.skip(process.env.LIVE_CUBE !== "1", "Requires local hc-cube integration");
  test.setTimeout(120000);
  await page.goto("/recipes/return-rate-drilldown");
  await expect(page.getByText("v1.0.0 · 저장됨")).toBeVisible();
  await expect(page.locator(".react-flow__node")).toHaveCount(3);
  await page.screenshot({ path: info.outputPath("live-recipe-graph.png"), fullPage: true });
  await page.getByRole("button", { name: "Recipe 실행" }).click();
  await page.getByLabel("시작일").fill("2026-07-01");
  await page.getByLabel("종료일").fill("2026-09-30");
  await page.getByRole("button", { name: "저장된 Recipe 실행" }).click();
  await expect(page).toHaveURL(/\/runs\//, { timeout: 110000 });
  await expect(page.getByRole("heading", { name: /return-rate-drilldown/ })).toBeVisible();
  await expect(page.getByText("완료", { exact: true }).first()).toBeVisible();
});
