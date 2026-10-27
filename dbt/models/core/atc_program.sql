-- One row per ORD-related ATCSCC traffic-management program advisory (GDP, ground stop, AFP,
-- CTOP): each issuance, revision, proposal and cancellation, with its period parsed to UTC.
-- Programs at other airports (e.g. MDW) appear when their advisories mention ORD, ZAU or C90;
-- filter on `airport`. Resolving advisories into in-effect intervals is left to a later model.

with listed as (
    -- A day's listing can repeat a number: re-sends a minute apart, and occasionally a number
    -- reused for another advisory. Keep the listing whose airport matches the text, then the
    -- latest send (the text we hold is the final version).
    select
        a.*,
        i.category,
        i.title,
        i.control_element,
        i.is_cancellation,
        i.send_time,
        row_number() over (
            partition by a.adv_date, a.number
            order by split_part(i.control_element, '/', 1) = a.ctl_element desc, i.send_time desc
        ) as listing_rank
    from {{ source('stage', 'atcscc_advisories') }} as a
    inner join {{ source('stage', 'atcscc_index') }} as i using (adv_date, number)
),

advisories as (
    select
        adv_date,
        number,
        category as program_type,
        title,
        coalesce(ctl_element, control_element) as ctl_element,
        regexp_extract(coalesce(ctl_element, control_element), '^[A-Z0-9]{3,4}') as airport,
        element_type,
        is_cancellation,
        coalesce(regexp_matches(upper(title), 'PROPOSED'), false) as is_proposed,
        send_time as issued_at,
        send_time as known_time,
        period as period_text,
        program_rate,
        try_cast(regexp_extract(average_delay, '\d+') as integer) as average_delay_min,
        try_cast(regexp_extract(maximum_delay, '\d+') as integer) as maximum_delay_min,
        reason,
        raw_sha256,
        licence_class
    from listed
    where listing_rank = 1 and category in ('gdp', 'ground_stop', 'afp', 'ctop')
),

parts as (
    select
        *,
        -- "11/1246Z - 12/0759Z" (most), also without "Z", spaces or the slash.
        regexp_extract(
            period_text, '(\d{2})/?(\d{2})(\d{2})Z?\s*-\s*(\d{2})/?(\d{2})(\d{2})',
            ['d1', 'h1', 'm1', 'd2', 'h2', 'm2']
        ) as dated,
        -- "1030Z-1130Z": times without days.
        regexp_extract(
            period_text, '^\s*(\d{2})(\d{2})Z?\s*-\s*(\d{2})(\d{2})Z?\b', ['h1', 'm1', 'h2', 'm2']
        ) as undated,
        -- "UNTIL 0100Z": from the advisory's send time.
        regexp_extract(period_text, '^\s*(?:EXTENDED\s+)?UNTIL\s+(\d{2})(\d{2})', ['h', 'm'])
            as until_time
    from advisories
),

periods as (
    select
        *,
        case
            when dated.d1 != '' then 'dated'
            when undated.h1 != '' then 'undated'
            when until_time.h != '' then 'until'
        end as period_format,
        case
            when dated.d1 != ''
                then {{ day_time_near('issued_at', 'dated.d1', 'dated.h1', 'dated.m1') }}
            when undated.h1 != '' then {{ time_near('issued_at', 'undated.h1', 'undated.m1') }}
            when until_time.h != '' then issued_at
        end as start_utc
    from parts
)

select
    adv_date,
    number,
    program_type,
    title,
    airport,
    ctl_element,
    element_type,
    is_cancellation,
    is_proposed,
    issued_at,
    known_time,
    period_text,
    period_format,
    start_utc,
    case period_format
        when 'dated' then {{ day_time_near('start_utc', 'dated.d2', 'dated.h2', 'dated.m2') }}
        when 'undated' then {{ time_after('start_utc', 'undated.h2', 'undated.m2') }}
        when 'until' then {{ time_after('issued_at', 'until_time.h', 'until_time.m') }}
    end as end_utc,
    program_rate,
    average_delay_min,
    maximum_delay_min,
    reason,
    issued_at as valid_time,
    raw_sha256,
    licence_class
from periods
order by issued_at, number
