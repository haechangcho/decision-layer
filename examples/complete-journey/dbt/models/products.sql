select product_id, department, brand, commodity_desc as commodity
from {{ source('journey', 'product') }}
