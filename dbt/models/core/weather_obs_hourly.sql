-- One row per UTC hour, from the first to the last ORD observation: the latest values reported in
-- the hour and the worst conditions seen during it. Hours without observations are kept, with
-- n_obs = 0. An hour's row is complete only at known_time: features as of time t must use
-- rows with known_time <= t, which normally excludes the current hour.

with obs as (
    select * from {{ ref('weather_obs') }}
),

hours as (
    select range as hour
    from range(
        (select date_trunc('hour', min(valid_time)) from obs),
        (select date_trunc('hour', max(valid_time)) + interval 1 hour from obs),
        interval 1 hour
    )
),

by_hour as (
    select
        date_trunc('hour', valid_time) as hour,
        count(*) as n_obs,
        max(known_time) as known_time,
        -- arg_max skips nulls: the latest value reported in the hour.
        arg_max(temp_c, valid_time) as temp_c,
        arg_max(dewpoint_c, valid_time) as dewpoint_c,
        arg_max(wind_dir_deg, valid_time) as wind_dir_deg,
        arg_max(wind_speed_kt, valid_time) as wind_speed_kt,
        arg_max(visibility_mi, valid_time) as visibility_mi,
        arg_max(ceiling_ft, valid_time) as ceiling_ft,
        arg_max(flight_category, valid_time) as flight_category,
        max(wind_speed_kt) as max_wind_speed_kt,
        max(wind_gust_kt) as max_wind_gust_kt,
        min(visibility_mi) as min_visibility_mi,
        min(ceiling_ft) as min_ceiling_ft,
        case max({{ flight_category_rank('flight_category') }})
            when 4 then 'LIFR' when 3 then 'IFR' when 2 then 'MVFR' when 1 then 'VFR'
        end as worst_flight_category,
        bool_or(has_thunder) as any_thunder,
        bool_or(has_snow) as any_snow,
        bool_or(has_freezing) as any_freezing,
        bool_or(has_rain) as any_rain,
        bool_or(has_fog) as any_fog,
        max(precip_in) as precip_in
    from obs
    group by 1
)

select
    hours.hour as valid_time,
    coalesce(by_hour.n_obs, 0) as n_obs,
    by_hour.* exclude (hour, n_obs),
    'public-domain' as licence_class
from hours
left join by_hour on by_hour.hour = hours.hour
order by hours.hour
