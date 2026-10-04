import { expect, test } from "@playwright/test";
import type { SemanticObject } from "../../lib/api";
import { suggestedDateRange, suggestedTimeDimension } from "../../lib/semantic-dates";

const metric = "cube://production/manufacturing/defects";
const time = "cube://production/manufacturing/inspection_date";
const object: SemanticObject = { ref: time, kind: "time_dimension", title: "검사일", data_type: "time", public: true,
  metadata: { suggestedDateRange: ["2023-01-01", "2023-09-30"] } };
const baseRecipe = { name: "defect-review", version: "1.0.0", description: "품질 검사 분석", mode: "pipeline",
  routing: { use_for: [], do_not_use_for: [] },
  semantic_scope: { primary_metric: metric, related_metrics: [], preferred_dimensions: [], required_filters: [] },
  steps: [{ id: "trend", method: "query.trend", bindings: { metric }, params: {} }],
  allowed_methods: [], validators: [], limits: { max_steps: 12, max_queries: 30 } };

test("period hints reject invalid dates and never guess across semantic cubes", () => {
  expect(suggestedDateRange(object)).toEqual(["2023-01-01", "2023-09-30"]);
  for (const range of [["2023-02-29", "2023-09-30"], ["2024-01-01", "2023-01-01"], [1, 2]])
    expect(suggestedDateRange({ ...object, metadata: { suggestedDateRange: range } })).toBeNull();
  expect(suggestedTimeDimension([object], metric)?.ref).toBe(time);
  expect(suggestedTimeDimension([object], "cube://production/finance/revenue")).toBeUndefined();
  expect(suggestedTimeDimension([object, { ...object, ref: "cube://production/manufacturing/shipment_date" }], metric)).toBeUndefined();
});

test("provider period suggestions work outside the sample domain and preserve Recipe defaults", async ({ page }) => {
  await page.route("**/api/semantic/catalog", route => route.fulfill({ json: { objects: [
    { ref: metric, title: "Defects", kind: "measure" }, object,
    { ref: "cube://production/finance/date", title: "Accounting date", kind: "time_dimension" },
  ], hierarchies: {} } }));
  await page.route("**/api/sources/current/readiness", route => route.fulfill({ json: { metrics: [] } }));
  await page.route("**/api/recipes/defect-review", route => route.fulfill({ json: baseRecipe }));
  await page.goto("/recipes/defect-review");
  await expect(page.getByLabel("날짜 기준")).toHaveValue(time);
  await expect(page.getByLabel("시작일", { exact: true })).toHaveValue("2023-01-01");
  await expect(page.getByLabel("종료일", { exact: true })).toHaveValue("2023-09-30");
  await page.getByLabel("시작일", { exact: true }).fill("2023-03-01");
  await page.getByLabel("날짜 기준").selectOption("cube://production/finance/date");
  await page.getByLabel("날짜 기준").selectOption(time);
  await expect(page.getByLabel("시작일", { exact: true })).toHaveValue("2023-03-01");
  await page.route("**/api/recipes/defect-review", route => route.fulfill({ json: { ...baseRecipe,
    default_scope: { date_range: ["2022-04-01", "2022-06-30"], time_dimension: time } } }));
  await page.reload();
  await expect(page.getByLabel("시작일", { exact: true })).toHaveValue("2022-04-01");
  await expect(page.getByLabel("종료일", { exact: true })).toHaveValue("2022-06-30");
});
