# Campaign performance investigation — analyst procedure 2.0.0

Use this procedure for one campaign's performance and next-campaign decision.
It contains no campaign-specific answers or executable calculation code.

1. Discover the semantic catalog. Use `campaign_household_outcomes`, which
   contains eligible previously active households with complete dataset windows.
   Keep its provider-owned definitions. Select exactly one campaign using
   `campaign_id`. Use the unique `observation_id` as the observational unit.
   If no dates are supplied, use the demo campaign-start-date range
   2000-01-01 through 2001-12-11. This selects campaign start dates; it does not
   change the fixed prior/subsequent 30-day purchase windows.
2. Retrieve the complete eligible household cohort for that campaign. Check
   query exhaustion, unique non-null IDs, and exactly one campaign. For both
   numeric target-list groups (0 and 1), report household count and mean prior
   sales, prior purchase frequency and subsequent sales. Count households
   targeted by other overlapping campaigns (`overlapping_campaigns > 0`) and
   missing age, income and composition codes. These are cohort diagnostics.
3. Compare subsequent household sales using OLS with an intercept,
   target-list membership and exactly two covariates: prior sales and prior
   purchase frequency. The provider measures are `post_sales_mean`,
   `pre_sales_mean` and `pre_frequency_mean`, at the observation grain. Stop
   this estimation if either group has fewer than 30 observations, inputs are
   nonfinite/missing, outcome is constant, IDs repeat, variables overlap, the
   design is rank deficient, rows do not outnumber coefficients, or complete
   retrieval cannot be established. Report the target coefficient, sample
   size, both groups' descriptive means and the variables actually adjusted.
4. This registered procedure does not compute a confidence interval. State
   that estimate uncertainty is unreported; do not assert statistical
   significance. The adjustment does not include demographic classifications
   or overlapping campaigns. Preserve those limitations in the explanation.
5. Explain that target-list membership is not verified exposure or randomized
   assignment, and non-targets may receive other marketing. Prior purchasing
   differences, overlapping campaigns and limited cohort eligibility constrain
   interpretation. This is an association, not verified incremental campaign
   sales. It does not establish profitability or a decision to continue.
   Missing cost, discount burden and margin prevent a profitability assessment.
   Say what further evidence is needed and retain query/calculation evidence.

Do not substitute a different procedure silently. If a separate supplementary
analysis is useful, label it separately and disclose its assumptions.
