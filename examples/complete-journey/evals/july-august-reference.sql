-- Independent reference for the pilot, against the Complete Journey PostgreSQL.
-- Preserve missing month/group combinations as zero only after the full join.
WITH totals AS (
    SELECT p.department, p.brand, date_trunc('month', t.transaction_date)::date AS month,
           sum(t.sales_value::numeric) AS receipts
    FROM journey.transaction_data t
    JOIN journey.product p ON p.product_id = t.product_id
    WHERE t.transaction_date >= DATE '2001-07-01' AND t.transaction_date < DATE '2001-09-01'
    GROUP BY 1, 2, 3
), departments AS (
    SELECT department,
           coalesce(sum(receipts) FILTER (WHERE month = DATE '2001-07-01'), 0) AS previous,
           coalesce(sum(receipts) FILTER (WHERE month = DATE '2001-08-01'), 0) AS current
    FROM totals GROUP BY department
)
SELECT department, round(previous, 2) AS july, round(current, 2) AS august,
       round(current - previous, 2) AS change
FROM departments ORDER BY abs(current - previous) DESC, department;
