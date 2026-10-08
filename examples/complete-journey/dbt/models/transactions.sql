select
    product_id,
    household_key,
    store_id::text as store,
    transaction_date,
    cast(sales_value as decimal(18, 4)) as receipts,
    cast(quantity as decimal(18, 4)) as units,
    basket_id,
    case when cast(coupon_disc as decimal(18, 4)) < 0 then 1 else 0 end as coupon_line,
    1 as line_count
from {{ source('journey', 'transaction_data') }}
