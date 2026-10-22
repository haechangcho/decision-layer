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

test("method details lead directly to selecting inputs and running", async ({ page }, info) => {
  await page.goto(`/methods/${manifest.name}`);
  await expect(page.getByRole("link", { name: "입력 선택하고 테스트" })).toHaveAttribute("href", `/recipes/new?method=${manifest.name}`);
  await expect(page.getByRole("button", { name: "현재 연결에서 실행 조건 확인" })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("method-inputs.png"), fullPage: true });
});

test("Skill is readable guidance and cannot be mistaken for an executable Recipe step", async ({ page }) => {
  const skill = { ...manifest, name: "guide.breakdown", implementation: "skill", execution: "agent_guided", roles: {}, parameters: {}, outputs: [] };
  await page.route("**/api/methods/guide.breakdown", route => route.fulfill({ json: skill }));
  await page.route("**/api/methods/guide.breakdown/guide", route => route.fulfill({ json: {
    name: skill.name, version: "1.0.0", sha256: "a".repeat(64), enforcement: "advisory",
    markdown: "Discover the metric. Stop when scope is ambiguous.", suggested_methods: ["query.aggregate"] } }));
  await page.goto("/methods/guide.breakdown");
  await page.getByRole("tab", { name: "분석 지침", exact: true }).click();
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
  await expect(page.getByRole("region", {name:"data", exact:true})).toBeVisible();
  await expect(page.getByText("선택한 ID마다 한 행", {exact:true})).toBeVisible();
  await expect(page.getByText("confounders", {exact:true}).first()).toBeVisible();
  await expect(page.getByText("추가 필터", {exact:false})).toBeVisible();
  await expect(page.getByText("population_filters", {exact:true})).toBeVisible();
  await expect(page.getByRole("link", {name:"입력 선택하고 테스트"})).toHaveAttribute("href", "/recipes/new?method=example.group_metric");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
