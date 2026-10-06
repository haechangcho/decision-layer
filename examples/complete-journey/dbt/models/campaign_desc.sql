select
    campaign::text as campaign_id,
    description as kind,
    start_day::integer as start_day,
    end_day::integer as end_day,
    start_date,
    end_date
from {{ source('journey', 'campaign_desc') }}
