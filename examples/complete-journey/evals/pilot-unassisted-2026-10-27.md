# Codex pilot: Cube + self-written Python versus Decision Layer

Diagnostic only: one successful trial per task and condition, not randomized,
using an unpinned Codex CLI default model. The baseline has Cube catalog and
query tools plus a generic Cube-to-CSV export; it has no prewritten OLS or
task-specific analysis tool. Codex wrote and executed Python with installed
pandas/statsmodels. The Decision Layer condition uses saved Recipes and
registered Methods. Both use the same Complete Journey Cube data and detailed
task instructions. Preparation and infrastructure costs are excluded.

| Task | Condition | Input tokens | Cached input (included) | Output tokens | Seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| Sales | Cube + self-written Python | 240,205 | 213,376 | 3,475 | 91.19 |
| Sales | Decision Layer | 228,471 | 188,544 | 3,394 | 86.20 |
| Campaign | Cube + self-written Python | 140,458 | 102,400 | 1,703 | 56.65 |
| Campaign | Decision Layer | 242,884 | 207,488 | 1,621 | 61.77 |

Both sales answers matched the independently verified overall receipts and unit
totals and selected GROCERY (+22,183.29). Both described receipts and total
units moving in opposite directions without claiming a price effect. The
baseline wrote Python to aggregate the exported results. The Recipe retrieved
all department-by-brand groups for both periods and recorded retrieval evidence;
its query sequence differs from the baseline. Query exhaustion does not establish
source ingestion completeness or consistent snapshots across queries.

For campaign 8, both methods reported a +32.4658 adjusted association over
2,008 households, matching an independent SQL cross-product calculation. The
baseline used self-written statsmodels OLS and provided HC3 uncertainty and raw
group summaries. The Decision Layer registered OLS returned no uncertainty
interval or raw group summaries. Both cautioned that the observed association
does not establish a causal campaign effect. These outputs are not equivalent
in detail; do not infer general quality or Recipe effects from the pair.

## Failed preliminary trial and changed setup

The first campaign baseline attempted CSV export twice with a `limit` argument
that the initial adapter rejected. It also invoked a Python executable lacking
statsmodels. Codex fell back to a self-written NumPy calculation and returned
the correct coefficient after failed attempts; this trial took 119.51 seconds,
337,924 input tokens (313,600 cached) and 3,419 output tokens. The tool was
then changed to accept a bounded `limit` and the baseline prompt provided the
installed Python executable path. The corrected baseline was rerun after the
Decision Layer trial. This setup change and sequential order prevent treating
the table as a preregistered randomized comparison. All five trials consumed
1,189,942 input tokens (including cache reads) and 13,612 output tokens.

The raw traces and generated scripts are under
`/private/tmp/dl-campaign-unassisted-20261027`,
`/private/tmp/dl-campaign-unassisted-retry-20261027`, and
`/private/tmp/dl-sales-unassisted-20261027`. The temporary CSV inputs and
generated outputs in these runs were removed when their temporary working
directories closed, so links to them in the raw answers are no longer valid.
Subsequent harness runs preserve local work artifacts in the output directory;
review raw data and local metadata before any publication. The signed-in
ChatGPT account was used; the CLI reported token usage but no dollar cost.
