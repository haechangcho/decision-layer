import { expect, test } from "@playwright/test";

const runId = process.env.CHINOOK_RUN_ID;
test.skip(!runId, "Set CHINOOK_RUN_ID after the Chinook MCP live test");

test("multi-table MCP analysis shows a question, metric graph and reviewable Recipe draft", async ({ page }, info) => {
  await page.goto(`/runs/${runId}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("2023년 구매 항목 기준 판매액은 얼마이고, 어떤 장르가 가장 많이 기여했나요?");
  await expect(page.getByRole("region", { name: "분석 답변" })).toContainText("469.58");
  const graph = page.getByRole("region", { name: "실행 그래프" });
  await expect(graph.getByText("2023년 전체 판매액 확인")).toBeVisible();
  await expect(graph.getByText("판매액이 가장 큰 장르 확인")).toBeVisible();
  await expect(page.getByRole("img", { name: /그룹별 지표 값 그래프/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Recipe 초안 검토" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("chinook-run.png"), fullPage: true });
  await page.getByRole("button", { name: "Recipe 초안 검토" }).click();
  await expect(graph.getByRole("checkbox", { name: "1단계 초안에 포함" })).toBeChecked();
  await expect(graph.getByRole("checkbox", { name: "2단계 초안에 포함" })).toBeChecked();
  await page.getByRole("link", { name: "선택한 2단계 검토" }).click();
  await expect(page).toHaveURL(/\/recipes\/new\?from_run=/);
  await expect(page.getByRole("region", { name: "Recipe 그래프" })).toBeVisible();
  await expect(page.getByLabel("분석할 지표", { exact: true })).toHaveValue("cube://chinook/invoice_line/sales");
  await expect(page.getByRole("button", { name: "초안 저장", exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath("chinook-recipe-candidate.png"), fullPage: true });
});
