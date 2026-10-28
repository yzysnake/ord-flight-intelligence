-- One row per flown leg of an aircraft (tail number) on each local date on which that aircraft
-- touches ORD, with its previous leg: the inbound aircraft for ORD departures. Tails are the
-- aircraft that actually flew, so legs are ordered by actual departure (the order they were
-- flown), and these links are known only after the fact (see the BTS data cards).

with legs as (
    select
        *,
        coalesce(dep_utc, sched_dep_utc) as flown_order
    from {{ ref('int_bts_legs') }}
    where not cancelled and tail_number is not null
),

ord_days as (
    select distinct tail_number, flight_date
    from legs
    where origin = 'ORD' or dest = 'ORD'
),

scope as (
    -- ORD days plus the day before, so a day's first leg can link to the previous evening.
    select legs.*
    from legs
    semi join (
        select tail_number, flight_date from ord_days
        union
        select tail_number, flight_date - 1 from ord_days
    ) as needed using (tail_number, flight_date)
),

chained as (
    select
        *,
        lag(flight_key) over aircraft as prev_flight_key,
        lag(dest) over aircraft as prev_dest,
        lag(sched_arr_utc) over aircraft as prev_sched_arr_utc,
        lag(arr_utc) over aircraft as prev_arr_utc,
        lag(arr_delay) over aircraft as prev_arr_delay,
        lag(diverted) over aircraft as prev_diverted,
        row_number() over aircraft_day as leg_seq,
        count(*) over (partition by tail_number, flight_date) as legs_in_day
    from scope
    window
        aircraft as (partition by tail_number order by flown_order, sched_dep_utc),
        aircraft_day as (partition by tail_number, flight_date order by flown_order, sched_dep_utc)
)

select
    tail_number,
    flight_date,
    leg_seq,
    legs_in_day,
    flight_key,
    operating_carrier,
    flight_number,
    origin,
    dest,
    origin = 'ORD' or dest = 'ORD' as touches_ord,
    sched_dep_utc,
    sched_arr_utc,
    dep_utc,
    arr_utc,
    dep_delay,
    arr_delay,
    diverted,
    prev_flight_key,
    prev_dest,
    prev_dest = origin as station_continuous,
    prev_sched_arr_utc,
    prev_arr_utc,
    prev_arr_delay,
    prev_diverted,
    date_diff('minute', prev_sched_arr_utc, sched_dep_utc) as sched_ground_min,
    date_diff('minute', prev_arr_utc, dep_utc) as actual_ground_min,
    sched_dep_utc as valid_time,
    known_time,
    licence_class
from chained
semi join ord_days using (tail_number, flight_date)
order by tail_number, flight_date, leg_seq
