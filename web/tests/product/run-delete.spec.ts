import { expect, test } from "@playwright/test";

const run = { id: "delete-test", origin: "mcp", plan: { question: "어느 상품 부문의 수취액이 가장 큰가?", scope: {} },
  steps: [], caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [],
  created_at: "2026-10-01T10:00:00Z" };

test("a Run can be deleted from the list after confirmation", async ({ page }) => {
  let removed = false;
  let deletes = 0;
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: removed ? [] : [run] }));
  await page.route("**/api/runs/delete-test", route => {
    if (route.request().method() !== "DELETE") return route.fulfill({ json: run });
    deletes++;
    removed = true;
    return route.fulfill({ status: 204, body: "" });
  });
  await page.goto("/runs");
  await page.getByRole("button", { name: /실행 기록 삭제:/ }).click();
  const dialog = page.getByRole("dialog", { name: "실행 기록을 삭제할까요?" });
  await expect(dialog).toContainText(run.plan.question);
  await expect(dialog).toContainText("이미 등록한 Recipe는 유지됩니다");
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  expect(deletes).toBe(0);
  await page.getByRole("button", { name: /실행 기록 삭제:/ }).click();
  await dialog.getByRole("button", { name: "기록 삭제" }).click();
  await expect(page.getByRole("status")).toContainText("삭제했습니다");
  await expect(page.getByRole("button", { name: /실행 기록 삭제:/ })).toHaveCount(0);
  expect(deletes).toBe(1);
});

test("detail offers deletion to the owner and returns to the list", async ({ page }) => {
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [], hierarchies: {} } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [] }));
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: [] }));
  await page.route("**/api/runs/delete-test", route => route.request().method() === "DELETE"
    ? route.fulfill({ status: 204, body: "" }) : route.fulfill({ json: run }));
  await page.goto("/runs/delete-test");
  await page.getByRole("button", { name: /실행 기록 삭제:/ }).click();
  await page.getByRole("dialog", { name: "실행 기록을 삭제할까요?" }).getByRole("button", { name: "기록 삭제" }).click();
  await expect(page).toHaveURL(/\/runs$/);
});

test("an active Run cannot be deleted from the list", async ({ page }) => {
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: [{ ...run, status: "open",
    running: { kind: "step", method: "query.trend", started_at: "2026-10-01T10:00:00Z" } }] }));
  await page.goto("/runs");
  await expect(page.getByRole("button", { name: /실행 기록 삭제:/ })).toBeDisabled();
});
