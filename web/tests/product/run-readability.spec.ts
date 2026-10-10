import { expect, test } from "@playwright/test";

const metric = "cube://sample/orders/revenue";
const rows = Array.from({ length: 25 }, (_, i) => ({ period: `2001-07-${String(i + 1).padStart(2, "0")}`, [metric]: i * 100 }));
const result = { status: "success", primary: { type: "time_series", data: { metric, rows, analysis_period: { date_range: ["2001-07-01", "2001-07-25"], source: "method_parameters" } } }, artifacts: [],
  warnings: ["Moving together does not prove association."], validation: [], provenance: { method: "method://query/trend@1.0.0", semantic_refs: [metric], queries: [], runtime: {} } };
const run = { id: "readability", origin: "mcp", plan: { question: "매출 추이", scope: {} },
  steps: [{ step: { id: "trend", method: "query.trend", bindings: { metric }, params: {}, purpose: "추이 확인" }, result }],
  status: "completed", validation: [], caller: { subject: "alice", groups: [] }, shared_with: [], created_at: "2026-10-07T00:00:00Z" };

test.beforeEach(async ({ page }) => {
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [] }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [{ ref: metric, title: "매출", kind: "measure", description: "주문 금액 합계" }], hierarchies: {} } }));
});

test("question, conclusion and findings have distinct readable regions", async ({ page }, info) => {
  await page.route("**/api/runs/readability", route => route.fulfill({ json: { ...run,
    conclusion: { source: "caller", answer: "선택한 기간의 매출이 증가했습니다.",
      findings: [{ text: "마지막 관측일의 매출은 2,400입니다.", step_indices: [0] }],
      limitations: ["매출 증가의 원인은 이 분석에서 확인하지 않았습니다."] },
  } }));
  await page.goto("/runs/readability");
  const header = page.locator('header[aria-label="질문과 실행 정보"]');
  await expect(header.getByRole("heading", { level: 1 })).toContainText("매출 추이");
  const registration = page.getByRole("region", { name: "Recipe 등록", exact: true });
  await expect(registration).toBeVisible();
  const borders = await registration.evaluate(element => {
    const style = getComputedStyle(element);
    return [style.borderTopWidth, style.borderBottomWidth];
  });
  expect(borders).toEqual(["0px", "0px"]);
  const answer = page.getByRole("region", { name: "분석 답변" });
  await expect(answer.getByRole("heading", { name: "분석 결론", exact: true })).toBeVisible();
  await expect(answer.getByRole("heading", { name: "주요 발견", exact: true })).toBeVisible();
  await expect(answer.getByRole("button", { name: "1단계 · 시간에 따른 변화" })).toBeVisible();
  const spacing = await page.evaluate(() => {
    const header = document.querySelector('header[aria-label="질문과 실행 정보"]')!.getBoundingClientRect();
    const answer = document.querySelector('section[aria-label="분석 답변"]')!.getBoundingClientRect();
    return answer.top - header.bottom;
  });
  expect(spacing).toBeGreaterThanOrEqual(24);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("answer-hierarchy.png"), fullPage: true });
});

test("result table paginates and preserves interpretation notes outside the result", async ({ page }, info) => {
  await page.route("**/api/runs/readability", route => route.fulfill({ json: run }));
  await page.goto("/runs/readability");
  await expect(page.getByText("분석 완료", { exact: true })).toHaveCount(0);
  await expect(page.getByText(result.warnings[0])).toHaveCount(0);
  const table = page.getByRole("region", { name: "결과 데이터 표" });
  await expect(table.getByRole("row")).toHaveCount(13);
  await page.getByRole("button", { name: "다음 행", exact: true }).click();
  await expect(page.getByText("13–24 / 25행")).toBeVisible();
  await expect(table.getByRole("cell", { name: "2001-07-13", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("result-table.png"), fullPage: true });
  await page.getByRole("tab", { name: "실행 검증" }).click();
  await expect(page.getByText(result.warnings[0])).toBeVisible();
  await page.getByRole("tab", { name: "사용한 설정" }).click();
  await expect(page.getByRole("heading", { name: "실제 조회 기간" })).toBeVisible();
  await expect(page.getByText("2001-07-01 ~ 2001-07-25")).toBeVisible();
  await expect(page.getByText("단계 설정", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "출처", exact: true }).click();
  await expect(page.getByRole("heading", { name: "사용한 분석 방법" })).toBeVisible();
  await expect(page.getByText("주문 금액 합계")).toBeVisible();
  await expect(page.getByText(metric, { exact: true })).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("sources.png"), fullPage: true });
});

test("list headings and values share column positions", async ({ page }, info) => {
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: [run] }));
  await page.goto("/runs");
  await expect(page.getByText("완료", { exact: true }).last()).toBeVisible();
  if (info.project.name === "desktop") {
    const positions = await page.evaluate(() => {
      const header = document.querySelector('[class*="runColumns"]');
      const row = document.querySelector('a[href="/runs/readability"]');
      return [1, 2].map(i => Math.abs(header!.children[i].getBoundingClientRect().x - row!.children[i].getBoundingClientRect().x));
    });
    expect(positions.every(offset => offset < 2)).toBe(true);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
