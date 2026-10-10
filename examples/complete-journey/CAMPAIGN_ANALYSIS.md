# Campaign Household Comparison

The importer builds `journey.campaign_household_outcomes` once and refreshes it on subsequent imports.
Cube reads its eligible rows. Reference dbt model definitions read the same rows when deployed to your own dbt environment. The source
tables are unchanged. Each observation is one campaign and household, not a transaction or coupon redemption.

## Definitions

- Target: household present in that campaign's deduplicated target list. Control: absent from that list.
- Prior window: `[campaign start - 30 days, campaign start)`.
- Subsequent window: `[campaign start, campaign start + 30 days)`.
- Eligible: both windows fit the dataset's date bounds and the household purchased at least once in the prior window.
- Outcome: subsequent mean household sales; eligible non-purchasers contribute zero.
- Prior amount bands: below 50, 50 to below 150, 150 to below 300, 300 to below 600, 600 or more dollars.
- Prior frequency bands: 1-2, 3-5, 6-10, 11+ baskets. Raw model also retains zero-history rows as ineligible.
- Household classifications remain publisher codes; missing values stay null and are excluded if used for matching.
- Other overlapping targeted campaigns: distinct other campaign assignments overlapping the combined prior/subsequent window.

Selecting a date range selects **campaign start dates**; it does not crop the relative purchase windows.
Select one campaign for a household comparison. Combining campaigns repeats households; no independence
or clustered uncertainty estimate is claimed. The 30-day definition and bands are fixed sample model
definitions, not global defaults or arbitrary runtime parameters. Change and version the model to use another horizon.

Dataset bounds are not proof of individual follow-up. The household universe is derived from purchasers,
not a full eligible customer registry. Target assignment is not random, actual receipt timestamps are missing,
and controls can receive other campaigns. No campaign causal ground truth is supplied.

## Execute

Use `causal.cem`, a campaign filter and an explicit period containing its start date. Bind:

| Role | Cube member |
| --- | --- |
| metric | campaign_household_outcomes.post_sales_mean |
| sample_count | campaign_household_outcomes.count |
| treatment | campaign_household_outcomes.is_targeted |
| conditions | pre_sales_band, pre_frequency_band (same cube) |

Use target `[true]` and comparison `[false]`. The Method verifies one non-null outcome and one counted row
per provider-declared primary unit. Results show raw/matched means and retention, **not continuous-outcome
confidence intervals or significance**. Add demographic conditions as a separate step; default overlap checks
may refuse because of missing values and sparse shared strata. Do not lower thresholds just to obtain a result.

Hosted dbt GraphQL
metadata currently cannot verify this contract, so the product adapter still refuses rather than guessing.

## Existing Volumes

Cube, from this example directory:

```bash
docker compose -p decision-layer-cube build import api
docker compose -p decision-layer-cube run --rm --no-deps import
docker compose -p decision-layer-cube up -d --no-deps --wait cube api
```

No volume deletion or source re-download is required. Refresh takes an exclusive lock on this sample
materialized view; do not refresh during active analyses. For a fresh install, the normal startup commands
already create it. CEM is now version 1.1.0: review older pinned Recipes explicitly; old Runs are unchanged.

Opt-in boundary and Cube tests are in `tests/provider/test_campaign_outcomes_live.py`.
Set `DL_JOURNEY_DATABASE_URL` for isolated SQL tests and `DL_JOURNEY_CUBE_URL` plus
`DL_JOURNEY_CUBE_SECRET` for Cube verification against the independent SQL baseline.
