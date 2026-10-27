-- One row per scheduled ORD departure or arrival. From 2018 the source is the marketing-carrier
-- file, which also covers flights by non-reporting regional operators. For 2015–2017 it is the
-- reporting-carrier file, which misses some carriers in those years (see the BTS data cards).

{%- set shared = [
    'flight_date', 'tail_number', 'origin', 'dest', 'origin_airport_id', 'dest_airport_id',
    'crs_dep_time', 'dep_time', 'crs_arr_time', 'arr_time', 'wheels_off', 'wheels_on',
    'sched_dep_utc', 'sched_arr_utc', 'dep_utc', 'arr_utc', 'wheels_off_utc', 'wheels_on_utc',
    'origin_tz', 'dest_tz', 'dep_delay', 'dep_del15', 'arr_delay', 'arr_del15', 'taxi_out',
    'taxi_in', 'cancelled', 'cancellation_code', 'diverted', 'div_reached_dest', 'div_arr_delay',
    'crs_elapsed_time', 'actual_elapsed_time', 'air_time', 'distance', 'carrier_delay',
    'weather_delay', 'nas_delay', 'security_delay', 'late_aircraft_delay', 'total_add_gtime',
    'raw_sha256', 'known_time', 'licence_class',
] %}

with marketing as (
    select
        'marketing' as source_table,
        operating_airline as operating_carrier,
        flight_number_operating_airline as flight_number,
        marketing_airline_network as marketing_carrier,
        flight_number_marketing_airline as marketing_flight_number,
        {{ shared | join(', ') }}
    from {{ source('stage', 'bts_ontime_marketing') }}
    where origin = 'ORD' or dest = 'ORD'
),

reporting as (
    select
        'reporting' as source_table,
        reporting_airline as operating_carrier,
        flight_number_reporting_airline as flight_number,
        cast(null as varchar) as marketing_carrier,
        cast(null as bigint) as marketing_flight_number,
        {{ shared | join(', ') }}
    from {{ source('stage', 'bts_ontime_reporting') }}
    where (origin = 'ORD' or dest = 'ORD') and flight_date < date '2018-01-01'
),

legs as (
    select * from marketing
    union all
    select * from reporting
)

select
    concat_ws('_', flight_date, operating_carrier, flight_number, origin, dest, crs_dep_time)
        as flight_key,
    case when origin = 'ORD' then 'departure' else 'arrival' end as direction,
    case when origin = 'ORD' then sched_dep_utc else sched_arr_utc end as sched_ord_utc,
    sched_dep_utc as valid_time,
    year(flight_date) as year,
    * exclude (raw_sha256, known_time, licence_class),
    raw_sha256,
    known_time,
    licence_class
from legs
