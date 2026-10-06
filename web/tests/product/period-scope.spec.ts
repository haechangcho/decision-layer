import { expect, test } from "@playwright/test";

test("a waiting Run asks once and continues with the same id and chosen dates", async ({ page }, info) => {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale", "ko"));
  let run: Record<string, unknown> = {
    id: "period-waiting", origin: "mcp", status: "open", steps: [], caller: { subject: "alice", groups: [] }, shared_with: [], validation: [],
    created_at: "2026-10-01T10:00:00Z", plan: { question: "상품 부문별 매출을 분석해줘", scope: { period: { mode: "unresolved" } } },
    needs_input: { field: "period", reason_code: "PERIOD_UNRESOLVED", question: "Choose an analysis period.", allow_all: false, max_period_days: 366 }, scope_revision: 2,
  };
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [] }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [], hierarchies: {} } }));
  await page.route("**/api/runs/period-waiting", route => route.fulfill({ json: run }));
  let submission: Record<string, unknown> | undefined;
  await page.route("**/api/runs/period-waiting/scope", route => {
    submission = route.request().postDataJSON();
    expect(route.request().method()).toBe("PUT");
    run = { ...run, needs_input: null, scope_revision: 3, plan: { question: "상품 부문별 매출을 분석해줘", scope: {
      date_range: ["2026-07-01", "2026-09-30"], period: { mode: "range" } } }, scope_resolution: { source: "caller", source_trust: "caller_reported" } };
    return route.fulfill({ json: run });
  });
  await page.goto("/runs/period-waiting");
  await expect(page.getByRole("heading", { name: "분석 기간을 정해 주세요" })).toBeVisible();
  await expect(page.getByLabel("전체 기간", { exact: true })).toHaveCount(0);
  await page.getByLabel("시작일", { exact: true }).fill("2026-07-01");
  await page.getByLabel("종료일", { exact: true }).fill("2026-09-30");
  await page.screenshot({ path: info.outputPath("period-confirmation.png"), fullPage: true });
  await page.getByRole("button", { name: "이 기간으로 계속" }).click();
  await expect(page.getByRole("heading", { name: "분석 기간을 정해 주세요" })).toHaveCount(0);
  await expect(page).toHaveURL(/\/runs\/period-waiting$/);
  expect(submission).toEqual({ base_revision: 2, scope: { period: { mode: "range", date_range: ["2026-07-01", "2026-09-30"] } } });
  await expect(page.locator('p[class*="runScope"]')).toContainText("2026-07-01 ~ 2026-09-30");
});

test("old Run does not invent period-selection provenance", async ({ page }) => {
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "other" } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [] }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [], hierarchies: {} } }));
  await page.route("**/api/runs/old-period", route => route.fulfill({ json: {
    id: "old-period", plan: { scope: {} }, status: "completed", steps: [], caller: { subject: "alice", groups: [] }, shared_with: [], validation: [], created_at: "2026-10-01T10:00:00Z",
  } }));
  await page.goto("/runs/old-period");
  await expect(page.locator('p[class*="runScope"]')).toContainText("기간 선택 기록 없음");
  await expect(page.getByRole("heading", { name: "분석 기간을 정해 주세요" })).toHaveCount(0);
});
