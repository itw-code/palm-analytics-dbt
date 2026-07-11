{% test non_negative(model, column_name) %}
-- Custom generic test: fails if any value in the column is negative.
select {{ column_name }}
from {{ model }}
where {{ column_name }} < 0
{% endtest %}
