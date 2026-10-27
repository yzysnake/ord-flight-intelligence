-- Parsed program periods must run forwards, last under two days and start within two days of
-- the advisory's send time; a failure means the day or month was resolved wrongly.
select adv_date, number, issued_at, period_text, start_utc, end_utc
from {{ ref('atc_program') }}
where end_utc < start_utc
    or end_utc - start_utc > interval 2 day
    or abs(epoch(start_utc) - epoch(issued_at)) > 2 * 86400
