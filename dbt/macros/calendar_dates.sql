{#- Date rules for US federal holidays. `year` is a SQL expression; ISO weekdays (1 = Monday). -#}

{#- The n-th given weekday of a month, e.g. Thanksgiving = nth_weekday(year, 11, 4, 4). -#}
{% macro nth_weekday(year, month, isodow, n) -%}
    (make_date({{ year }}, {{ month }}, 1)
        + cast(({{ isodow }} - isodow(make_date({{ year }}, {{ month }}, 1)) + 7) % 7
               + 7 * ({{ n }} - 1) as integer))
{%- endmacro %}

{#- The last given weekday of a month, e.g. Memorial Day = last_weekday(year, 5, 1). -#}
{% macro last_weekday(year, month, isodow) -%}
    (last_day(make_date({{ year }}, {{ month }}, 1))
        - cast((isodow(last_day(make_date({{ year }}, {{ month }}, 1))) - {{ isodow }} + 7) % 7
               as integer))
{%- endmacro %}

{#- Federal observance of a fixed-date holiday: Saturday → Friday, Sunday → Monday. -#}
{% macro observed(day) -%}
    (case isodow({{ day }})
        when 6 then {{ day }} - 1
        when 7 then {{ day }} + 1
        else {{ day }}
    end)
{%- endmacro %}
