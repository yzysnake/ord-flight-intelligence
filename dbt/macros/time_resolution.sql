{#- Turn day-of-month and clock-time fragments (from FAA advisories) into UTC timestamps near an
    anchor. All arguments are SQL expressions; parts are text such as '04', '21', '05'. -#}

{% macro hours_minutes(hh, mi) -%}
    (try_cast({{ hh }} as integer) * interval 1 hour + try_cast({{ mi }} as integer) * interval 1 minute)
{%- endmacro %}

{#- Day `dd` at hh:mm in the anchor's month, or the month before or after when `dd` is more than
    15 days away (e.g. "31/2300Z" in an advisory sent on the 1st). -#}
{% macro day_time_near(anchor, dd, hh, mi) -%}
    (date_trunc('month', {{ anchor }})
        + (case
            when try_cast({{ dd }} as integer) - day({{ anchor }}) > 15 then -1
            when day({{ anchor }}) - try_cast({{ dd }} as integer) > 15 then 1
            else 0
        end) * interval 1 month
        + (try_cast({{ dd }} as integer) - 1) * interval 1 day
        + {{ hours_minutes(hh, mi) }})
{%- endmacro %}

{#- hh:mm on the anchor's UTC date, or the day before or after, whichever is nearest. -#}
{% macro time_near(anchor, hh, mi) -%}
    {%- set same_day = "(date_trunc('day', " ~ anchor ~ ") + " ~ hours_minutes(hh, mi) ~ ")" -%}
    ({{ same_day }} + (case
        when epoch({{ same_day }}) - epoch({{ anchor }}) > 43200 then -1
        when epoch({{ same_day }}) - epoch({{ anchor }}) < -43200 then 1
        else 0
    end) * interval 1 day)
{%- endmacro %}

{#- The first hh:mm at or after the anchor. -#}
{% macro time_after(anchor, hh, mi) -%}
    {%- set same_day = "(date_trunc('day', " ~ anchor ~ ") + " ~ hours_minutes(hh, mi) ~ ")" -%}
    ({{ same_day }} + (case when {{ same_day }} < {{ anchor }} then 1 else 0 end) * interval 1 day)
{%- endmacro %}
