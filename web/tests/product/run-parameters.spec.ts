import { expect, test } from "@playwright/test";

const step = {
  step: { id: "trend", method: "query.trend", bindings: { metric: "cube://local/insurance/payout" },
    params: { granularity: "month", vs_previous: false } },
  method: "method://query.trend@1.0.0",
  result: { status: "success", primary: null, artifacts: [], warnings: [], validation: [],
    provenance: { method: "method://query.trend@1.0.0", semantic_refs: [], queries: [] } },
  started_at: "2026-10-01T10:00:00Z", finished_at: "2026-10-01T10:00:01Z",
};

const candidateRecipe = { name: "draft", version: "1.0.0", description: "Review the procedure", status: "draft", origin_runs: ["provenance-test"],
  routing: { use_for: [], do_not_use_for: [] }, semantic_scope: { primary_metric: "cube://local/insurance/payout", related_metrics: [], preferred_dimensions: [], required_filters: [] },
  mode: "pipeline", steps: [step.step], allowed_methods: [], validators: [], limits: { max_steps: 12, max_queries: 30 } };

test.beforeEach(async ({ page }) => {
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [], hierarchies: {} } }));
  await page.route("**/api/methods", route => route.fulfill({ json: [] }));
  await page.route("**/api/me", route => route.fulfill({ json: { subject: "alice" } }));
  await page.route("**/api/runs/*/recipe-candidate?*", route => route.fulfill({ json: { recipe: candidateRecipe, source_run_id: "provenance-test", selected_steps: [0], review_notes: [] } }));
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

test("long Run graphs keep step cards readable and the last step selectable", async ({ page }) => {
  await page.route("**/api/runs/long-graph", route => route.fulfill({ json: {
    id: "long-graph", plan: { question: "여러 방법으로 매출을 조사해줘", scope: {} },
    steps: Array.from({ length: 6 }, (_, index) => ({ ...step,
      step: { ...step.step, id: `step-${index}`, purpose: `${index + 1}번째 분석 목적` } })),
    caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [],
    created_at: "2026-10-05T10:00:00Z",
  } }));
  await page.goto("/runs/long-graph");
  const graph = page.getByRole("region", { name: "실행 그래프" });
  const first = graph.locator(".react-flow__node-step").first();
  await expect.poll(async () => (await first.boundingBox())?.width ?? 0).toBeGreaterThanOrEqual(239);
  await expect(graph.locator(".react-flow__pane")).toHaveCSS("touch-action", "pan-y");
  const canvas = graph.locator(".react-flow").locator("..").locator("..");
  await canvas.hover();
  await page.mouse.wheel(0, 400);
  await expect.poll(() => canvas.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
  const last = graph.getByRole("button", { name: "6단계 시간에 따른 변화 결과 보기" });
  await last.click();
  await expect(page.getByText("6 / 6단계", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("one-click registration supports inline retry without a popup", async ({ page }, info) => {
  let requests = 0;
  await page.route("**/api/runs/provenance-test/recipe", route => {
    expect(route.request().method()).toBe("POST");
    expect(route.request().postDataJSON()).toEqual({});
    requests++;
    return route.fulfill(requests === 1
      ? { status: 503, json: { error: { code: "STORE_UNAVAILABLE", message: "저장소에 연결하지 못했습니다. 다시 시도하세요." } } }
      : { json: { name: "saved-analysis", status: "published" } });
  });
  await page.goto("/runs/provenance-test");
  const register = page.getByRole("button", { name: "Recipe로 등록", exact: true });
  await expect(register).toBeInViewport();
  await page.screenshot({ path: info.outputPath("run-registration.png"), fullPage: true });
  await register.click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("alert").filter({ hasText: "저장소" })).toBeVisible();
  await register.click();
  await expect(page.getByRole("heading", { name: "Recipe로 등록했습니다" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Recipe 보기", exact: true })).toHaveAttribute("href", "/recipes/saved-analysis");
  expect(requests).toBe(2);
});

test("a calculated validation refusal does not block procedure registration", async ({ page }) => {
  const refused = { ...step, result: { ...step.result, status: "refused",
    primary: { type: "estimate", title: "Comparison", data: { difference: 3 } },
    validation: [{ validator: "comparability", status: "fail", code: "NOT_COMPARABLE", message: "비교 가능한 표본 부족" }] } };
  await page.route("**/api/runs/validation-refusal", route => route.fulfill({ json: {
    id: "validation-refusal", plan: { question: "조건을 맞춰 비교해줘", scope: {} },
    steps: [refused, { ...step, step: { ...step.step, id: "supplement" } }],
    caller: { subject: "alice", groups: [] }, status: "completed", validation: [],
    shared_with: [], created_at: step.started_at,
  } }));
  await page.route("**/api/runs/validation-refusal/recipe", route => route.fulfill({ json: {
    name: "saved-validation-procedure", status: "published",
  } }));
  await page.goto("/runs/validation-refusal");
  const register = page.getByRole("button", { name: "Recipe로 등록", exact: true });
  await expect(register).toBeEnabled();
  await expect(page.getByText(/보조 비교로 자동 전환하지 않습니다/)).toBeVisible();
  await expect(page.getByRole("link", { name: "편집해서 저장" })).toHaveAttribute("href", /step=0&step=1/);
  await register.click();
  await expect(page.getByRole("heading", { name: "Recipe로 등록했습니다" })).toBeVisible();
});

test("a refusal before calculation still requires editing", async ({ page }) => {
  await page.route("**/api/runs/incomplete-refusal", route => route.fulfill({ json: {
    id: "incomplete-refusal", plan: { scope: {} },
    steps: [step, { ...step, result: { ...step.result, status: "refused" } }],
    caller: { subject: "alice", groups: [] }, status: "completed", validation: [],
    shared_with: [], created_at: step.started_at,
  } }));
  await page.goto("/runs/incomplete-refusal");
  await expect(page.getByRole("button", { name: "Recipe로 등록", exact: true })).toBeDisabled();
  await expect(page.getByRole("link", { name: "편집해서 저장" })).toHaveAttribute("href", /step=0$/);
});

test("Run shows applied values and their sources on demand", async ({ page }, info) => {
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [{ ref: "cube://local/insurance/payout", title: "지급액", kind: "measure" }], hierarchies: {} } }));
  await page.goto("/runs/provenance-test");
  await expect(page.getByRole("heading", { name: "지급액이 왜 변했나?", exact: true })).toBeVisible();
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
  await page.getByRole("tab", { name: "출처", exact: true }).click();
  await expect(page.getByRole("tabpanel")).toContainText("시간에 따른 변화");
  await expect(page.getByRole("tabpanel")).toContainText("v1.0.0");
  await expect(page.getByText("method://query.trend@1.0.0")).not.toBeVisible();
  await page.getByRole("button", { name: "원본 기록 보기" }).click();
  await expect(page.getByRole("dialog", { name: "원본 실행 기록" })).toContainText("method://query.trend@1.0.0");
  await page.keyboard.press("Escape");
  await page.getByRole("tab", { name: "사용한 설정" }).click();
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
    { ...base, id: "awaiting-conclusion", steps: [step] },
  ] }));
  await page.goto("/runs");
  const list = page.getByRole("region", { name: "실행 기록 목록" });
  for (const label of ["대기 중", "입력 필요", "중단", "진행 중", "결론 대기"]) await expect(list.getByText(label, { exact: true })).toHaveCount(1);
});

test("an unfinished MCP analysis keeps its graph and requires review before registration", async ({ page }, info) => {
  const question = "어떤 부문과 매장의 수취액이 높고 동료 집단과 어떻게 다른가?";
  const run = { id: "question-analysis", origin: "mcp", status: "open", running: null,
    plan: { question, scope: {} }, validation: [], conclusion: null,
    caller: { subject: "alice", groups: [] }, shared_with: [], created_at: "2026-10-06T10:00:00Z",
    steps: [0, 1, 2].map(index => ({ ...step, step: { ...step.step, id: `step_${index + 1}`, purpose: `${index + 1}번째 질문 확인` } })),
  };
  let completed = false;
  await page.route("**/api/runs/question-analysis", route => route.fulfill({ json: {
    ...run, status: completed ? "completed" : "open", conclusion_author: completed ? { client_name: "Decision Layer Web" } : null, conclusion: completed ? {
      source: "caller", answer: "결과를 검토했습니다.", findings: [], limitations: [],
    } : null,
  } }));
  await page.route("**/api/runs/question-analysis:complete", async route => {
    const body = route.request().postDataJSON();
    expect(body.conclusion.answer).toBe("결과를 검토했습니다.");
    expect(body.author.client_name).toBe("Decision Layer Web");
    expect(body.conclusion.findings.map((finding: { step_indices: number[] }) => finding.step_indices)).toEqual([[0], [1], [2]]);
    completed = true;
    await route.fulfill({ json: { ...run, status: "completed" } });
  });
  await page.goto("/runs/question-analysis");
  await expect(page.getByRole("heading", { name: question })).toBeVisible();
  await expect(page.getByText("결론 대기", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "실행 그래프" }).locator(".react-flow__node-step")).toHaveCount(3);
  const register = page.getByRole("button", { name: "Recipe로 등록", exact: true });
  await expect(register).toBeDisabled();
  const finish = page.getByRole("button", { name: "결론 저장하고 완료" });
  await expect(finish).toBeDisabled();
  await page.getByRole("textbox", { name: /Conclusion \(when closing\)|결론 \(닫을 때\)/ }).fill("결과를 검토했습니다.");
  await finish.click();
  await expect(register).toBeEnabled();
  await expect(page.getByText("결론 대기", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "분석 답변" })).toContainText("사용자 작성");
  await page.screenshot({ path: info.outputPath("question-scoped-run.png"), fullPage: true });
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
  await expect(page.getByRole("button", { name: "Recipe로 등록", exact: true })).toBeVisible();
});

test("old Runs do not invent parameter provenance", async ({ page }) => {
  await page.goto("/runs/legacy-test");
  await page.getByRole("tab", { name: "사용한 설정" }).click();
  await expect(page.getByText("출처 기록 없음")).toHaveCount(2);
});

for (const method of ["query.drilldown", "query.trend", "query.peer_comparison", "causal.cem", "community.new_method"]) {
  test(`legacy conclusions use the shared result view for ${method}`, async ({ page }) => {
    const original = "복잡한 이전 결론 원문 · 여러 수치와 설정이 나열되어 있음";
    await page.route("**/api/runs/any-analysis", route => route.fulfill({ json: {
      id: "any-analysis", origin: "mcp", plan: { question: "이 지표를 확인해줘", scope: {} },
      steps: [{ ...step, step: { ...step.step, method }, result: { ...step.result, primary: { type: "table", title: "다른 도메인의 측정 결과", data: [] } } }],
      summary: original, conclusion: { source: "execution", answer: "Execution summary", findings: [], limitations: [] },
      caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [], created_at: "2026-10-05T10:00:00Z",
    } }));
    await page.goto("/runs/any-analysis");
    const answer = page.getByRole("region", { name: "분석 답변" });
    await expect(answer).toContainText("단계별 결과 요약");
    await expect(answer).toContainText("다른 도메인의 측정 결과");
    await expect(answer.getByText(original, { exact: true })).not.toBeVisible();
    await answer.getByRole("button", { name: "기존 결론 원문 보기" }).click();
    await expect(page.getByRole("dialog", { name: "기존 결론 원문" })).toContainText(original);
    await page.getByRole("dialog").getByRole("button", { name: "닫기" }).click();
    await answer.getByRole("button", { name: /1단계/ }).click();
    await expect(page.getByRole("tab", { name: "결과", exact: true })).toHaveAttribute("aria-selected", "true");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("structured answers link to evidence and distinguish product from model", async ({ page }, info) => {
  await page.route("**/api/runs/structured", route => route.fulfill({ json: {
    id: "structured", origin: "mcp", plan: { question: "조건을 맞춰도 차이가 있나?", scope: {} },
    steps: [{ ...step, author: { client_name: "Example Client", client_version: "2.0", client_source: "protocol", model_id: "example-model", model_source: "client_reported" },
      result: { ...step.result, primary: { type: "estimate", data: { metric: "cube://local/insurance/payout", target: { label: "A" }, comparison: { label: "B" }, raw: { target: 10, comparison: 12, difference: -2 }, matched: { target: 11, comparison: 12, difference: -1 } } },
        artifacts: [{ type: "balance", title: "비교 표본", data: { target_retention: 0.968, target_units: 100 } }],
        validation: [{ validator: "comparability", status: "pass", code: "OK", message: "비교 조건 충족" }] } }],
    conclusion: { answer: "조건을 맞춘 뒤에도 차이가 남았습니다.", findings: [{ text: "대상 집단의 값이 더 낮았습니다.", step_indices: [0] }], limitations: ["관찰 비교이며 원인으로 단정할 수 없습니다."] },
    summary: "복잡한 이전 형식 요약", conclusion_author: { client_name: "Example Client", model_id: "example-model", model_source: "client_reported" },
    caller: { subject: "alice", groups: [] }, shared_with: [], status: "completed", validation: [], created_at: "2026-10-05T10:00:00Z",
  } }));
  await page.goto("/runs/structured");
  const answer = page.getByRole("region", { name: "분석 답변" });
  await expect(answer).toContainText("조건을 맞춘 뒤에도 차이가 남았습니다.");
  await expect(answer).not.toContainText("복잡한 이전 형식 요약");
  await expect(answer).toContainText("AI 작성");
  await answer.getByRole("button", { name: /1단계/ }).click();
  await expect(page.getByRole("cell", { name: "조건 맞춤 전", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "조건 맞춤 후", exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "검증·추가 결과 1개" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("비교 조건 충족");
  await expect(page.getByRole("tabpanel")).toContainText("96.8%");
  await page.getByRole("tab", { name: "출처", exact: true }).click();
  await expect(page.getByRole("tabpanel")).toContainText("Example Client");
  await expect(page.getByRole("tabpanel")).toContainText("example-model");
  await expect(page.getByRole("tabpanel")).toContainText("미제공");
  await expect(page.locator("details")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("structured-answer-sources.png"), fullPage: true });
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
  await page.getByRole("tab", { name: "사용한 설정" }).click();
  await expect(page.getByText("날짜 기준 이름 확인 필요", { exact: true })).toBeVisible();
  await expect(page.getByText("cube://local/dim_customer/count", { exact: true })).not.toBeVisible();
  await page.getByRole("tab", { name: "출처", exact: true }).click();
  await expect(page.getByText("cube://local/dim_customer/count", { exact: true })).not.toBeVisible();
  await page.getByRole("button", { name: "원본 기록 보기" }).click();
  await expect(page.getByRole("dialog", { name: "원본 실행 기록" })).toContainText("cube://local/dim_customer/count");
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
  await expect(page.locator("details")).toHaveCount(0);
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
      result: { ...step.result, primary: { type: "table", title: "두 번째 결과", data: { rows: [] } },
        artifacts: [{ type: "table", title: "추가 비교", data: [{ group: "A", count: 42 }] }] } }],
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
  await page.getByRole("tab", { name: "검증·추가 결과 1개" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("추가 비교");
  await expect(page.getByRole("tabpanel")).toContainText("42");
  await expect(page.locator("details")).toHaveCount(0);
  await graph.getByRole("button", { name: "1단계 시간에 따른 변화 결과 보기" }).click();
  await expect(page.getByRole("tab", { name: "결과", exact: true })).toHaveAttribute("aria-selected", "true");
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
  await page.getByRole("link", { name: "편집해서 저장" }).click();
  await expect(page).toHaveURL(/\/recipes\/new\?from_run=promotion-test&step=0&step=1/);
  await expect(page.getByText("실행 기록에서 가져온 분석 절차")).toBeVisible();
  await expect(page.getByRole("link", { name: /원본 실행 보기/ })).toHaveAttribute("href", "/runs/promotion-test");
});
