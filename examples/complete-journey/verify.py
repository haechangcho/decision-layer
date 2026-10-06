"""Independent SQL references; does not call a Decision Layer Method."""
import json
from datetime import date, timedelta
from decimal import Decimal
import os
import psycopg

with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT table_name, rows FROM journey_meta.imports ORDER BY table_name")
        tables = cursor.fetchall()
        assert len(tables) == 8
        cursor.execute("SELECT count(*), sum(sales_value::numeric), min(day::integer), max(day::integer) FROM journey.transaction_data")
        rows, sales, lo, hi = cursor.fetchone()
        assert rows == dict(tables)["transaction_data"]
        cursor.execute("""SELECT table_name, column_name, data_type, is_generated FROM information_schema.columns
            WHERE table_schema = 'journey' AND (table_name, column_name) IN
            (('transaction_data', 'transaction_date'), ('coupon_redempt', 'redemption_date'),
             ('campaign_desc', 'start_date'), ('campaign_desc', 'end_date'))""")
        columns = cursor.fetchall()
        assert len(columns) == 4 and all(kind == 'date' and generated == 'ALWAYS' for _, _, kind, generated in columns)
        cursor.execute("SELECT min(transaction_date), max(transaction_date) FROM journey.transaction_data")
        date_lo, date_hi = cursor.fetchone()
        assert (date_lo, date_hi) == (date(2000, 1, 1) + timedelta(days=lo - 1), date(2000, 1, 1) + timedelta(days=hi - 1))
        cursor.execute("""SELECT
            (SELECT count(*) FROM journey.transaction_data WHERE transaction_date IS NULL OR transaction_date != DATE '2000-01-01' + (day::integer - 1)) +
            (SELECT count(*) FROM journey.coupon_redempt WHERE redemption_date IS NULL OR redemption_date != DATE '2000-01-01' + (day::integer - 1)) +
            (SELECT count(*) FROM journey.campaign_desc WHERE start_date IS NULL OR end_date IS NULL OR
              start_date != DATE '2000-01-01' + (start_day::integer - 1) OR end_date != DATE '2000-01-01' + (end_day::integer - 1) OR end_date < start_date)""")
        assert cursor.fetchone()[0] == 0, "Calendar conversion must preserve every source day and campaign window"
        cursor.execute("SELECT count(*) FROM journey.transaction_data t LEFT JOIN journey.product p USING(product_id)")
        assert cursor.fetchone()[0] == rows, "Product join must not multiply transaction lines"
        cursor.execute("SELECT count(*) FROM journey.household")
        households = cursor.fetchone()[0]
        cursor.execute("SELECT department, sum(sales_value::numeric) AS amount FROM journey.transaction_data JOIN journey.product USING(product_id) GROUP BY department ORDER BY amount DESC LIMIT 1")
        department, amount = cursor.fetchone()
        assert round(sales, 2) == Decimal("8057463.08")
        assert department == "GROCERY" and round(amount, 2) == Decimal("4093814.14")
        cursor.execute("""SELECT
            100.0 * count(*) FILTER (WHERE t.coupon_disc::numeric < 0) / count(*)
            FROM journey.transaction_data t JOIN journey.product p USING (product_id)
            WHERE t.store_id = '364' AND p.department = 'GROCERY'""")
        subject_rate = cursor.fetchone()[0]
        cursor.execute("""SELECT count(*), count(DISTINCT observation_id),
            count(*) FILTER (WHERE eligible AND (post_sales_30d IS NULL OR pre_baskets_30d <= 0))
            FROM journey.campaign_household_outcomes""")
        observations, distinct_observations, invalid = cursor.fetchone()
        cursor.execute("SELECT count(*) FROM journey.campaign_desc")
        assert observations == distinct_observations == households * cursor.fetchone()[0]
        assert invalid == 0
        cursor.execute("""SELECT observation_id, campaign_start_date, household_key, pre_sales_30d,
            pre_baskets_30d, post_sales_30d, is_targeted FROM journey.campaign_household_outcomes
            WHERE eligible ORDER BY (post_sales_30d = 0) DESC, observation_id LIMIT 10""")
        checks = cursor.fetchall()
        for _, start, household, pre_sales, pre_baskets, post_sales, targeted in checks:
            cursor.execute("""SELECT
                coalesce(sum(sales_value::numeric) FILTER (WHERE transaction_date < %s), 0),
                count(DISTINCT basket_id) FILTER (WHERE transaction_date < %s),
                coalesce(sum(sales_value::numeric) FILTER (WHERE transaction_date >= %s), 0)
                FROM journey.transaction_data WHERE household_key=%s
                  AND transaction_date >= %s AND transaction_date < %s""",
                (start,start,start,household,start-timedelta(days=30),start+timedelta(days=30)))
            assert cursor.fetchone() == (pre_sales, pre_baskets, post_sales)
        cursor.execute("""SELECT campaign_id, is_targeted, count(*), avg(post_sales_30d)
            FROM journey.campaign_household_outcomes WHERE eligible AND campaign_id='8' GROUP BY 1,2""")
        campaign_reference = [{"campaign":c,"targeted":t,"households":n,"mean_sales":str(mean)}
                              for c,t,n,mean in cursor.fetchall()]
        print(json.dumps({"tables": dict(tables), "households": households, "retailer_receipts": str(sales),
                          "source_day_range": [lo, hi], "top_department": department, "department_receipts": str(amount),
                          "transaction_date_range": [date_lo.isoformat(), date_hi.isoformat()],
                          "campaign_household_observations": observations,
                          "campaign_8_reference": campaign_reference,
                          "store_364_grocery_coupon_line_rate": str(subject_rate)}))
