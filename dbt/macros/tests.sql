{% test date_coverage(model, column_name, start_date, end_date) %}
select expected_date
from range(date '{{ start_date }}', date '{{ end_date }}' + interval 1 day, interval 1 day) as expected(expected_date)
left join (
    select distinct {{ column_name }} as observed_date
    from {{ model }}
) observed on expected.expected_date = observed.observed_date
where observed.observed_date is null
{% endtest %}

{% test min_row_count(model, minimum) %}
select count(*) as row_count
from {{ model }}
having count(*) < {{ minimum }}
{% endtest %}

{% test relationships_where_present(model, column_name, to, field) %}
select distinct child.{{ column_name }}
from {{ model }} child
left join {{ to }} parent
  on child.{{ column_name }} = parent.{{ field }}
where child.{{ column_name }} is not null
  and parent.{{ field }} is null
{% endtest %}
