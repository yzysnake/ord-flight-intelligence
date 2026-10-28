-- One row per TAF and hour of its validity window: the prevailing forecast at the start of the
-- hour, plus the TEMPO and PROB overlays touching the hour. Keyed by (product_id, valid_time).
-- The forecast as of time t: rows with known_time <= t, latest issuance per valid hour.

with bulletins as (
    select product_id, station, sent_at, known_time, is_amendment, taf_format, valid_from,
        valid_to, licence_class
    from {{ source('stage', 'iem_taf_bulletins') }}
    where valid_from is not null
),

hours as (
    select *, unnest(range(valid_from, valid_to, interval 1 hour)) as valid_time
    from bulletins
),

prevailing as (
    select * from {{ source('stage', 'iem_taf_periods') }} where role = 'prevailing'
),

overlays as (
    select
        h.product_id,
        h.valid_time,
        min(o.visibility_sm) filter (where o.kind = 'TEMPO') as tempo_visibility_sm,
        min(o.ceiling_ft) filter (where o.kind = 'TEMPO') as tempo_ceiling_ft,
        bool_or(o.has_thunder) filter (where o.kind = 'TEMPO') as tempo_thunder,
        bool_or(o.has_snow) filter (where o.kind = 'TEMPO') as tempo_snow,
        min(o.visibility_sm) filter (where o.kind like 'PROB%') as prob_visibility_sm,
        min(o.ceiling_ft) filter (where o.kind like 'PROB%') as prob_ceiling_ft,
        bool_or(o.has_thunder) filter (where o.kind like 'PROB%') as prob_thunder,
        max(case o.kind when 'PROB30' then 30 when 'PROB40' then 40 end) as prob_pct
    from hours as h
    inner join {{ source('stage', 'iem_taf_periods') }} as o
        on o.product_id = h.product_id
        and o.role = 'overlay'
        and o.start_utc < h.valid_time + interval 1 hour
        and o.end_utc > h.valid_time
    group by all
)

select
    h.station,
    h.product_id,
    h.sent_at,
    h.known_time,
    h.is_amendment,
    h.valid_time,
    (epoch(h.valid_time) - epoch(h.sent_at)) / 3600 as lead_hours,
    p.kind as prevailing_kind,
    p.wind_dir_deg,
    p.wind_variable,
    p.wind_speed_kt,
    p.wind_gust_kt,
    p.visibility_sm,
    p.ceiling_ft,
    p.weather,
    p.has_thunder,
    p.has_snow,
    p.has_freezing,
    p.has_rain,
    p.has_fog,
    p.wind_shear,
    {{ flight_category('p.ceiling_ft', 'p.visibility_sm') }} as flight_category,
    o.* exclude (product_id, valid_time),
    -- The worst category the TAF allows for the hour, TEMPO and PROB groups included.
    {{ flight_category(
        'least(p.ceiling_ft, o.tempo_ceiling_ft, o.prob_ceiling_ft)',
        'least(p.visibility_sm, o.tempo_visibility_sm, o.prob_visibility_sm)'
    ) }} as worst_flight_category,
    h.taf_format,
    h.licence_class
from hours as h
left join prevailing as p
    on p.product_id = h.product_id
    and h.valid_time >= p.start_utc
    and h.valid_time < p.end_utc
left join overlays as o
    on o.product_id = h.product_id
    and o.valid_time = h.valid_time
order by h.valid_time, h.sent_at
