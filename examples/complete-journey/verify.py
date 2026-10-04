"""Independent SQL references; does not call a Decision Layer Method."""
import json
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
        print(json.dumps({"tables": dict(tables), "households": households, "retailer_receipts": str(sales),
                          "source_day_range": [lo, hi], "top_department": department, "department_receipts": str(amount),
                          "store_364_grocery_coupon_line_rate": str(subject_rate)}))
