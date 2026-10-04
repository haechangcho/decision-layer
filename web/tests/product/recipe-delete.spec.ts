import { expect, test } from "@playwright/test";

const recipe = { name: "delete-test", description: "상품 부문별 수취액", version: "1.0.0", status: "published",
  mode: "pipeline", routing: { use_for: [], do_not_use_for: [] },
  semantic_scope: { primary_metric: "cube://journey/transaction/receipts", related_metrics: [], preferred_dimensions: [], required_filters: [] },
  steps: [], allowed_methods: [], validators: [], limits: { max_steps: 12, max_queries: 30 } };

test("delete requires confirmation, checks the latest version and updates both lists", async ({ page }, info) => {
  let removed = false;
  let deletes = 0;
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [], hierarchies: {} } }));
  await page.route("**/api/recipes", route => route.fulfill({ json: removed ? [] : [recipe] }));
  await page.route("**/api/recipes:drafts", route => route.fulfill({ json: removed ? [] : [{ ...recipe, status: "draft", version: "1.0.1" }] }));
  await page.route("**/api/recipes/delete-test/edit", route => route.fulfill({ json: { ...recipe, status: "draft", version: "1.0.1" } }));
  await page.route("**/api/recipes/delete-test?*", route => {
    expect(route.request().method()).toBe("DELETE");
    expect(new URL(route.request().url()).searchParams.get("base_version")).toBe("1.0.1");
    deletes++;
    if (deletes === 1) return route.fulfill({ status: 409, json: { error: { code: "RECIPE_VERSION_CONFLICT", message: "Recipe changed." } } });
    removed = true;
    return route.fulfill({ status: 204 });
  });
  await page.goto("/recipes");
  const trigger = page.getByRole("button", { name: "Recipe 삭제: 상품 부문별 수취액", exact: true }).first();
  await trigger.click();
  let dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("button", { name: "취소", exact: true })).toBeFocused();
  await expect(dialog).toContainText("기존 실행 기록과 분석 결과는 유지됩니다");
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  expect(deletes).toBe(0);
  await trigger.click();
  dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("button", { name: "Recipe 삭제", exact: true })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("recipe-delete.png"), fullPage: true });
  await dialog.getByRole("button", { name: "Recipe 삭제", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("Recipe changed");
  await dialog.getByRole("button", { name: "다시 불러오기" }).click();
  await expect(dialog.getByRole("button", { name: "Recipe 삭제", exact: true })).toBeEnabled();
  await dialog.getByRole("button", { name: "Recipe 삭제", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByRole("button", { name: /Recipe 삭제:/ })).toHaveCount(0);
  await expect(page.getByRole("status")).toContainText("삭제됨");
});
