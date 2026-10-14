import { expect, test } from "@playwright/test";

const manifest = { name: "example.group_metric", version: "1.0.0", kind: "query",
  description: "Retrieve the largest governed metric values by a grouping dimension.",
  interpretation: "association", execution: "semantic_pushdown", outputs: ["table"],
  roles: { metric: { kind: "measure", required: true, multiple: false, description: "" } },
  parameters: { limit: { type: "integer", required: false, default: 5, description: "" } } };

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale", "ko"));
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/methods/example.group_metric", route => route.fulfill({ json: manifest }));
});

test("requirement inspection uses the shared request and does not claim suitability", async ({ page }, info) => {
  let calls = 0;
  await page.route("**/api/methods:search", route => {
    calls++;
    expect(route.request().postDataJSON()).toEqual({ names: [manifest.name] });
    return route.fulfill({ json: { candidates: [{ manifest }], excluded: [], semantic_meaning_verified: false } });
  });
  await page.goto(`/methods/${manifest.name}`);
  expect(calls).toBe(0);
  await page.getByRole("button", { name: "현재 연결에서 실행 조건 확인" }).click();
  await expect(page.getByText("필요한 입력 유형과 라이브러리를 사용할 수 있습니다. 실행할 입력을 선택하세요.")).toBeVisible();
  await expect(page.getByText("질문 적합성, 조인, 기간, 분석 가정은 확인하지 않습니다. 나머지 검사는 실행할 때 수행합니다.")).toBeVisible();
  await expect(page.getByText("measure", { exact: true })).toBeVisible();
  expect(calls).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("method-requirements.png"), fullPage: true });
});

test("unavailable inputs and access failures remain visible", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/methods:search", route => {
    calls++;
    return calls === 1 ? route.fulfill({ json: { candidates: [], excluded: [{ name: manifest.name,
      reasons: [{ code: "SEMANTIC_INPUT_UNAVAILABLE", input: "metric" }] }] } })
      : route.fulfill({ status: 403, json: { error: { code: "PROVIDER_ACCESS_DENIED", message: "Access denied" } } });
  });
  await page.goto(`/methods/${manifest.name}`);
  await page.getByRole("button", { name: "현재 연결에서 실행 조건 확인" }).click();
  await expect(page.getByText("사용 가능한 입력 유형을 찾지 못함: metric")).toBeVisible();
  await page.getByRole("button", { name: "현재 연결에서 실행 조건 확인" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Access denied" })).toBeVisible();
});
