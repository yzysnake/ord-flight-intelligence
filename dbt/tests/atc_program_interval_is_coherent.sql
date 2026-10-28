-- Programs must run forwards, last less than 36 hours (GDPs) or 24 hours (ground stops) and not
-- overlap within their chain. Only programs whose advisories state no time may lack an end, and
-- few may: not more than a handful and 1 % (0.4 % on the full data). Returns a row if any check
-- fails.
with programs as (
    select
        *,
        lag(end_utc) over (
            partition by program_type, scope order by first_issued_at, program_id
        ) as previous_end_utc
    from {{ ref('atc_program_interval') }}
),

checks as (
    select
        count(*) filter (where end_utc < start_utc) as backwards,
        count(*) filter (where start_utc < previous_end_utc) as overlapping,
        count(*) filter (
            where duration_min > case program_type when 'gdp' then 36 * 60 else 24 * 60 end
        ) as too_long,
        count(*) filter (where (end_utc is null) != (end_reason = 'unknown')) as unexplained_ends,
        count(*) filter (where known_time < first_issued_at) as known_too_early,
        count(*) filter (where end_reason = 'unknown') as unknown,
        count(*) as programs
    from programs
)

select * from checks
where backwards > 0
    or overlapping > 0
    or too_long > 0
    or unexplained_ends > 0
    or known_too_early > 0
    or unknown > 10 and unknown > 0.01 * programs
