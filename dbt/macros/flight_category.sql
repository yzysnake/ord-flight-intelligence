{#- FAA flight category from a ceiling (ft; null = none) and a visibility (statute miles), as
    used by weather_obs (observed) and taf_hourly (forecast). -#}
{% macro flight_category(ceiling_ft, visibility_mi) -%}
    (case
        when {{ ceiling_ft }} is null and {{ visibility_mi }} is null then null
        when {{ ceiling_ft }} < 500 or {{ visibility_mi }} < 1 then 'LIFR'
        when {{ ceiling_ft }} < 1000 or {{ visibility_mi }} < 3 then 'IFR'
        when {{ ceiling_ft }} <= 3000 or {{ visibility_mi }} <= 5 then 'MVFR'
        else 'VFR'
    end)
{%- endmacro %}

{#- Rank of a flight category, worst highest (LIFR 4 .. VFR 1), for taking the worst of several. -#}
{% macro flight_category_rank(category) -%}
    (case {{ category }} when 'LIFR' then 4 when 'IFR' then 3 when 'MVFR' then 2 when 'VFR' then 1 end)
{%- endmacro %}
