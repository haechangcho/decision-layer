import { expect, test } from "@playwright/test";

const runId = process.env.JOURNEY_RUN_ID;
test.skip(!runId, "Set JOURNEY_RUN_ID after the Complete Journey MCP test");

test("retail exploration shows peer benchmarks and a reviewable draft", async ({ page }, info) => {
  await page.goto(`/runs/${runId}`);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("364 매장");
  const graph = page.getByRole("region", { name: "실행 그래프" });
  await expect(graph.getByText("수취액이 가장 큰 상품 부문 확인")).toBeVisible();
  await expect(graph.getByText("364 매장의 식료품 쿠폰 사용 비율을 다른 매장과 비교")).toBeVisible();
  await expect(page.getByRole("img", { name: /그룹별 지표 값 그래프/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("journey-run.png"), fullPage: true });
  await expect(page.getByRole("button", { name: "Recipe로 등록", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "편집해서 저장" }).click();
  await expect(page.getByRole("region", { name: "Recipe 그래프" })).toBeVisible();
  await expect(page.getByRole("button", { name: "초안 저장", exact: true })).toBeVisible();
  await page.getByRole("region", { name: "Recipe 그래프" }).getByText("동료·전체 집단과 비교", { exact: true }).click();
  await expect(page.getByLabel("대상 값 1", { exact: true })).toHaveValue("364");
  await expect(page.getByLabel("동료 값 1", { exact: true })).toHaveValue("GROCERY");
  await page.screenshot({ path: info.outputPath("journey-candidate.png"), fullPage: true });
});
