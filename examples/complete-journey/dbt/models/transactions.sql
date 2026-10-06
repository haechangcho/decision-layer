select
    product_id,
    household_key,
    store_id::text as store,
    transaction_date,
    sales_value::numeric as receipts,
    quantity::numeric as units,
    basket_id,
    case when coupon_disc::numeric < 0 then 1 else 0 end as coupon_line,
    1 as line_count
from {{ source('journey', 'transaction_data') }}
