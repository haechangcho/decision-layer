select *
from {{ source('journey', 'campaign_household_outcomes') }}
where eligible
