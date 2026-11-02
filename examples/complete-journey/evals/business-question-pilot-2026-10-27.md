# Business-question pilot — 2026-10-27

## What was tested

The business owner asked only:

> 8번 캠페인 성과가 어땠어? 다음 캠페인을 진행할지 판단하는 데 도움이 될 근거를 알려줘.

The same question was repeated with campaign 7. Neither question named OLS,
specified a cohort, or supplied an analytical procedure. The two conditions
shared the Complete Journey demo's Cube data and semantic catalog:

* **Cube baseline:** Codex could inspect and query Cube, export query results,
  and write/run its own Python with ordinary installed libraries. It received
  no analyst-authored procedure or prebuilt campaign-analysis tool.
* **Decision Layer:** Codex could discover and execute registered analysis
  assets through MCP. An analyst had registered the campaign investigation
  Recipe and its Python Methods beforehand. The agent could not write a new
  analysis method for this condition.

See [the protocol](business-question-protocol.md) for the rubric, differences
in tool-access instructions, and reproduction details. This compares the
**product plus encoded analyst knowledge** with an agent working from generic
Cube access. It does not isolate the marginal effect of one component. The
model was the local Codex default rather than a pinned model. Each cell has
one agent run; this is a diagnostic pilot, not a statistical benchmark.

## Initial Recipe: both attempts stopped

The first analyst Recipe specified a default date range but did not tell the
agent to use it when the business owner omitted dates. The agent found the
Recipe for both questions, then requested a date range instead of producing an
analysis. For campaign 8 it attempted `period.mode=all`, which the Python
Method execution rejected because it needs a bounded range. An earlier start
also used the invalid interpretation label `associational` and was corrected
to `association` after validation. These are product/agent usability failures,
not evidence that the questions lacked enough information.

| Initial run | Result | Wall time | Input tokens (cached) | Output tokens |
| --- | --- | ---: | ---: | ---: |
| Decision Layer, campaign 8 | Asked for dates; no result | 96.81 s | 361,808 (323,712) | 1,743 |
| Decision Layer, campaign 7 | Asked for dates; no result | 55.61 s | 205,202 (179,328) | 1,058 |

After examining these failures **and the baseline's work**, the analyst
created an exploratory v2 Recipe. It specifies a dataset-bounded default
campaign-start date range of 2000-01-01 through 2001-12-11 and executes two
registered Methods in order: cohort/balance/missingness inspection, then an
OLS association adjusted for prior 30-day sales and purchase frequency. The
Methods require exactly one campaign, both target and comparison groups, and
complete retrieval as far as the Cube provider can verify. The v2 Recipe and
Methods are under [reuse-project](reuse-project/). This revision was made
after seeing pilot results; the following runs are **exploratory**, not
independent confirmation of a prespecified improvement. The v2 execution
policy also differed from the initial trial; its Recipe still used a concrete
bounded range.

## Follow-up runs: short business questions, no method hints

| Question / condition | What it actually did | Wall time | Input tokens (cached) | Output tokens |
| --- | --- | ---: | ---: | ---: |
| Campaign 8 / Cube baseline | Wrote Python, queried Cube, compared cohorts, checked other campaigns and coupon use, computed raw change and exploratory adjusted models | 149.63 s | 268,431 (226,304) | 4,284 |
| Campaign 8 / Decision Layer v2 | Found the Recipe; both registered Methods executed, with an inspectable Run | 121.82 s | 349,138 (297,216) | 2,760 |
| Campaign 7 / Cube baseline | Wrote Python, queried Cube, checked coupon use and overlap, computed raw change and an exploratory adjusted model | 132.98 s | 313,299 (280,192) | 3,616 |
| Campaign 7 / Decision Layer v2 | Found the same Recipe; both Methods executed with the campaign 7 filter, with an inspectable Run | 88.54 s | 261,192 (210,176) | 2,226 |

The registered Method estimated a target-list association of **+32.47** per
eligible household for campaign 8 (1,043 targeted, 965 comparison) and
**+39.62** for campaign 7 (195 targeted, 1,816 comparison), after adjusting
for prior sales and purchase frequency. Independent SQL cohort summaries and
OLS cross-products in [business-campaign-reference.sql](business-campaign-reference.sql)
agree with these figures. Both Run answers identified higher prior purchasing
in targeted households, other overlapping campaigns, the absence of verified
exposure and campaign cost/margin, and the inability to establish a causal
effect or ROI. The Methods report no confidence intervals, so neither answer
could assess estimate uncertainty.

The baseline agent **also performed substantive analysis on its own**. For
campaign 8 it reported a raw change contrast of +5.46 with a 95% interval of
−5.90 to +16.81 and an exploratory adjusted estimate of +23.43 with an interval
of +10.64 to +36.22. For campaign 7 it reported a raw change contrast of +8.83
with an interval of −12.62 to +30.28 and an exploratory adjusted estimate of
+30.32 with an interval of +9.09 to +51.56. It correctly treated these as
noncausal and recommended a controlled follow-up before expansion. It also
checked coupon responses, which the registered Recipe did not include. The
baseline used different, agent-selected covariates and functional forms, so
its adjusted coefficients are **not the same estimand/specification** as the
registered Method's +32.47/+39.62 and should not be judged as arithmetic
errors solely because they differ.

There is a concrete baseline quality concern: in the campaign 8 generated
analysis, 1,229 of 2,008 eligible households lacked demographic codes and
were placed in an `Unknown` category, but the final answer described its
demographic adjustment without disclosing that large missing share. The
baseline also tried several candidate models; its intervals and model choices
were not independently audited in this pilot. Conversely, Decision Layer's
registered OLS omitted overlapping campaign targeting from adjustment and
gave no uncertainty interval. Neither condition established incremental
sales or campaign profitability. No condition should be scored as having
answered the decision definitively.

## What the numbers support

The v2 runs show that a business owner can ask a short question and get the
**same analyst-defined two-step procedure** applied to two campaigns, with
versioned Methods, validated inputs and an inspectable Run. The baseline
shows that an unconstrained Codex agent can already discover a useful
multi-step investigation from the same short question. This pilot therefore
does **not** demonstrate better answer quality for Decision Layer. The
initial two failed runs show that Recipe defaults and runtime parameter
selection are part of the product value and must work before this is reliable.

There is no demonstrated token saving. The v2 Decision Layer runs used
610,330 total input tokens versus 581,730 for the two baseline runs, while
using 4,986 output tokens versus 7,900. Cached input comprised much of both
conditions, so raw token totals should not be turned into a dollar claim.
The v2 runs were faster in this small sample (210.36 s total versus 282.61 s),
but one run per cell and different tools preclude a latency conclusion.
Recipe authoring and maintenance time were excluded. The local Codex CLI did
not expose a reliable charge for these runs; monetary cost remains unmeasured.

The next evaluation should freeze the Recipe, model, data snapshot and tool
instructions before collecting hidden questions from business owners. It
should include cases where the registered procedure ought to refuse or ask
for missing evidence, and review actual Run records and baseline code against
a separately specified analytical rubric. Measure setup/maintenance effort,
answer validity, provenance completeness, repeatability, tokens, latency and
charges. Separately improve the Recipe or Method to report uncertainty and
handle overlapping campaigns if that becomes part of the approved analytical
procedure; the agent should not silently change the model per question.

Detailed local traces (not for publication without review):

* `/private/tmp/dl-business-8-baseline-v2/` and `/private/tmp/dl-business-7-v1/`
* `/private/tmp/dl-business-8-v1/` and `/private/tmp/dl-business-7-v1/`
* `/private/tmp/dl-business-8-recipe-v2/` and `/private/tmp/dl-business-7-recipe-v2/`

