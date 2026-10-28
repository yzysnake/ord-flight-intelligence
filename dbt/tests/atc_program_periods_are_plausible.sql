-- atc_program leaves a dated period unresolved (null) when it runs backwards, lasts over two days
-- or starts over two days from the send time, as a mistyped day does. That must stay rare: more
-- than a handful and over 0.1 % would mean days or months are resolved wrongly.
with dated as (
    select count(*) filter (where start_utc is null) as unresolved, count(*) as periods
    from {{ ref('atc_program') }}
    where period_format = 'dated'
)

select * from dated where unresolved > 10 and unresolved > 0.001 * periods
