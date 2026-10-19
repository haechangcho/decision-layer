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

test("Skill is readable guidance and cannot be mistaken for an executable Recipe step", async ({ page }) => {
  const skill = { ...manifest, name: "guide.breakdown", implementation: "skill", execution: "agent_guided", roles: {}, parameters: {}, outputs: [] };
  await page.route("**/api/methods/guide.breakdown", route => route.fulfill({ json: skill }));
  await page.route("**/api/methods/guide.breakdown/guide", route => route.fulfill({ json: {
    name: skill.name, version: "1.0.0", sha256: "a".repeat(64), enforcement: "advisory",
    markdown: "Discover the metric. Stop when scope is ambiguous.", suggested_methods: ["query.aggregate"] } }));
  await page.goto("/methods/guide.breakdown");
  await expect(page.getByRole("heading", { name: "AI가 참고하는 분석 지침" })).toBeVisible();
  await expect(page.getByText("Discover the metric. Stop when scope is ambiguous.")).toBeVisible();
  await expect(page.getByRole("link", { name: "분석 절차 만들기" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "현재 연결에서 실행 조건 확인" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "query.aggregate" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("ordinary function inputs explain grain and binding separately from calculation options", async ({ page }) => {
  const native = { ...manifest, kind:"stats", execution:"dataframe", data_inputs: {
    data: {measures:["outcome"], dimensions:[], entity:"unit", format:"dataframe", minimum_rows:1,
      column_args:["outcome", "treatment", "confounders"],
      period_role:"current", filters_parameter:"population_filters", columns: {
        treatment:{kind:"dimension",required:true},
        confounders:{kind:"dimension",accepted_kinds:["dimension","measure"],multiple:true,required:true},
      }},
  }};
  await page.route("**/api/methods/example.group_metric", route => route.fulfill({json:native}));
  await page.route("**/api/methods/example.group_metric/source", route => route.fulfill({json:{
    implementation:"python",version:"1.0.0",permissions:{edit:false,publish:false},content:"def analyze(data):\n    return data",code:null,history:[],
  }}));
  await page.goto(`/methods/${manifest.name}`);
  await page.getByText("함수에 전달되는 데이터 · data",{exact:true}).click();
  await expect(page.getByText("unit에 연결한 개체 하나",{exact:false})).toBeVisible();
  await expect(page.getByRole("cell",{name:"confounders_0, confounders_1, …",exact:true})).toBeVisible();
  await expect(page.getByText("필터: Run 범위 + population_filters 입력.",{exact:false})).toBeVisible();
  await expect(page.getByText("타입과 반환 데이터 검사는 사업적 의미",{exact:false})).toBeVisible();
  await expect(page.getByRole("heading", {name:"함수의 컬럼 인자"})).toBeVisible();
  await expect(page.getByText('["confounders_0", "confounders_1", …]', {exact:true})).toBeVisible();
  await expect(page.getByRole("link", {name:"입력 선택하고 테스트"})).toHaveAttribute("href", "/recipes/new?method=example.group_metric");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
