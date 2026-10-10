import { expect, test } from "@playwright/test";

test("model suggestions are read-only with copyable YAML and evidence", async ({ page }, info) => {
  const ref = "cube://sample/household/pre_spending";
  const requirement = { description: "이전 구매금액 구간", kind: "dimension", ref: null as string | null };
  const item = { id: "fix", goal_id: "compare", reason: "기존 구매 성향을 맞출 정보가 필요합니다.", evidence: "현재 카탈로그의 가구 차원을 확인했습니다.",
    proposal: "캠페인 이전 구매금액 구간을 모델에 추가해 주세요.", requirements: [requirement], revision: 0, status: "proposed", checks: [] as Record<string, unknown>[], events: [] as Record<string, unknown>[] };
  const run = { id: "gap", origin: "mcp", plan: { question: "캠페인 효과를 이전 구매 성향을 맞춰 비교해줘", scope: { date_range: ["2001-01-01", "2001-06-30"] } },
    goals: [{ id: "compare", description: "이전 구매 성향을 맞춰 비교", semantic_refs: [], required_capabilities: [] }], remediations: [item],
    steps: [], status: "completed", validation: [], shared_with: [], caller: { subject: "alice", groups: [] }, created_at: "2026-10-08T00:00:00Z",
    conclusion: { answer: "이전 구매 성향을 확인할 정보가 없어 비교하지 못했습니다.", findings: [], limitations: [], goal_outcomes: [{ goal_id: "compare", status: "unsupported", reason_code: "semantic_missing", reason: "이전 구매 성향 정보가 없습니다.", step_indices: [] }] } };
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [] }));
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [{ ref, title: "이전 구매금액 구간", kind: "dimension", data_type: "string", public: true }] } }));
  await page.route("**/api/runs/gap", route => route.fulfill({ json: run }));
  await page.goto("/runs/gap");
  await page.getByRole("combobox", { name: "language" }).selectOption("ko");
  const section = page.getByRole("region", { name: "데이터 모델 보완" });
  await expect(section.getByText("검토 필요", { exact: true })).toHaveCount(0);
  await expect(section.getByText("수정할 내용", { exact: true })).toBeVisible();
  const frame = await section.getByRole("article").evaluate(element => {
    const style = getComputedStyle(element);
    const header = getComputedStyle(element.querySelector("header")!);
    return { border: style.borderTopWidth, padding: parseFloat(style.paddingLeft), surface: style.backgroundColor, header: header.backgroundColor };
  });
  expect(frame.border).toBe("1px");
  expect(frame.padding).toBeGreaterThanOrEqual(18);
  expect(frame.header).not.toBe(frame.surface);
  await expect(section.getByRole("heading", { name: "YAML 작성 예시 Cube", exact: true })).toBeVisible();
  await expect(section.locator("pre")).toContainText("<source_column_or_expression>");
  await page.evaluate(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async () => {} } }));
  await section.getByRole("button", { name: "YAML 복사", exact: true }).click();
  await expect(section.getByText("복사했습니다", { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath("model-improvement.png"), fullPage: true });
  await expect(section.getByText("현재 카탈로그의 가구 차원을 확인했습니다.")).not.toBeVisible();
  await section.getByRole("button", { name: "근거 보기", exact: true }).click();
  await expect(section.getByText("현재 카탈로그의 가구 차원을 확인했습니다.")).toBeVisible();
  await expect(section.getByRole("button", { name: "제안 검토" })).toHaveCount(0);
  await expect(section.getByRole("button", { name: "다시 분석 시작" })).toHaveCount(0);
  await expect(section.getByRole("button", { name: "모델 다시 확인" })).toHaveCount(0);
  await expect(section.getByRole("combobox")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("semantic-review.png"), fullPage: true });
});
