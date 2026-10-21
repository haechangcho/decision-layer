-- One row per campaign and household. Bounds describe the dataset, not individual follow-up.
CREATE MATERIALIZED VIEW IF NOT EXISTS journey.campaign_household_outcomes AS
WITH daily AS MATERIALIZED (
  SELECT household_key, transaction_date,
    sum(sales_value::numeric) AS sales,
    count(DISTINCT basket_id) AS baskets
  FROM journey.transaction_data
  GROUP BY household_key, transaction_date
), bounds AS (
  SELECT min(transaction_date) AS first_date, max(transaction_date) AS last_date FROM daily
), recipients AS (
  SELECT DISTINCT campaign, household_key FROM journey.campaign_table
), purchases AS (
  SELECT c.campaign, h.household_key,
    coalesce(sum(d.sales) FILTER (WHERE d.transaction_date < c.start_date), 0) AS pre_sales_30d,
    coalesce(sum(d.baskets) FILTER (WHERE d.transaction_date < c.start_date), 0) AS pre_baskets_30d,
    coalesce(sum(d.sales) FILTER (WHERE d.transaction_date >= c.start_date), 0) AS post_sales_30d
  FROM journey.campaign_desc c CROSS JOIN journey.household h
  LEFT JOIN daily d ON d.household_key = h.household_key
    AND d.transaction_date >= c.start_date - 30 AND d.transaction_date < c.start_date + 30
  GROUP BY c.campaign, h.household_key
), campaign_overlaps AS (
  SELECT c.campaign, r.household_key, count(DISTINCT other.campaign) AS overlapping_campaigns
  FROM journey.campaign_desc c
  JOIN recipients r ON r.campaign <> c.campaign
  JOIN journey.campaign_desc other ON other.campaign = r.campaign
    AND other.start_date < c.start_date + 30 AND other.end_date >= c.start_date - 30
  GROUP BY c.campaign, r.household_key
)
SELECT c.campaign || ':' || h.household_key AS observation_id,
  c.campaign AS campaign_id, h.household_key, c.description AS campaign_type,
  c.start_date AS campaign_start_date,
  r.household_key IS NOT NULL AS is_targeted,
  b.first_date <= c.start_date - 30 AND b.last_date >= c.start_date + 29 AS window_complete,
  b.first_date <= c.start_date - 30 AND b.last_date >= c.start_date + 29
    AND p.pre_baskets_30d > 0 AS eligible,
  CASE WHEN b.first_date <= c.start_date - 30 THEN p.pre_sales_30d END AS pre_sales_30d,
  CASE WHEN b.first_date <= c.start_date - 30 THEN p.pre_baskets_30d END AS pre_baskets_30d,
  CASE WHEN b.last_date >= c.start_date + 29 THEN p.post_sales_30d END AS post_sales_30d,
  CASE WHEN p.pre_sales_30d < 50 THEN '01: <50'
    WHEN p.pre_sales_30d < 150 THEN '02: 50-149.99'
    WHEN p.pre_sales_30d < 300 THEN '03: 150-299.99'
    WHEN p.pre_sales_30d < 600 THEN '04: 300-599.99' ELSE '05: >=600' END AS pre_sales_band,
  CASE WHEN p.pre_baskets_30d = 0 THEN '00: no purchase'
    WHEN p.pre_baskets_30d < 3 THEN '01: 1-2'
    WHEN p.pre_baskets_30d < 6 THEN '02: 3-5'
    WHEN p.pre_baskets_30d < 11 THEN '03: 6-10' ELSE '04: >=11' END AS pre_frequency_band,
  d.classification_1 AS age_code, d.classification_3 AS income_code,
  d.classification_5 AS composition_code,
  coalesce(o.overlapping_campaigns, 0) AS overlapping_campaigns,
  1 AS observation_count
FROM journey.campaign_desc c CROSS JOIN journey.household h CROSS JOIN bounds b
JOIN purchases p ON p.campaign = c.campaign AND p.household_key = h.household_key
LEFT JOIN recipients r ON r.campaign = c.campaign AND r.household_key = h.household_key
LEFT JOIN campaign_overlaps o ON o.campaign = c.campaign AND o.household_key = h.household_key
LEFT JOIN journey.hh_demographic d ON d.household_key = h.household_key
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS campaign_household_observation
  ON journey.campaign_household_outcomes(campaign_id, household_key);
CREATE INDEX IF NOT EXISTS campaign_household_start
  ON journey.campaign_household_outcomes(campaign_start_date);
REFRESH MATERIALIZED VIEW journey.campaign_household_outcomes;
