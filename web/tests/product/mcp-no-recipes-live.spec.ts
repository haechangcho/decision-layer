import { expect, test } from "@playwright/test";

const runId = process.env.MCP_RUN_ID;
const api = process.env.MCP_EMPTY_API_URL;
test.skip(!runId || !api, "Set MCP_RUN_ID and MCP_EMPTY_API_URL after the isolated MCP live test");

test("a Recipe-free MCP question appears as one two-step Run graph", async ({ page }, info) => {
  if (!process.env.MCP_WEB_DIRECT) {
    await page.route("**/api/**", async (route) => {
      const requestUrl = new URL(route.request().url());
      const target = `${api}${requestUrl.pathname.replace(/^\/api/, "")}${requestUrl.search}`;
      const response = await route.fetch({ url: target });
      await route.fulfill({ response });
    });
  }

  await page.goto("/runs");
  await page.getByRole("combobox", { name: "실행 출처" }).selectOption("mcp");
  const runLink = page.locator(`a[href="/runs/${runId}"]`);
  await expect(runLink).toContainText("2026년 6월 지급결정금액은 얼마이며 지급유형별로 어디가 가장 큰가?");
  await runLink.click();

  await expect(page.getByRole("heading", { level: 1 })).toHaveText("2026년 6월 지급결정금액은 얼마이며 지급유형별로 어디가 가장 큰가?");
  await expect(page.getByText("지급결정금액 합계", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "실행 그래프" })).toBeVisible();
  await expect(page.getByText("지급일자 기준", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "분석 답변" }).getByText("데이터 최신성")).toBeVisible();

  const graph = page.getByRole("region", { name: "실행 그래프" });
  await expect(graph.getByRole("button", { name: "1단계 시간에 따른 변화 결과 보기" })).toBeVisible();
  await expect(graph.getByRole("button", { name: "2단계 항목별로 나눠 보기 결과 보기" })).toBeVisible();
  await expect(graph.getByText("지급결정금액 합계", { exact: true })).toHaveCount(1);
  await expect(graph.getByText("6월 지급결정금액 확인", { exact: true })).toBeVisible();
  await expect(graph.getByText("지급유형별 최대 금액 확인", { exact: true })).toBeVisible();
  await expect(graph.getByText("실행 순서", { exact: true })).toBeVisible();

  await graph.getByRole("button", { name: "1단계 시간에 따른 변화 결과 보기" }).click();
  await expect(page.locator('[class*="runStepDetail"]')).toContainText("860,160,000");
  await graph.getByRole("button", { name: "2단계 항목별로 나눠 보기 결과 보기" }).click();
  await expect(page.locator('[class*="runStepDetail"]')).toContainText("일당");
  await expect(page.getByRole("img", { name: /그룹별 지표 값 그래프/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Recipe 초안 검토" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("mcp-no-recipes-run.png"), fullPage: true });
});
