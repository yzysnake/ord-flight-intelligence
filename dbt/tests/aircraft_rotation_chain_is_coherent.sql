-- The rotation must form a physical chain: almost every leg starts where the aircraft's
-- previous leg ended (about 98 % on the full data), and flown times do not overlap. Returns a
-- row when either rate is off, which points at a broken ordering or tail cleaning.
with rates as (
    select
        avg(station_continuous::int) filter (where prev_flight_key is not null) as continuity,
        avg((actual_ground_min < 0)::int) as flown_overlap
    from {{ ref('aircraft_rotation') }}
)

select * from rates where continuity < 0.97 or flown_overlap > 0.001
