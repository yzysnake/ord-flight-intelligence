-- One row per scheduled ORD departure or arrival (sources and flight key: int_bts_legs).

select
    flight_key,
    case when origin = 'ORD' then 'departure' else 'arrival' end as direction,
    case when origin = 'ORD' then sched_dep_utc else sched_arr_utc end as sched_ord_utc,
    sched_dep_utc as valid_time,
    year(flight_date) as year,
    * exclude (flight_key, raw_sha256, known_time, licence_class),
    raw_sha256,
    known_time,
    licence_class
from {{ ref('int_bts_legs') }}
where origin = 'ORD' or dest = 'ORD'
