-- Known federal holidays and DST changes; returns the expectations the calendar contradicts.
with expected (date, holiday_observed, dst_change) as (
    values
        (date '2026-01-19', 'Martin Luther King Jr. Day', null),
        (date '2026-02-16', 'Washington''s Birthday', null),
        (date '2026-05-25', 'Memorial Day', null),
        (date '2021-06-18', 'Juneteenth', null),  -- 19 June 2021 was a Saturday
        (date '2020-07-03', 'Independence Day', null),  -- 4 July 2020 was a Saturday
        (date '2026-09-07', 'Labor Day', null),
        (date '2026-10-12', 'Columbus Day', null),
        (date '2026-11-26', 'Thanksgiving Day', null),
        (date '2021-12-31', 'New Year''s Day', null),  -- 1 Jan 2022 was a Saturday
        (date '2026-03-08', null, 'start'),
        (date '2026-11-01', null, 'end'),
        (date '2006-04-02', null, 'start'),  -- before the 2007 rule change
        (date '2006-10-29', null, 'end')
)

select expected.*, calendar.holiday_observed as actual_holiday, calendar.dst_change as actual_dst
from expected
left join {{ ref('calendar') }} as calendar using (date)
where calendar.holiday_observed is distinct from expected.holiday_observed
    or calendar.dst_change is distinct from expected.dst_change
