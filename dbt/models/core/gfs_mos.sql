-- GFS MOS (MAV) guidance for ORD, one row per run and projection: 3-hourly, 6 to 72 h ahead
-- (2014-12 →). For the guidance as of time t: rows with known_time <= t, the latest run per
-- valid time.

with ranked as (
    select
        *,
        -- Each element's flight category, worst highest (LIFR 4 .. VFR 1), from the MAV card's
        -- categories: ceiling 1-2 < 500 ft, 3 500-900 ft, 4-5 1000-3000 ft; visibility 1-2
        -- < 1 mi, 3-4 1 to < 3 mi, 5 3-5 mi.
        case when cig <= 2 then 4 when cig = 3 then 3 when cig <= 5 then 2 when cig <= 8 then 1
        end as ceiling_rank,
        case when vis <= 2 then 4 when vis <= 4 then 3 when vis = 5 then 2 when vis <= 7 then 1
        end as visibility_rank
    from {{ source('stage', 'iem_mos_gfs') }}
)

select
    station,
    runtime,
    known_time,
    ftime as valid_time,
    (epoch(ftime) - epoch(runtime)) / 3600 as lead_hours,
    cig as ceiling_category,
    vis as visibility_category,
    case greatest(ceiling_rank, visibility_rank)
        when 4 then 'LIFR' when 3 then 'IFR' when 2 then 'MVFR' when 1 then 'VFR'
    end as flight_category,
    t06_1 as thunder_6h_pct,
    t06_2 as severe_6h_pct,
    t12_1 as thunder_12h_pct,
    p06 as pop_6h_pct,
    p12 as pop_12h_pct,
    pos as snow_pct,
    poz as freezing_pct,
    typ as precip_type,
    snw as snow_24h_category,
    wsp as wind_speed_kt,
    wdr as wind_dir_deg,
    tmp as temp_f,
    dpt as dewpoint_f,
    obv as obstruction,
    licence_class
from ranked
