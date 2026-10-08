{% if target.type == 'snowflake' %}
select dateadd(day, row_number() over (order by seq4()) - 1, date '1999-01-01')::date as date_day
from table(generator(rowcount => 1826))
{% else %}
select generate_series(date '1999-01-01', date '2003-12-31', interval '1 day')::date as date_day
{% endif %}
