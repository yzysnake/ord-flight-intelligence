-- One row per date, 2000-01-01 .. 2030-12-31: weekday fields, US federal holidays (actual and
-- observed dates), days to the next and since the previous holiday, and America/Chicago DST.

with days as (
    select cast(range as date) as date
    from range(date '2000-01-01', date '2031-01-01', interval 1 day)
),

years as (
    -- One extra year on each side, so every date has a previous and a next holiday.
    select range as year from range(1999, 2032)
),

holiday_dates as (
    select 'New Year''s Day' as holiday, make_date(year, 1, 1) as actual_date, true as fixed
    from years
    union all
    select 'Martin Luther King Jr. Day', {{ nth_weekday('year', 1, 1, 3) }}, false from years
    union all
    select 'Washington''s Birthday', {{ nth_weekday('year', 2, 1, 3) }}, false from years
    union all
    select 'Memorial Day', {{ last_weekday('year', 5, 1) }}, false from years
    union all
    select 'Juneteenth', make_date(year, 6, 19), true from years where year >= 2021
    union all
    select 'Independence Day', make_date(year, 7, 4), true from years
    union all
    select 'Labor Day', {{ nth_weekday('year', 9, 1, 1) }}, false from years
    union all
    select 'Columbus Day', {{ nth_weekday('year', 10, 1, 2) }}, false from years
    union all
    select 'Veterans Day', make_date(year, 11, 11), true from years
    union all
    select 'Thanksgiving Day', {{ nth_weekday('year', 11, 4, 4) }}, false from years
    union all
    select 'Christmas Day', make_date(year, 12, 25), true from years
),

holidays as (
    select
        holiday,
        actual_date,
        case when fixed then {{ observed('actual_date') }} else actual_date end as observed_date
    from holiday_dates
),

chicago as (
    select
        date,
        -- UTC offset at local noon: the day's offset after any 02:00 transition.
        cast(
            (epoch(date::timestamp + interval 12 hour)
                - epoch(timezone('America/Chicago', date::timestamp + interval 12 hour))) / 3600
            as integer
        ) as utc_offset_hours
    from days
)

select
    days.date,
    year(days.date) as year,
    quarter(days.date) as quarter,
    month(days.date) as month,
    day(days.date) as day_of_month,
    isodow(days.date) as day_of_week,
    dayname(days.date) as day_name,
    isodow(days.date) >= 6 as is_weekend,
    weekofyear(days.date) as iso_week,
    dayofyear(days.date) as day_of_year,
    actual.holiday,
    observed.holiday as holiday_observed,
    observed.holiday is not null as is_holiday_observed,
    next_holiday.holiday as next_holiday,
    cast(next_holiday.actual_date - days.date as integer) as days_to_holiday,
    previous_holiday.holiday as previous_holiday,
    cast(days.date - previous_holiday.actual_date as integer) as days_since_holiday,
    chicago.utc_offset_hours,
    chicago.utc_offset_hours = -5 as is_dst,
    case
        when chicago.utc_offset_hours > lag(chicago.utc_offset_hours) over (order by days.date)
            then 'start'
        when chicago.utc_offset_hours < lag(chicago.utc_offset_hours) over (order by days.date)
            then 'end'
    end as dst_change
from days
inner join chicago using (date)
left join holidays as actual on actual.actual_date = days.date
left join holidays as observed on observed.observed_date = days.date
asof left join holidays as next_holiday on days.date <= next_holiday.actual_date
asof left join holidays as previous_holiday on days.date >= previous_holiday.actual_date
order by days.date
