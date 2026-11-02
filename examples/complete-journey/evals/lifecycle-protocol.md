# Document versus Decision Layer lifecycle experiment

Frozen before outcome inspection, 2026-10-27. No product behavior changes.

Question: does executable organizational analysis reduce the total cost of
authoring, repeated use, maintenance and retrospective explanation compared with
a prose procedure whose users can retain and reuse their own code?

## Arms and units

- B: Codex + identical Cube catalog/query/export access + analyst document.
  Initial analyst publishes prose only. Business sessions can author Python and
  persist/reuse it; later analyst maintenance can update those scripts too.
- C: same Codex model and effort + Decision Layer. Analyst authors a fresh
  registered project from the same specification and framework documentation.
  Business sessions discover and execute current registered assets.
- Fresh sessions, persistent per-arm workspace, sequential randomized paired
  order, model `gpt-6.1-sol`, medium effort, same frozen source and catalog.
  Every business request obtains current data. Historical answers cannot replace
  new executions. Both arms retain transcripts, code and prior results.
- Authoring references are downloaded from the public GitHub repository. Local
  repository/installed package source text is not supplied to Codex; calling the
  framework and inspecting public signatures is allowed. The first launch was
  rejected before any session ran because it allowed local source inspection;
  the narrowed public-documentation launch was approved. This restriction may
  affect authoring time and is part of this experiment's observed environment.
- Campaigns 1,2,3,4,5,6,9,12, with repeat/paraphrase requests for 5 and 12:
  10 questions × 3 procedure versions × 2 arms = 60 business calls. Six analyst
  author/maintenance calls and two retrospective audits = 68 planned calls.
  These are 8 related scenarios, not 60 independent datasets or human subjects.

## Version changes

1. Publish cohort diagnostics and prior-sales/frequency adjusted association.
   At least 30 per group; no confidence interval. Original common specification
   is campaign-playbook.md. No case-specific numerical answers in analyst input.
2. Organizational policy changes minimum sample size to 100 in EACH group.
   Smaller groups retain descriptives but must refuse adjusted estimation.
   This cutoff is an experimental policy, not a statistical sufficiency claim.
3. Retain 100 minimum, add HC3 robust 95% normal confidence intervals for the same
   target coefficient (`use_t=False`). Covariates and point estimator unchanged.
4. Audit campaign 2's first and current answer, versions, changed rule and evidence
   without re-querying data or computing a new result.

Questions name only the campaign and ask for performance/next-campaign evidence.
Analytical steps and method names appear only in analyst assets, never questions.
Cases fixed by campaign ID, excluding previous training/pilot 7,8,10,11. Cohort
counts checked before launch: target counts 13,47,12,80,165,64,172,163 respectively.
This includes always-refused, newly-refused and always-eligible cohorts.

## Evaluation and accounting

Independent NumPy reference on the provider-owned cohort checks counts, means,
coefficient and HC3 interval. It does not independently validate upstream cohort
construction. Score numerical correctness, current-policy behavior, material
limitations and audit evidence separately. A correct refusal is a valid result.
No requirement to emit an estimate for every case. Review final answers as well
as tool results; distinguish correct stored results from omissions in narration.

The primary valid-business-result judgment requires a fresh complete retrieval,
current procedure/policy, an adjusted estimate for eligible cohorts or a clear
refusal for ineligible cohorts, and no incorrect numerical claims. Version 3 also
requires the specified interval for eligible cohorts. Match displayed numbers
within their rounding precision (normally 0.02 sales units). Score explanation
coverage separately: eligibility/selection, actual adjustments when estimated,
overlap and demographic missingness, uncertainty, associational interpretation,
and missing profitability evidence. An omitted caveat is not automatically a
wrong coefficient. Audit success requires the original campaign 2 estimate,
current refusal, 30→100 rule, target sample size 47, identifiable versions and
historical evidence; no new analysis may substitute for retained evidence.

Measure CLI wall time, reported input/cached/uncached/output tokens, calls and
changed source files, split by authoring, maintenance, use and audit. Input totals
already include cached tokens. Missing usage stays unknown, not zero. Report
total lifecycle cost, not just runtime savings. No API bill is exposed; do not
translate subscription usage into invented dollar charges or human work hours.
Framework/instrumentation work and manual evaluator review are common research
overhead and not measured human product onboarding time. Startup/check overhead
is recorded separately where measurable. One implementation/update sequence per
arm cannot establish general maintenance-time superiority.

Each author stage gets at most two explicit repair sessions after validation;
all repair time/usage must be counted. Never silently retry business failures.
Preserve incomplete/failed jobs and any protocol deviations. Do not change the
product or evaluator to favor an arm after seeing its outcomes. Short synthetic
checks and project-registration checks may gate deployment before held-out use.
All source/code revisions and raw events remain in the local experiment folder;
only reviewed aggregate observations and the report should be committed.

## Recorded operational deviation

After phase 2 authoring, the shared checkout fingerprint no longer matched:
CLI, Skill loading/scaffolding and starter Skill text had concurrent edits.
Analysis/authoring guide Markdown also changed; it was mistakenly absent from
the initial fingerprint. The initially modified calculation engine, DataInput,
Cube provider and model files still matched their frozen hashes. No user edits
were reverted. A separate runtime was copied under the experiment directory;
changed fingerprinted files were recovered from Git HEAD only after their bytes
matched the initial hashes. Guide Markdown was recovered from HEAD based on its
clean initial git status, without claiming a hash proof that was not recorded.
The updated project passed all 28 tests again against that frozen runtime.

Phase 2 business calls and subsequent stages use the isolated runtime and its
full-file manifest. The initial phase and phase 2 authoring remain observed
descriptive results, with possible environment effects on time/tokens, rather
than a claim of a perfectly fixed-version experiment. Keep this qualification
in the final report and do not silently discard affected runs. The runner change
only redirects the interpreter/MCP process to the isolated runtime; question,
order, model, analytical policy and scoring remain unchanged.

The baseline CSV adapter rejected an otherwise harmless `offset: 0` in three
phase-1 sessions (campaign 6 and both campaign-12 requests; four failed tool
calls). Each session recovered without a new experimental run. Full accounting
includes this time, with a sensitivity analysis excluding both arms of all three
affected pairs. This overhead must not be attributed solely to absence of
Decision Layer. A Decision Layer session also corrected a rejected unversioned
recipe reference within the same session; this remains in full accounting.

The generic runner does not provision the demo, launch/version-switch the API
server, or automatically reconstruct the isolated runtime. The recorded local
controller and runtime manifest capture those operations for this run. A future
replication must provision and freeze the runtime before phase 1, retain the
same semantic snapshot, and start the corresponding registered project before
each business phase. Running the `business` command alone is not a complete
reproduction of this lifecycle experiment.
