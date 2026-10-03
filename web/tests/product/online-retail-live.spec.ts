import { expect, test } from "@playwright/test";

const runId = process.env.RETAIL_RUN_ID;
test.skip(!runId, "Set RETAIL_RUN_ID after the Online Retail MCP live test");

test("public-data MCP Run shows its question, methods, chart, and Recipe review", async ({ page }, info) => {
  await page.goto(`/runs/${runId}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("2011년 3월 영국 외 판매액은 얼마이고 어느 국가가 가장 큰가요?");
  await expect(page.getByRole("region", { name: "분석 답변" })).toContainText("131,409.08 GBP");
  const graph = page.getByRole("region", { name: "실행 그래프" });
  await expect(graph.getByText("영국 외 3월 판매액 확인")).toBeVisible();
  await expect(graph.getByText("가장 큰 국가 확인")).toBeVisible();
  await expect(page.getByRole("img", { name: /그룹별 지표 값 그래프/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Recipe 초안 검토" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("public-data-run.png"), fullPage: true });
});
