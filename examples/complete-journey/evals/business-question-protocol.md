# Business-question pilot: analyst knowledge reuse

## Question and design

Test whether analyst-authored procedures help a business owner who does not
name analytical methods or spell out the steps. The prompts are:

* `8번 캠페인 성과가 어땠어? 다음 캠페인을 진행할지 판단하는 데 도움이 될 근거를 알려줘.`
* `7번 캠페인 성과가 어땠어? 다음 캠페인을 진행할지 판단하는 데 도움이 될 근거를 알려줘.`

Both conditions receive exactly the same question, Cube dataset and semantic
catalog. The baseline has generic Cube query and CSV-export tools, a Python
interpreter and ordinary libraries; it receives no analyst procedure, OLS
instructions, prewritten task-specific analysis or Decision Layer code. The
other condition has Decision Layer tools and an analyst-authored Recipe using a
registered Python Method. Its prompt does not name the Recipe or analysis
method, or list the steps. Tool-access and safety instructions are necessarily
different: the baseline may write Python, Decision Layer must use registered
assets. This is a comparison of the product plus encoded organizational
knowledge against an agent without that knowledge, not an isolated Recipe
effect or a comparison against an analyst-provided prompt.

The Recipe considers eligible target-list and non-target households, prior
30-day purchase amount and frequency, and subsequent 30-day purchase amount.
It reports group sizes, raw means and a prior-activity-adjusted OLS association.
It requires one campaign and at least 30 observations in each group. It flags
unverified causal identification, target-list membership versus actual
exposure, unreported uncertainty and limited eligibility. It does not claim a
campaign should be continued or that associations are an incremental effect.

## Evaluation rubric fixed before the trial

Review final answers and execution traces independently of model self-reports:

1. Correct campaign, population and outcome period; no fabricated numbers.
2. Comparison group and its limitations identified; raw group sizes and means
   where actually returned.
3. Prior purchase activity accounted for, with an explicit distinction between
   raw comparisons and adjusted associations. A different sound method can also
   receive credit; execution evidence and valid assumptions are required.
4. Selection and exposure limitations, lack of causal identification, and
   uncertainty explained. No claim that observed differences prove impact, ROI,
   or that the campaign should be continued.
5. Evidence actually supports each statement; ask for missing data rather than
   silently invent it. Identify any additional useful evidence and limitations.
6. Record wall time, tool calls, input/cached/output tokens and generated code.

Separately check the Recipe selection, actual Run, calculation and required
retrieval checks. When the baseline cannot execute Python or query the data,
record the error instead of treating failure to run as an analytical outcome.
Independent SQL cross-products and summaries are in `business-campaign-reference.sql`.
Camp 7 and 8 are a small public pilot, not a hidden or representative benchmark;
their gold numbers are never included in the model prompts. Outputs may differ
because of prompt randomness, model changes, services and scheduling. The
default model is not pinned. Recipe authoring effort is excluded from the trial.
The baseline and Recipe are allowed to produce different analyses and levels of
detail; do not equate a faster response with a better answer or claim causality.

## Exploratory revision after the first trials

The first Recipe paused for a date range for both business questions. After
inspecting those failures and the baseline analyses, a second Recipe version
was authored: it explicitly directs the agent to use its dataset-bounded
default period, and separates a cohort/missingness/overlapping-campaign check
from the adjusted comparison. This revision was made after seeing pilot
results, so its follow-up trials are exploratory and are not independent
confirmation. Preserve the original failures in the report. The runtime policy
for the v2 trial allows all-period mode, although the Python Methods still
require a concrete range and the Recipe directs use of the default range.

For reproduction, start the experiment server as in `reuse-protocol.md`, with
only the desired version of `campaign-business*.yaml` in `DL_RECIPES_DIR`. Use a
unique local database and set `DL_EXECUTION_POLICY` to allow its 711-day demo
scope. Then run `codex_pilot.py --task business8` and `--task business7` with
unique output paths. To reproduce a single diagnostic condition use
`--condition cube` or `--condition decision_layer`. Do not publish the raw
workspaces without reviewing their data and metadata. The model prompts do not
contain the SQL reference values or the analyst-authored Recipe instructions.
