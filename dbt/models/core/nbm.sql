-- NBM short-range (NBS) guidance for ORD, one row per cycle and projection: 3-hourly to 72 h
-- ahead (2018-11 →). For the guidance as of time t: rows with known_time <= t, the latest cycle
-- per valid time.
--
-- The bulletin's codes changed with NBM's versions (checked against ORD's METARs): visibility
-- is in whole miles before the 2020-02-20 12Z cycle and in tenths after, with 999 for no
-- forecast; an unlimited ceiling is 888 before v4.0 (2020-09-29) and -88 after. Visibility is
-- capped at 10 miles, as v4.0 does.

with decoded as (
    select
        *,
        case when cig not in (-88, 888) then cig * 100 end as ceiling_ft,  -- null: unlimited
        case
            when vis = 999 then null
            when runtime < '2020-02-20 12:00:00+00'::timestamptz then least(vis::double, 10)
            else least(vis / 10.0, 10)
        end as visibility_mi
    from {{ source('stage', 'iem_mos_nbs') }}
)

select
    station,
    runtime,
    known_time,
    ftime as valid_time,
    (epoch(ftime) - epoch(runtime)) / 3600 as lead_hours,
    ceiling_ft,
    visibility_mi,
    case when cig is not null and visibility_mi is not null
        then {{ flight_category('ceiling_ft', 'visibility_mi') }}
    end as flight_category,
    ifc as ifr_ceiling_pct,
    ifv as ifr_visibility_pct,
    t03 as thunder_3h_pct,
    t06_1 as thunder_6h_pct,
    t12_1 as thunder_12h_pct,
    p06 as pop_6h_pct,
    p12 as pop_12h_pct,
    psn as snow_pct,
    pzr as freezing_pct,
    ppl as sleet_pct,
    pra as rain_pct,
    s06 / 10.0 as snow_6h_in,
    i06 / 100.0 as ice_6h_in,
    wsp as wind_speed_kt,
    gst as wind_gust_kt,
    sky as sky_cover_pct,
    tmp as temp_f,
    dpt as dewpoint_f,
    licence_class
from decoded
