-- Every ORD GDP or ground-stop advisory that is not a proposal or cancellation is one version of
-- one program, and each program's last version is the program as atc_program_interval has it.
-- Returns a row per mismatch.
with issued as (
    select count(*) as n
    from {{ ref('atc_program') }}
    where airport = 'ORD'
        and program_type in ('gdp', 'ground_stop')
        and not is_proposed
        and not is_cancellation
),

issued_versions as (
    select count(*) as n
    from {{ ref('atc_program_interval_version') }}
    where change in ('issued', 'revised', 'updated')
),

last_versions as (
    select *
    from {{ ref('atc_program_interval_version') }}
    qualify version = max(version) over (partition by program_id)
)

select 'advisories without a version' as problem, null as program_id
from issued, issued_versions
where issued.n != issued_versions.n

union all

select 'last version differs', p.program_id
from {{ ref('atc_program_interval') }} as p
left join last_versions as v using (program_id)
where v.program_id is null
    or v.start_utc is distinct from p.start_utc
    or v.end_utc is distinct from p.end_utc
