import { expect, test } from "@playwright/test";

const base = { version: "1.0.0", kind: "query", roles: {}, parameters: {}, outputs: ["table"], description: "선택한 데이터로 분석합니다." };
const skill = { ...base, name: "analysis.metric_lookup", implementation: "skill", agent_executable: true };
const python = { ...base, name: "stats.regression_adjustment", implementation: "python" };
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("decision-layer.locale", "ko"));
  await page.route("**/api/sources/current", route => route.fulfill({ json: { auth_method: "none" } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [skill, python] }));
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: [] }));
});

test("methods separate guidance and calculation while retaining search", async ({ page }, info) => {
  await page.goto("/methods");
  await expect(page.getByRole("region", { name: "Skill 분석 방법" })).toContainText("지표 조회");
  await expect(page.getByRole("region", { name: "Python 분석 방법" })).toContainText("OLS 회귀분석");
  await page.getByRole("textbox", { name: "분석 방법 검색" }).fill("regression");
  await expect(page.getByRole("region", { name: "Skill 분석 방법" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Python 분석 방법" })).toBeVisible();
  await page.getByRole("button", { name: "검색 지우기" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("methods.png"), fullPage: true });
});

test("failed loading is not an empty successful library and retry recovers", async ({ page }) => {
  let fail = true;
  await page.route("**/api/methods", route => fail ? route.abort() : route.fulfill({ json: [skill] }));
  await page.goto("/methods");
  await expect(page.getByRole("alert").filter({ hasText: "분석 방법을 불러오지 못했습니다" })).toContainText("분석 방법을 불러오지 못했습니다");
  await expect(page.getByText("등록된 분석 방법이 없습니다")).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "분석 방법 검색" })).toHaveCount(0);
  fail = false;
  await page.getByRole("button", { name: "다시 시도" }).click();
  await expect(page.getByRole("region", { name: "Skill 분석 방법" })).toBeVisible();
});

test("evidence belongs to the exact executed version, not the latest registration", async ({ page }) => {
  await page.route(`**/api/methods/${python.name}`, route => route.fulfill({ json: python }));
  await page.route(`**/api/methods/${python.name}/source`, route => route.fulfill({ json: {
    version: "1.0.0", implementation: "python", permissions: { edit: false, publish: false }, code: null, history: [],
  } }));
  const run = (id: string, version: string, status: string) => ({
    id, plan: { question: id }, steps: [{ method: `method://${python.name.replaceAll(".", "/")}@${version}`, started_at: "2026-02-01T00:00:00Z",
      result: { status, validation: [], provenance: { queries: [] } } }],
  });
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: [run("older-success", "0.9.0", "success"), run("current-refused", "1.0.0", "refused")] }));
  await page.goto(`/methods/${python.name}`);
  await page.getByRole("tab", { name: "실행 기록", exact: true }).click();
  const evidence = page.getByRole("region", { name: "이 버전의 실행 기록" });
  await expect(evidence).toContainText("검사로 중단");
  await expect(evidence).not.toContainText("실행 성공");
  await expect(evidence.getByRole("link", { name: /current-refused/ })).toHaveAttribute("href", "/runs/current-refused");
  await expect(page.getByText("Python 작성 코드", { exact: true })).not.toBeVisible();
  await page.getByRole("tab", { name: "개요와 입력", exact: true }).click();
  await expect(page.getByRole("link", { name: "입력 선택하고 테스트" })).toHaveAttribute("href", `/recipes/new?method=${python.name}`);
});
