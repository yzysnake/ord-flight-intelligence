-- Nearly every forecast hour must have a prevailing forecast and a flight category. On the full
-- data every hour has one; 0.006 % have no category, where a hand-typed group's visibility is
-- missing or mistyped (e.g. P6VSM). Returns a row if not.
with coverage as (
    select
        avg((prevailing_kind is not null)::int) as with_prevailing,
        avg((flight_category is not null)::int) as with_category
    from {{ ref('taf_hourly') }}
)

select * from coverage where with_prevailing < 0.999 or with_category < 0.999
