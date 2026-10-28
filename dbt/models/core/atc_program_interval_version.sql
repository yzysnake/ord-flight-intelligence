-- Each ORD program as known after each of its advisories (2001 →), for point-in-time use: the
-- program as known at time t is its version with known_time <= t < valid_to (valid_to null: the
-- latest). The last version of each program matches atc_program_interval. A cancellation that
-- came after the program had expired changes nothing and is left out.

with chain as (
    select * from {{ ref('int_atc_program_chain') }}
    where kind != 'cancel' or cancels
),

programs as (
    -- Where the previous program of the chain ended (known before this one began).
    select
        program_id,
        lag(end_utc) over (
            partition by program_type, scope order by first_issued_at, program_id
        ) as previous_end_utc
    from {{ ref('atc_program_interval') }}
),

states as (
    select
        c.*,
        p.previous_end_utc,
        case
            when c.kind = 'cancel' then greatest(c.effective_utc, c.known_start)
            else c.known_end
        end as state_end_utc
    from chain as c
    inner join programs as p using (program_id)
)

select
    program_id,
    airport,
    program_type,
    scope,
    row_number() over versions as version,
    case
        when kind = 'cancel' then 'cancelled'
        when kind = 'partial' then 'partly cancelled'
        when seq = 1 then 'issued'
        when start_utc is null then 'updated'  -- no period stated
        else 'revised'
    end as change,
    adv_date,
    number,
    least(greatest(known_start, previous_end_utc), state_end_utc) as start_utc,
    state_end_utc as end_utc,
    kind = 'cancel' as is_cancelled,
    known_time,
    lead(known_time) over versions as valid_to,
    licence_class
from states
window versions as (partition by program_id order by issued_at, adv_date, number)
order by known_time, program_id
