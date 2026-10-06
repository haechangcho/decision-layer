select
    campaign::text as campaign_id,
    household_key,
    coupon_upc,
    redemption_date
from {{ source('journey', 'coupon_redempt') }}
