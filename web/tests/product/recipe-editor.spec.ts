import { test, expect } from "@playwright/test";

const metric = "cube://local/ecom_order/return_rate";
const manifest = { name: "query.trend", version: "1.0.0", description: "Compare a measure over time", kind: "query", roles: { metric: { kind: "measure", required: true, multiple: false } }, parameters: { granularity: { type: "enum", enum: ["day", "week", "month"], default: "month", required: false } }, outputs: ["time_series"] };

test("compose, review and save a versioned Recipe from Method nodes", async ({ page }, info) => {
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [{ ref: metric, kind: "measure", title: "반품률", public: true }], hierarchies: {} } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [manifest] }));
  await page.route("**/api/methods/query.trend", route => route.fulfill({ json: manifest }));
  let saved: any;
  await page.route("**/api/recipes/orders-rate", async route => {
    if (route.request().method() === "PUT") {
      saved = { ...route.request().postDataJSON().recipe };
      expect(route.request().headers()["x-recipe-admin-key"]).toBe("recipe-editor-key");
      await route.fulfill({ json: saved });
    } else await route.fulfill({ json: saved });
  });
  await page.goto(`/recipes/new?method=query.trend&metric=${encodeURIComponent(metric)}`);
  await expect(page.locator(".react-flow__node")).toContainText(["공통 분석 대상", "시간에 따른 변화"]);
  await page.getByRole("button", { name: "공통 설정" }).click();
  await page.getByLabel("Recipe 이름").fill("orders-rate");
  await page.getByLabel("설명").fill("반품률을 월별로 살펴봅니다.");
  await page.screenshot({ path: info.outputPath("recipe-editor.png"), fullPage: true });
  await page.getByRole("button", { name: "Recipe 저장" }).click();
  await page.getByLabel("Recipe 편집 키").fill("recipe-editor-key");
  await page.getByText("변경 내용").click();
  await expect(page.getByText("저장 전")).toBeVisible();
  await page.getByText("변경 내용").click();
  await page.getByRole("button", { name: "새 버전 저장" }).click();
  await expect.poll(() => saved?.version).toBe("1.0.0");
  expect(saved.name).toBe("orders-rate");
  expect(saved.steps[0]).toEqual({ id: "step_1", method: "query.trend", bindings: { metric: "$scope.primary_metric" }, params: {} });
  await expect(page.getByText("v1.0.0 · 저장됨")).toBeVisible();
  await expect(page.getByRole("button", { name: "Recipe 실행" })).toBeEnabled();
});
