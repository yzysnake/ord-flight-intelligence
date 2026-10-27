-- One row per ORD METAR (routine and special; 5-minute HFMETAR rows stay in stage), with ceiling,
-- flight category and present-weather flags. Use both report types together: IEM's labels are
-- unreliable in 2001 and Jan–Jul 2006 (see the iem_asos_metar card).

with obs as (
    select *
    from {{ source('stage', 'iem_asos_metar') }}
    where station = 'ORD' and report_type in ('routine', 'special')
),

sky as (
    select
        *,
        -- Ceiling: the lowest broken, overcast or vertical-visibility layer (least skips nulls).
        least(
            case when skyc1 in ('BKN', 'OVC', 'VV') then skyl1 end,
            case when skyc2 in ('BKN', 'OVC', 'VV') then skyl2 end,
            case when skyc3 in ('BKN', 'OVC', 'VV') then skyl3 end,
            case when skyc4 in ('BKN', 'OVC', 'VV') then skyl4 end
        ) as ceiling_ft
    from obs
)

select
    station,
    valid as valid_time,
    known_time,
    report_type,
    (tmpf - 32) * 5 / 9 as temp_c,
    (dwpf - 32) * 5 / 9 as dewpoint_c,
    relh as rel_humidity_pct,
    drct as wind_dir_deg,
    sknt as wind_speed_kt,
    gust as wind_gust_kt,
    vsby as visibility_mi,
    ceiling_ft,
    -- FAA categories; a missing ceiling means none reported (unlimited).
    case
        when ceiling_ft is null and vsby is null then null
        when ceiling_ft < 500 or vsby < 1 then 'LIFR'
        when ceiling_ft < 1000 or vsby < 3 then 'IFR'
        when ceiling_ft <= 3000 or vsby <= 5 then 'MVFR'
        else 'VFR'
    end as flight_category,
    wxcodes,
    coalesce(regexp_matches(wxcodes, 'TS'), false) as has_thunder,  -- includes VCTS (vicinity)
    coalesce(regexp_matches(wxcodes, 'SN'), false) as has_snow,
    coalesce(regexp_matches(wxcodes, 'FZ'), false) as has_freezing,
    coalesce(regexp_matches(wxcodes, 'RA|DZ'), false) as has_rain,
    coalesce(regexp_matches(wxcodes, 'FG|BR'), false) as has_fog,
    p01i as precip_in,  -- since the last routine report; trace = 0.0001
    ice_accretion_1hr as ice_accretion_1h_in,
    snowdepth as snow_depth_in,
    peak_wind_gust as peak_wind_gust_kt,
    peak_wind_drct as peak_wind_dir_deg,
    peak_wind_time,
    metar,
    raw_sha256,
    licence_class
from sky
