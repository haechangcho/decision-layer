select
    c.campaign::text as campaign_id,
    c.household_key,
    d.start_date as campaign_start_date
from {{ source('journey', 'campaign_table') }} c
left join {{ source('journey', 'campaign_desc') }} d using (campaign)
