-- One row per ORD ground delay program or ground stop (2001 →), from its start to its
-- cancellation or end, chained from atc_program's advisories (int_atc_program_chain). GDP periods
-- are arrival times at ORD; ground-stop periods are departure times at the origins it covers.
-- A row is final at known_time; for a program as it was known earlier, use
-- atc_program_interval_version.

with chain as (
    select * from {{ ref('int_atc_program_chain') }}
),

programs as (
    select
        program_id,
        any_value(airport) as airport,
        any_value(program_type) as program_type,
        any_value(scope) as scope,
        min(effective_utc) filter (where kind = 'issued') as start_utc,
        arg_min(end_utc, seq) filter (where kind = 'issued') as planned_end_utc,
        arg_max(end_utc, seq) filter (where kind = 'issued') as latest_end_utc,
        min(effective_utc) filter (where cancels) as cancelled_from,
        min(issued_at) as first_issued_at,
        min(issued_at) filter (where cancels) as cancelled_at,
        max(issued_at) filter (where kind != 'cancel' or cancels) as last_issued_at,
        count(*) filter (where kind = 'issued') as n_advisories,
        -- The lowest hourly arrival rate a GDP advisory set ("76/76/96" is three hours).
        min(list_min(list_transform(
            string_split(program_rate, '/'), lambda rate: try_cast(trim(rate) as integer)
        ))) as min_program_rate,
        max(average_delay_min) as max_average_delay_min,
        max(maximum_delay_min) as max_maximum_delay_min,
        arg_min(title, seq) as title,
        arg_min(reason, seq) as reason,
        any_value(licence_class) as licence_class
    from chain
    group by program_id
),

ended as (
    select
        *,
        case
            when cancelled_from is not null then greatest(cancelled_from, start_utc)
            else latest_end_utc
        end as end_utc,
        case
            when cancelled_from is not null then 'cancelled'
            when latest_end_utc is not null then 'expired'
            else 'unknown'
        end as end_reason
    from programs
),

clipped as (
    -- A stop re-issued just after a cancellation is sometimes backdated before it; it starts at
    -- the cancellation instead, so a chain's programs never overlap.
    select
        * replace (least(greatest(start_utc, previous_end_utc), end_utc) as start_utc)
    from (
        select
            *,
            lag(end_utc) over (
                partition by program_type, scope order by first_issued_at, program_id
            ) as previous_end_utc
        from ended
    )
)

select
    program_id,
    airport,
    program_type,
    scope,
    start_utc,
    end_utc,
    end_reason,
    planned_end_utc,
    (epoch(end_utc) - epoch(start_utc)) / 60 as duration_min,
    first_issued_at,
    cancelled_at,
    last_issued_at,
    n_advisories,
    min_program_rate,
    max_average_delay_min,
    max_maximum_delay_min,
    title,
    reason,
    -- Final once the program has ended (or its last advisory, if later).
    greatest(end_utc, last_issued_at) as known_time,
    licence_class
from clipped
order by start_utc, program_id
