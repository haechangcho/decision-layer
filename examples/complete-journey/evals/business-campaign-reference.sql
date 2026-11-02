-- Independent group summaries and OLS cross-products for two pilot cases.
WITH observations AS (
    SELECT campaign_id, (CASE WHEN is_targeted THEN 1 ELSE 0 END)::numeric AS t,
           pre_sales_30d::numeric AS x1, pre_baskets_30d::numeric AS x2,
           post_sales_30d::numeric AS y
    FROM journey.campaign_household_outcomes
    WHERE eligible AND campaign_id IN ('7', '8')
)
SELECT campaign_id, t, count(*) AS n, avg(y) AS outcome_mean,
       avg(x1) AS prior_sales_mean, avg(x2) AS prior_frequency_mean,
       sum(y) AS sy, sum(x1) AS sx1, sum(x2) AS sx2,
       sum(x1*x1) AS sx1x1, sum(x1*x2) AS sx1x2, sum(x2*x2) AS sx2x2,
       sum(x1*y) AS sx1y, sum(x2*y) AS sx2y
FROM observations GROUP BY campaign_id, t ORDER BY campaign_id, t;
