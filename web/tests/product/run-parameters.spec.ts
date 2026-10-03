import { expect, test } from "@playwright/test";

const step = {
  step: { id: "trend", method: "query.trend", bindings: { metric: "cube://local/insurance/payout" },
    params: { granularity: "month", vs_previous: false } },
  method: "method://query.trend@1.0.0",
  result: { status: "success", primary: null, artifacts: [], warnings: [], validation: [],
    provenance: { method: "method://query.trend@1.0.0", semantic_refs: [], queries: [] } },
  started_at: "2026-10-01T10:00:00Z", finished_at: "2026-10-01T10:00:01Z",
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [], hierarchies: {} } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [] }));
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/runs/provenance-test", route => route.fulfill({ json: {
    id: "provenance-test", plan: { question: "지급액이 왜 변했나?", scope: {} }, steps: [{ ...step,
      parameter_sources: { granularity: "method_default", vs_previous: "recipe" } }],
    caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [],
    created_at: "2026-10-01T10:00:00Z",
  } }));
  await page.route("**/api/runs/legacy-test", route => route.fulfill({ json: {
    id: "legacy-test", plan: { scope: {} }, steps: [step],
    caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [],
    created_at: "2026-10-01T10:00:00Z",
  } }));
});

test("Run shows applied values and their sources on demand", async ({ page }, info) => {
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [{ ref: "cube://local/insurance/payout", title: "지급액", kind: "measure" }], hierarchies: {} } }));
  await page.goto("/runs/provenance-test");
  await expect(page.getByText("지급액이 왜 변했나?", { exact: true }).last()).toBeVisible();
  await expect(page.getByText("지급액", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "실행 그래프" })).toBeVisible();
  await expect(page.getByLabel("공유할 사용자 ID")).not.toBeVisible();
  if (info.project.name === "mobile") {
    const graph = await page.getByRole("region", { name: "실행 그래프" }).boundingBox();
    const detail = await page.locator('[class*="runStepDetail"]').boundingBox();
    expect(graph && detail && graph.y < detail.y).toBe(true);
  }
  await expect(page.getByText("Method 기본값")).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Show 0 executed queries" })).toHaveCount(0);
  await expect(page.getByText("method://query.trend@1.0.0")).not.toBeVisible();
  await page.getByText("표와 실행 근거 보기").click();
  await page.locator("summary").filter({ hasText: /^실행 근거/ }).click();
  await expect(page.getByText("method://query.trend@1.0.0")).toBeVisible();
  await page.getByText("적용된 설정").click();
  await expect(page.getByText("시간 단위")).toBeVisible();
  await expect(page.getByText("월", { exact: true })).toBeVisible();
  await expect(page.getByText("Method 기본값")).toBeVisible();
  await expect(page.getByText("Recipe 설정")).toBeVisible();
  await page.getByText("공유 설정", { exact: true }).click();
  await expect(page.getByLabel("공유할 사용자 ID")).toBeVisible();
  await page.screenshot({ path: info.outputPath("run-parameters.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("Run list distinguishes waiting, blocked and running analyses", async ({ page }) => {
  const base = { plan: { scope: {} }, caller: { subject: "alice", groups: [] }, shared_with: [],
    status: "open", validation: [], created_at: "2026-10-01T10:00:00Z" };
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: [
    { ...base, id: "waiting", steps: [] },
    { ...base, id: "needs-input", steps: [{ ...step, result: { ...step.result, status: "needs_input" } }] },
    { ...base, id: "stopped", steps: [{ ...step, result: { ...step.result, status: "refused" } }] },
    { ...base, id: "running", steps: [], running: { kind: "step", method: "query.trend", started_at: "2026-10-01T10:00:00Z" } },
  ] }));
  await page.goto("/runs");
  const list = page.getByRole("region", { name: "실행 기록 목록" });
  for (const label of ["대기 중", "입력 필요", "중단", "진행 중"]) await expect(list.getByText(label, { exact: true })).toHaveCount(1);
});

test("MCP runs are identifiable and filterable without claiming approval", async ({ page }, info) => {
  const base = { plan: { scope: {} }, caller: { subject: "alice", groups: [] }, shared_with: [],
    status: "completed", validation: [], created_at: "2026-10-01T10:00:00Z", steps: [step] };
  await page.route("**/api/runs?limit=100", route => route.fulfill({ json: [
    { ...base, id: "mcp-example", origin: "mcp" }, { ...base, id: "web-example", origin: "web" },
  ] }));
  await page.route("**/api/runs/mcp-example", route => route.fulfill({ json: { ...base, id: "mcp-example", origin: "mcp" } }));
  await page.goto("/runs");
  await page.getByRole("combobox", { name: "실행 출처" }).selectOption("mcp");
  const list = page.getByRole("region", { name: "실행 기록 목록" });
  await expect(list.getByRole("link")).toHaveCount(1);
  await expect(list).toContainText("MCP 탐색");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("mcp-run-list.png"), fullPage: true });
  await list.getByRole("link").click();
  await expect(page.getByText(/RUN · MCP 탐색/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Recipe 초안 검토" })).toBeVisible();
});

test("old Runs do not invent parameter provenance", async ({ page }) => {
  await page.goto("/runs/legacy-test");
  await page.getByText("표와 실행 근거 보기").click();
  await page.getByText("적용된 설정").click();
  await expect(page.getByText("출처 기록 없음")).toHaveCount(2);
});

test("missing catalog names do not expose semantic URIs in the result", async ({ page }) => {
  await page.route("**/api/runs/unknown-title", route => route.fulfill({ json: {
    id: "unknown-title", plan: { scope: { time_dimension: "cube://local/dim_customer/count" } },
    steps: [{ ...step, result: { ...step.result,
      primary: { type: "summary", title: "결과", data: { metric: "cube://local/dim_customer/count" } },
      provenance: { ...step.result.provenance, semantic_refs: ["cube://local/dim_customer/count"] } } }],
    caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [], created_at: "2026-10-01T10:00:00Z",
  } }));
  await page.goto("/runs/unknown-title");
  await expect(page.getByText("지표 이름 확인 필요", { exact: true }).first()).toBeVisible();
  await page.getByText("분석 범위와 실행 정보").click();
  await expect(page.getByText("날짜 기준 이름 확인 필요", { exact: true })).toBeVisible();
  await expect(page.getByText("cube://local/dim_customer/count", { exact: true })).not.toBeVisible();
  await page.getByText("표와 실행 근거 보기").click();
  await page.locator("summary").filter({ hasText: /^실행 근거/ }).click();
  await expect(page.getByText("지표 참조: cube://local/dim_customer/count")).toBeVisible();
});

test("a one-period trend leads with the answer and keeps audit details folded", async ({ page }, info) => {
  const metric = "cube://local/fact_payment/total_payment_amt";
  const count = "cube://local/fact_payment/count";
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [
    { ref: metric, title: "지급결정금액 합계", kind: "measure" }, { ref: count, title: "지급 건수", kind: "measure" },
  ], hierarchies: {} } }));
  await page.route("**/api/runs/readable-trend", route => route.fulfill({ json: {
    id: "readable-trend", origin: "mcp", plan: { question: "6월 지급액은 얼마인가?", scope: { date_range: ["2026-06-01", "2026-06-30"] } },
    steps: [{ ...step, step: { ...step.step, bindings: { metric } }, result: { ...step.result, interpretation: "descriptive",
      primary: { type: "time_series", title: "amount over time", data: { metric, units: { [metric]: count },
        rows: [{ period: "2026-06-01", [metric]: 860160000, [`${metric}#units`]: 384 }] } },
      artifacts: [{ type: "table", title: "largest period-over-period move per series", data: [] }],
      validation: [{ validator: "non_empty", status: "pass", code: "OK", message: "periods: 1 rows" },
        { validator: "freshness", status: "warning", code: "DATA_STALE", message: "Data only reaches June 4", details: { latest: "2026-06-04", end: "2026-06-30" } }],
      provenance: { ...step.result.provenance, semantic_refs: [metric], queries: [{ native_query: { measures: ["fact_payment.total_payment_amt"] }, rows: 1, elapsed_ms: 4 }] } } }],
    caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [], created_at: "2026-10-01T10:00:00Z",
  } }));
  await page.goto("/runs/readable-trend");
  await expect(page.getByRole("heading", { name: "6월 지급액은 얼마인가?" })).toBeVisible();
  await expect(page.getByText("지급결정금액 합계", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("860,160,000").first()).toBeVisible();
  await page.getByText("표와 실행 근거 보기").click();
  await expect(page.getByRole("columnheader", { name: "지급 건수" })).toBeVisible();
  await expect(page.getByText("기간이 하나뿐이라 증가·감소 추이는 판단할 수 없습니다.")).toBeVisible();
  await expect(page.getByRole("region", { name: "분석 답변" }).getByText(/데이터가 2026-06-04까지만 있어/)).toBeVisible();
  await expect(page.getByText("periods: 1 rows")).not.toBeVisible();
  await expect(page.getByText("largest period-over-period move per series")).toHaveCount(0);
  await expect(page.getByText(metric, { exact: true })).not.toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("readable-trend.png"), fullPage: true });
});

test("Run graph selects recorded steps without implying a dependency", async ({ page }, info) => {
  await page.route("**/api/runs/graph-test", route => route.fulfill({ json: {
    id: "graph-test", plan: { scope: {} }, steps: [step, { ...step,
      step: { id: "breakdown", method: "query.drilldown", bindings: {}, params: {} },
      result: { ...step.result, primary: { type: "table", title: "두 번째 결과", data: { rows: [] } } } }],
    caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [], created_at: "2026-10-01T10:00:00Z",
  } }));
  await page.goto("/runs/graph-test");
  const graph = page.getByRole("region", { name: "실행 그래프" });
  await expect(graph.getByRole("button", { name: "1단계 시간에 따른 변화 결과 보기" })).toBeVisible();
  await expect(graph.getByText("실행 순서", { exact: true })).toBeVisible();
  await graph.getByRole("button", { name: "1단계 시간에 따른 변화 결과 보기" }).click();
  await expect(page.locator('[class*="runStepDetail"]')).toContainText("기간별 값과 변화 확인");
  await graph.getByRole("button", { name: "2단계 항목별로 나눠 보기 결과 보기" }).click();
  await expect(page.locator('[class*="runStepDetail"]')).toContainText("두 번째 결과");
  await page.screenshot({ path: info.outputPath("run-graph.png"), fullPage: true });
});

test("successful Run steps can be reviewed as a Recipe draft", async ({ page }) => {
  await page.route("**/api/runs/promotion-test", route => route.fulfill({ json: {
    id: "promotion-test", plan: { scope: {} }, steps: [step, { ...step, step: { ...step.step, id: "second" } }],
    caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [], created_at: "2026-10-01T10:00:00Z",
  } }));
  await page.route("**/api/runs/promotion-test/recipe-candidate?*", route => route.fulfill({ json: {
    recipe: { name: "analysis-test", version: "1.0.0", status: "draft", description: "반품률 변화",
      origin_runs: ["promotion-test"], mode: "pipeline", routing: { use_for: [], do_not_use_for: [] },
      semantic_scope: { primary_metric: "cube://local/insurance/payout", related_metrics: [], preferred_dimensions: [], required_filters: [] },
      steps: [{ id: "step_1", method: "query.trend", bindings: { metric: "cube://local/insurance/payout" }, params: {} }],
      allowed_methods: [], validators: [], limits: { max_steps: 12, max_queries: 30 } },
    source_run_id: "promotion-test", selected_steps: [0], review_notes: [],
  } }));
  await page.route("**/api/sources/current/readiness", route => route.fulfill({ json: { metrics: [] } }));
  await page.goto("/runs/promotion-test");
  await page.getByRole("button", { name: "Recipe 초안 검토" }).click();
  const graph = page.getByRole("region", { name: "실행 그래프" });
  await expect(graph.getByRole("checkbox", { name: "1단계 초안에 포함" })).toBeChecked();
  await graph.getByRole("checkbox", { name: "2단계 초안에 포함" }).uncheck();
  await page.getByRole("link", { name: "선택한 1단계 검토" }).click();
  await expect(page).toHaveURL(/\/recipes\/new\?from_run=promotion-test&step=0/);
  await expect(page.getByText("실행 기록에서 만든 초안")).toBeVisible();
  await expect(page.getByRole("link", { name: /원본 실행 보기/ })).toHaveAttribute("href", "/runs/promotion-test");
});
