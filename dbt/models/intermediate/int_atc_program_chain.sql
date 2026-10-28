-- ORD's GDP and ground-stop advisories (proposals left out), each assigned to the program it
-- belongs to. Ephemeral: inlined into atc_program_interval and atc_program_interval_version.
--
-- A chain is one program type and scope. Ground stops limited to one carrier ("EGF ONLY", "UAL
-- SUBS") or to aircraft not cleared for low-visibility approaches ("CAT I") run beside the
-- general ones. Within a chain, a full cancellation closes the open program. Otherwise an
-- advisory continues it when its period starts within 15 minutes of the program's end so far:
-- GDP revisions follow within 5 minutes, and extensions sent after a stop lapsed restart within
-- 15. Each advisory's end supersedes the previous one's, since revisions also shorten programs.

with advisories as (
    select
        *,
        case
            when program_type = 'gdp' then 'general'
            when regexp_matches(
                upper(title),
                '\b(EGF|ENY|EAGLE|UAL|AAL|DAL|NKS|ASQ|BLR|RPA|SKW|CJC|ASH|CHQ|TCF|GJS)\b'
                || '|\bSUBS?\b|SUB ?CARRIER|MAINLINE|EXPRESS'
            ) then 'carrier'
            when regexp_matches(upper(title), '\bCAT(EGORY)?\s*(I|1)\b') then 'equipment'
            else 'general'
        end as scope,
        -- When the advisory takes effect: its period's start, else its send time.
        coalesce(start_utc, issued_at) as effective_utc
    from {{ ref('atc_program') }}
    where airport = 'ORD' and program_type in ('gdp', 'ground_stop') and not is_proposed
),

kinds as (
    select
        *,
        case
            when not is_cancellation then 'issued'
            -- "PARTIAL ... CANCELLATION", "CNX FOR ZBW/ZDC/ZNY/CZY": some facilities released.
            when scope = 'general' and regexp_matches(
                upper(title), 'PARTIAL|\b(CNX|CANCELL?ED|CANCELLATION)\s+FOR\b'
            ) then 'partial'
            else 'cancel'
        end as kind
    from advisories
),

grouped as (
    -- A full cancellation closes its chain's open program: later advisories form a new group.
    select
        *,
        coalesce(sum((kind = 'cancel')::int) over (
            partition by program_type, scope order by issued_at, adv_date, number
            rows between unbounded preceding and 1 preceding
        ), 0) as cancel_group
    from kinds
),

linked as (
    -- How long the group's latest program runs, as stated before each advisory: its last end,
    -- or the last advisory's time if later (an update with no period).
    select
        *,
        greatest(
            last_value(case when kind = 'issued' then end_utc end ignore nulls) over earlier,
            max(case when kind = 'issued' then effective_utc end) over earlier
        ) as open_until
    from grouped
    window earlier as (
        partition by program_type, scope, cancel_group order by issued_at, adv_date, number
        rows between unbounded preceding and 1 preceding
    )
),

islands as (
    select
        *,
        sum((kind = 'issued' and (
            open_until is null or effective_utc > open_until + interval 15 minute
        ))::int) over (
            partition by program_type, scope, cancel_group order by issued_at, adv_date, number
            rows between unbounded preceding and current row
        ) as island
    from linked
),

members as (
    -- Partial or repeated cancellations with no program open (island 0) are dropped.
    select
        *,
        first_value(adv_date) over program as first_adv_date,
        first_value(number) over program as first_number,
        row_number() over program as seq,
        -- The program as stated up to this advisory.
        min(case when kind = 'issued' then effective_utc end) over program as known_start,
        last_value(case when kind = 'issued' then end_utc end ignore nulls) over program
            as known_end
    from islands
    where island > 0
    window program as (
        partition by program_type, scope, cancel_group, island
        order by issued_at, adv_date, number
        rows between unbounded preceding and current row
    )
)

select
    concat_ws(
        '-', airport, program_type, strftime(first_adv_date, '%Y%m%d'),
        lpad(first_number::varchar, 3, '0')
    ) as program_id,
    airport,
    program_type,
    scope,
    seq,
    kind,
    -- A cancellation ends the program when it takes effect before the program's end (or up to
    -- 15 minutes after: stops are often released a little late). A later one confirms an expiry.
    kind = 'cancel' and (known_end is null or effective_utc <= known_end + interval 15 minute)
        as cancels,
    adv_date,
    number,
    title,
    issued_at,
    known_time,
    period_text,
    start_utc,
    end_utc,
    effective_utc,
    known_start,
    known_end,
    program_rate,
    average_delay_min,
    maximum_delay_min,
    reason,
    licence_class
from members
