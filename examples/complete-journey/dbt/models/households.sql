select
    h.household_key,
    coalesce(d.classification_1, 'Not available') as age_code,
    coalesce(d.classification_3, 'Not available') as income_code,
    coalesce(d.classification_5, 'Not available') as composition_code
from {{ source('journey', 'household') }} h
left join {{ source('journey', 'hh_demographic') }} d using (household_key)
