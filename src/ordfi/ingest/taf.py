"""TAF bulletin parser: raw NWS bulletins (current and pre-2008 formats) into forecast periods.

Input is the monthly bulletin text fetched by ``ordfi.ingest.iem`` (IEM's AFOS archive; products
are separated by SOH/ETX and listed in the order they were received). For each bulletin:

- **times** are resolved from its WMO header, which is when it was sent and so its knowledge
  time. Day-of-month fields resolve to the month nearest the previous bulletin;
- **validity** is ``DDHH/DDHH`` (current format, 5 Nov 2008 on) or ``DDHHHH`` (old, 24 h). An
  end hour of 24 means midnight, and windows may end in the next month;
- **groups**: the initial conditions and ``FM`` groups restate every element. ``BECMG`` changes
  only the elements it gives, from its start. ``TEMPO`` and ``PROB30/40`` are overlays with only
  their own elements. Old-format group times (``FMHHMM``, ``TEMPO HHHH``) resolve forward
  from the previous group.

Tokens that cannot be read are kept per group (``unparsed``) rather than guessed. Common typos
(letter O for zero, ``KTKT``) are repaired. A bulletin without a readable validity window has
no periods.
"""

from __future__ import annotations

import calendar
import os
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl

from ordfi.ingest.raw import LicenceClass, load_latest

SOURCE_ID = "iem_taf"
LICENCE: LicenceClass = "public-domain"
KNOWLEDGE_LAG = timedelta(minutes=10)  # IEM's archive latency, as for the other IEM products
MAX_WINDOW = timedelta(hours=36)
OVERLAYS = ("TEMPO", "PROB30", "PROB40")

_WMO = re.compile(r"^([A-Z]{4}\d{2}) ([A-Z]{4}) (\d{2})(\d{2})(\d{2})(?: ([A-Z]{3}))?")
_ISSUE = re.compile(r"^\d{4,7}Z{0,2}$")
_VALID_NEW = re.compile(r"^(\d{2})(\d{2})/(\d{2})(\d{2})$")
_VALID_OLD = re.compile(r"^(\d{2})(\d{2})(\d{2})$")
_FM_NEW = re.compile(r"^FM(\d{2})(\d{2})(\d{2})$")
_FM_OLD = re.compile(r"^FM(\d{2})(\d{2})$")
_SPAN_OLD = re.compile(r"^(\d{2})(\d{2})$")
_WIND = re.compile(r"^(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT$")
_VIS_WHOLE = re.compile(r"^(P|M)?(\d{1,2})SM$")
_VIS_FRACTION = re.compile(r"^(M)?(\d)/(\d{1,2})SM$")
_SKY = re.compile(r"^(FEW|SCT|BKN|OVC)([0-9O]{3})(CB|TCU)?$")
_VERTICAL = re.compile(r"^VV(\d{3})$")
_SHEAR = re.compile(r"^WS\d{3}/\d{5,6}KT$")
_WEATHER = re.compile(
    r"^(\+|-|VC)?((MI|PR|BC|DR|BL|SH|TS|FZ)"
    r"|(DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS))+$"
)


@dataclass(frozen=True)
class Conditions:
    """Forecast elements; ``None`` means not stated (overlays and BECMG state only changes)."""

    wind_dir_deg: int | None = None
    wind_variable: bool | None = None
    wind_speed_kt: int | None = None
    wind_gust_kt: int | None = None
    visibility_sm: float | None = None
    weather: tuple[str, ...] | None = None  # () = none forecast
    sky: tuple[tuple[str, int], ...] | None = None  # () = clear
    wind_shear: bool | None = None

    @property
    def ceiling_ft(self) -> int | None:
        """Lowest broken, overcast or vertical-visibility layer; ``None`` if none (or unstated)."""
        bases = [base for cover, base in self.sky or () if cover in ("BKN", "OVC", "VV")]
        return min(bases, default=None)

    def updated(self, change: Conditions) -> Conditions:
        """These conditions with every element that ``change`` states replaced."""
        stated = {name: value for name, value in vars(change).items() if value is not None}
        return replace(self, **stated)

    def restated(self) -> Conditions:
        """An initial or FM group restates everything: unstated weather or shear means none."""
        return replace(
            self,
            weather=() if self.weather is None else self.weather,
            wind_shear=False if self.wind_shear is None else self.wind_shear,
        )


@dataclass(frozen=True)
class Group:
    kind: str  # initial, FM, BECMG, TEMPO, PROB30, PROB40 ("PROBnn TEMPO" is kept as PROBnn)
    start: datetime
    end: datetime | None  # given for BECMG and overlays; prevailing ends are derived
    conditions: Conditions
    text: str
    unparsed: tuple[str, ...] = ()


@dataclass(frozen=True)
class Bulletin:
    sent_at: datetime
    wmo_header: str
    bbb: str | None
    awips_id: str
    is_amendment: bool
    is_correction: bool
    text: str
    taf_format: str | None = None  # "current", "old", or None when the validity is unreadable
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    groups: tuple[Group, ...] = ()

    @property
    def product_id(self) -> str:
        """IEM's product id (``YYYYMMDDHHMM-CCCC-TTAAII-AWIPS[-BBB]``), for joining its tables."""
        ttaaii, center = self.wmo_header.split()[:2]
        suffix = f"-{self.bbb}" if self.bbb else ""
        return f"{self.sent_at:%Y%m%d%H%M}-{center}-{ttaaii}-{self.awips_id}{suffix}"

    @property
    def defects(self) -> int:
        """Unreadable tokens, with an unreadable window counted as worse than any number."""
        unparsed = sum(len(group.unparsed) for group in self.groups)
        return unparsed if self.taf_format else 10**6


def keep_cleaner(bulletins: dict[str, Bulletin], bulletin: Bulletin) -> None:
    """Add ``bulletin``, or replace an earlier copy of the same product if this one is cleaner.

    The same TAF often arrives twice (via different feeds) with small transmission errors.
    """
    earlier = bulletins.get(bulletin.product_id)
    if earlier is None or bulletin.defects <= earlier.defects:
        bulletins[bulletin.product_id] = bulletin


# --- time resolution ------------------------------------------------------------------------


def _at(year: int, month: int, day: int, hour: int, minute: int) -> datetime | None:
    if not 1 <= day <= calendar.monthrange(year, month)[1] or hour > 24 or minute > 59:
        return None
    return datetime(year, month, day, tzinfo=UTC) + timedelta(hours=hour, minutes=minute)


def resolve_day_time(anchor: datetime, day: int, hour: int, minute: int = 0) -> datetime | None:
    """Day ``day`` at ``hour:minute`` UTC, in whichever of the three months around ``anchor``
    puts it nearest the anchor. Hour 24 is midnight at the end of the day."""
    candidates = []
    for offset in (-1, 0, 1):
        months = anchor.year * 12 + anchor.month - 1 + offset
        moment = _at(months // 12, months % 12 + 1, day, hour, minute)
        if moment is not None:
            candidates.append(moment)
    return min(candidates, key=lambda moment: abs(moment - anchor), default=None)


def next_time(after: datetime, hour: int, minute: int = 0, *, strict: bool = False) -> datetime:
    """The first ``hour:minute`` at or after (``strict``: after) ``after``; hour 24 is midnight."""
    moment = after.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)
    if moment < after or (strict and moment == after):
        moment += timedelta(days=1)
    return moment


# --- elements -------------------------------------------------------------------------------


def _repair(token: str) -> str:
    """Fix typing slips in numeric groups: letter O for zero, a doubled KT."""
    if token.endswith("KT") and not token.startswith("WS"):
        token = re.sub(r"(KT)+$", "", token)
        head = "VRB" if token.startswith("VRB") else token[:3].replace("O", "0")
        return head + token[3:].replace("O", "0") + "KT"
    if layer := _SKY.match(token):
        return layer.group(1) + layer.group(2).replace("O", "0") + (layer.group(3) or "")
    return token


def parse_conditions(tokens: list[str]) -> tuple[Conditions, tuple[str, ...]]:
    """Elements stated in a group's tokens, and the tokens that could not be read."""
    wind: tuple[int | None, bool, int, int] | None = None
    visibility: float | None = None
    weather: list[str] = []
    no_weather = False
    sky: list[tuple[str, int]] = []
    clear = False
    shear: bool | None = None
    unparsed: list[str] = []
    index = 0
    while index < len(tokens):
        token = _repair(tokens[index])
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        fraction = _VIS_FRACTION.match(following)
        if match := _WIND.match(token):
            variable = match.group(1) == "VRB"
            gust = int(match.group(3)) if match.group(3) else 0
            wind = (None if variable else int(match.group(1)), variable, int(match.group(2)), gust)
        elif token.isdigit() and len(token) == 1 and fraction:  # "1 1/2SM"
            visibility = int(token) + int(fraction.group(2)) / int(fraction.group(3))
            index += 1
        elif match := _VIS_WHOLE.match(token):
            visibility = float(match.group(2)) + (0.01 if match.group(1) == "P" else 0.0)
        elif match := _VIS_FRACTION.match(token):
            visibility = int(match.group(2)) / int(match.group(3))
        elif token in ("SKC", "CLR", "NSC"):
            clear = True
        elif match := _SKY.match(token):
            sky.append((match.group(1), int(match.group(2)) * 100))
        elif match := _VERTICAL.match(token):
            sky.append(("VV", int(match.group(1)) * 100))
        elif _SHEAR.match(token):
            shear = True
        elif token == "NSW":
            no_weather = True
        elif _WEATHER.match(token):
            weather.append(token)
        else:
            unparsed.append(tokens[index])
        index += 1
    conditions = Conditions(
        wind_dir_deg=wind[0] if wind else None,
        wind_variable=wind[1] if wind else None,
        wind_speed_kt=wind[2] if wind else None,
        wind_gust_kt=wind[3] if wind else None,
        visibility_sm=visibility,
        weather=tuple(weather) if weather else (() if no_weather else None),
        sky=tuple(sky) if sky else (() if clear else None),
        wind_shear=shear,
    )
    return conditions, tuple(unparsed)


# --- bulletins ------------------------------------------------------------------------------


def split_products(text: str) -> list[str]:
    """The products of one AFOS text file, in the order received."""
    products = (part.replace("\x03", "").strip() for part in text.split("\x01"))
    return [product for product in products if product]


def _span(token: str, anchor: datetime) -> tuple[datetime, datetime] | None:
    """A current-format ``DDHH/DDHH`` span near ``anchor``."""
    match = _VALID_NEW.match(token)
    if not match:
        return None
    start_day, start_hour, end_day, end_hour = (int(part) for part in match.groups())
    start = resolve_day_time(anchor, start_day, start_hour)
    end = None if start is None else resolve_day_time(start, end_day, end_hour)
    if start is None or end is None or not timedelta(0) < end - start <= MAX_WINDOW:
        return None
    return start, end


def _window(token: str, sent: datetime) -> tuple[str, datetime, datetime] | None:
    """The validity window: format, start and end."""
    if span := _span(token, sent):
        return ("current", *span)
    if old := _VALID_OLD.match(token):
        start = resolve_day_time(sent, int(old.group(1)), int(old.group(2)))
        if start is not None:
            return "old", start, next_time(start, int(old.group(3)), strict=True)
    return None


def _group_times(
    marker: str, span: str | None, taf_format: str, anchor: datetime, valid_from: datetime
) -> tuple[datetime, datetime | None] | None:
    """A group's start and (for BECMG and overlays) end, or ``None`` if unreadable.

    Old-format times resolve forward from ``anchor`` (the latest group start so far). Spans at
    the very start may begin up to two hours before the window (amendments issued at 22:03
    with "TEMPO 2101"), so there the search starts two hours early.
    """
    earliest = anchor - timedelta(hours=2) if anchor == valid_from else anchor
    if marker.startswith("FM"):
        if taf_format == "current" and (match := _FM_NEW.match(marker)):
            start = resolve_day_time(anchor, *(int(part) for part in match.groups()))
            return None if start is None else (start, None)
        if taf_format == "old" and (match := _FM_OLD.match(marker)):
            return next_time(anchor, int(match.group(1)), int(match.group(2))), None
        return None
    if span is None:
        return None
    if taf_format == "current":
        return _span(span, anchor)
    if match := _SPAN_OLD.match(span):
        start = next_time(earliest, int(match.group(1)))
        return start, next_time(start, int(match.group(2)), strict=True)
    return None


def _segments(tokens: list[str]) -> list[tuple[str, str | None, list[str]]]:
    """Body tokens as (marker, span, element tokens); the first segment is the initial group."""
    segments: list[tuple[str, str | None, list[str]]] = [("initial", None, [])]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("FM") and token[2:].isdigit():
            segments.append((token, None, []))
        elif token in ("BECMG", *OVERLAYS):
            index += 1
            if token.startswith("PROB") and index < len(tokens) and tokens[index] == "TEMPO":
                index += 1
            segments.append((token, tokens[index] if index < len(tokens) else None, []))
        else:
            segments[-1][2].append(token)
        index += 1
    return segments


def _body(words: list[str], awips: str, station: str) -> tuple[set[str], list[str]]:
    """Leading header words (TAF, AMD, COR, station) and the rest, minus the stated issue time."""
    lead = {"TAF", "AMD", "COR", "CCA", awips, f"K{station}", station}
    flags: set[str] = set()
    index = 0
    while index < len(words) and words[index].lstrip("|") in lead:
        flags.add(words[index].lstrip("|"))
        index += 1
    body = words[index:]
    if body and _ISSUE.match(body[0]) and not _VALID_OLD.match(body[0]):
        body = body[1:]  # the TAF's own issue time (the WMO header time is used instead)
    elif (
        len(body) > 1
        and _VALID_OLD.match(body[0])
        and (_VALID_OLD.match(body[1]) or _VALID_NEW.match(body[1]))
    ):
        body = body[1:]  # an issue time missing its "Z", followed by the validity
    return flags, body


def parse_bulletin(product: str, anchor: datetime, station: str = "ORD") -> Bulletin | None:
    """One bulletin; ``anchor`` is a time near its sending (e.g. the previous bulletin's)."""
    lines = product.splitlines()
    start = next((i for i, line in enumerate(lines) if _WMO.match(line.strip())), None)
    header = _WMO.match(lines[start].strip()) if start is not None else None
    if start is None or header is None:
        return None
    day, hour, minute = (int(header.group(n)) for n in (3, 4, 5))
    sent = resolve_day_time(anchor, day, hour, minute)
    if sent is None:
        return None
    bbb = header.group(6)
    # A product can hold several stations' TAFs (old collectives), each ending with "=".
    sections = " ".join(lines[start + 1 :]).split("=")
    station_word = re.compile(rf"(^|\s)\|?K{station}(\s|$)")
    words = next((s for s in sections if station_word.search(s)), sections[0]).split()
    first = sections[0].split()
    awips = next((word for word in first[:2] if re.fullmatch(r"TAF[A-Z0-9]{3}", word)),
                 f"TAF{station}")  # fmt: skip
    flags, body = _body(words, awips, station)
    bulletin = Bulletin(
        sent_at=sent, wmo_header=header.group(0), bbb=bbb, awips_id=awips,
        is_amendment="AMD" in flags or (bbb or "").startswith("AA"),
        is_correction=bool({"COR", "CCA"} & flags) or (bbb or "").startswith("CC"),
        text=product,
    )  # fmt: skip
    window = _window(body[0], sent) if body else None
    if window is None:
        return bulletin
    taf_format, valid_from, valid_to = window
    groups: list[Group] = []
    latest = valid_from
    for marker, span, tokens in _segments(body[1:]):
        times = (valid_from, None) if marker == "initial" else _group_times(
            marker, span, taf_format, latest, valid_from
        )  # fmt: skip
        if times is None:  # unreadable group time: the group is dropped
            continue
        conditions, unparsed = parse_conditions(tokens)
        latest = max(latest, times[0])
        kind = "FM" if marker.startswith("FM") else marker
        parts = [*([] if marker == "initial" else [marker]), *([span] if span else []), *tokens]
        groups.append(Group(kind, times[0], times[1], conditions, " ".join(parts), unparsed))
    return replace(bulletin, taf_format=taf_format, valid_from=valid_from, valid_to=valid_to,
                   groups=tuple(groups))  # fmt: skip


def parse_file(text: str, month_start: datetime, station: str = "ORD") -> list[Bulletin]:
    """A month's bulletins, each resolved against the previous one; re-sends kept once."""
    bulletins: dict[str, Bulletin] = {}
    anchor = month_start
    for product in split_products(text):
        bulletin = parse_bulletin(product, anchor, station)
        if bulletin is None:
            continue
        keep_cleaner(bulletins, bulletin)
        if abs(bulletin.sent_at - anchor) < timedelta(days=3):  # ignore stray out-of-order ones
            anchor = bulletin.sent_at
    return list(bulletins.values())


# --- periods --------------------------------------------------------------------------------


def periods(bulletin: Bulletin) -> list[dict[str, object]]:
    """Prevailing periods (the state after each initial, FM and BECMG group) and overlays."""
    if bulletin.valid_from is None or bulletin.valid_to is None:
        return []
    state = Conditions()
    prevailing: list[tuple[Group, Conditions]] = []
    for group in bulletin.groups:
        if group.kind in ("initial", "FM"):
            state = group.conditions.restated()
            prevailing.append((group, state))
        elif group.kind == "BECMG":
            state = state.updated(group.conditions)
            prevailing.append((group, state))
    rows: list[dict[str, object]] = []
    # In time order (text order breaks ties); of groups starting together, the last one stands.
    ordered = [
        item for _, item in sorted(enumerate(prevailing), key=lambda e: (e[1][0].start, e[0]))
    ]
    starts = [group.start for group, _ in ordered]
    for position, (group, conditions) in enumerate(ordered):
        if position + 1 < len(ordered) and starts[position + 1] == group.start:
            continue
        end = min([*(start for start in starts[position + 1 :] if start > group.start),
                   bulletin.valid_to])  # fmt: skip
        if end > group.start:
            rows.append(_row(bulletin, group, conditions, "prevailing", group.start, end))
    for group in bulletin.groups:
        if group.kind in OVERLAYS and group.end is not None:
            rows.append(_row(bulletin, group, group.conditions, "overlay", group.start, group.end))
    return rows


def _row(
    bulletin: Bulletin, group: Group, conditions: Conditions, role: str, start: datetime,
    end: datetime,
) -> dict[str, object]:  # fmt: skip
    weather, sky = conditions.weather, conditions.sky

    def has(pattern: str) -> bool | None:
        return None if weather is None else any(re.search(pattern, code) for code in weather)

    return {
        "product_id": bulletin.product_id, "sent_at": bulletin.sent_at, "kind": group.kind,
        "role": role, "start_utc": start, "end_utc": end,
        "wind_dir_deg": conditions.wind_dir_deg, "wind_variable": conditions.wind_variable,
        "wind_speed_kt": conditions.wind_speed_kt, "wind_gust_kt": conditions.wind_gust_kt,
        "visibility_sm": conditions.visibility_sm,
        "weather": None if weather is None else list(weather),
        "sky_cover": None if sky is None else [cover for cover, _ in sky],
        "sky_base_ft": None if sky is None else [base for _, base in sky],
        "ceiling_ft": conditions.ceiling_ft,
        "has_thunder": has("TS"), "has_snow": has("SN"), "has_freezing": has("FZ"),
        "has_rain": has("RA|DZ"), "has_fog": has("FG|BR"), "wind_shear": conditions.wind_shear,
        "group_text": group.text, "unparsed": list(group.unparsed),
        "taf_format": bulletin.taf_format,
    }  # fmt: skip


# --- staging --------------------------------------------------------------------------------

UTC_TS = pl.Datetime("us", "UTC")
BULLETIN_SCHEMA = pl.Schema(
    {
        "station": pl.String(),
        "product_id": pl.String(),
        "sent_at": UTC_TS,
        "known_time": UTC_TS,
        "wmo_header": pl.String(),
        "bbb": pl.String(),
        "is_amendment": pl.Boolean(),
        "is_correction": pl.Boolean(),
        "taf_format": pl.String(),
        "valid_from": UTC_TS,
        "valid_to": UTC_TS,
        "n_groups": pl.Int32(),
        "n_unparsed": pl.Int32(),
        "text": pl.String(),
        "raw_sha256": pl.String(),
    }
)
PERIOD_SCHEMA = pl.Schema(
    {
        "product_id": pl.String(),
        "sent_at": UTC_TS,
        "kind": pl.String(),
        "role": pl.String(),
        "start_utc": UTC_TS,
        "end_utc": UTC_TS,
        "wind_dir_deg": pl.Int32(),
        "wind_variable": pl.Boolean(),
        "wind_speed_kt": pl.Int32(),
        "wind_gust_kt": pl.Int32(),
        "visibility_sm": pl.Float64(),
        "weather": pl.List(pl.String()),
        "sky_cover": pl.List(pl.String()),
        "sky_base_ft": pl.List(pl.Int32()),
        "ceiling_ft": pl.Int32(),
        "has_thunder": pl.Boolean(),
        "has_snow": pl.Boolean(),
        "has_freezing": pl.Boolean(),
        "has_rain": pl.Boolean(),
        "has_fog": pl.Boolean(),
        "wind_shear": pl.Boolean(),
        "group_text": pl.String(),
        "unparsed": pl.List(pl.String()),
        "taf_format": pl.String(),
    }
)


def _write(frame: pl.DataFrame, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(".data.parquet.tmp")
    frame.write_parquet(tmp, compression="zstd")
    os.replace(tmp, target)
    return target


def stage_path(table: str, station: str, year: int, data_root: Path) -> Path:
    return (data_root / "stage" / SOURCE_ID / table / f"station={station}" / f"year={year:04d}"
            / "data.parquet")  # fmt: skip


def stage_year(
    data_root: Path, year: int, station: str = "ORD"
) -> tuple[Path, Path, dict[str, int]]:
    """Parse a station-year of raw bulletins into the ``bulletins`` and ``periods`` tables."""
    parsed: dict[str, tuple[Bulletin, str]] = {}  # product id → (bulletin, raw file checksum)
    for key, record in sorted(load_latest(data_root, SOURCE_ID).items()):
        key_station, kind, month = key.split("/")
        if key_station != station or kind != "bulletins" or not month.startswith(f"{year:04d}-"):
            continue
        month_start = datetime.combine(date.fromisoformat(f"{month}-01"), datetime.min.time(), UTC)
        text = (data_root / record.path).read_text(encoding="latin-1")
        for bulletin in parse_file(text, month_start, station):
            earlier = parsed.get(bulletin.product_id)  # a re-send can land in the next month
            if earlier is None or bulletin.defects <= earlier[0].defects:
                parsed[bulletin.product_id] = (bulletin, record.sha256)
    bulletin_rows: list[dict[str, object]] = []
    period_rows: list[dict[str, object]] = []
    for bulletin, sha256 in parsed.values():
        period_rows.extend(periods(bulletin))
        bulletin_rows.append({
            "station": station, "product_id": bulletin.product_id,
            "sent_at": bulletin.sent_at, "known_time": bulletin.sent_at + KNOWLEDGE_LAG,
            "wmo_header": bulletin.wmo_header, "bbb": bulletin.bbb,
            "is_amendment": bulletin.is_amendment, "is_correction": bulletin.is_correction,
            "taf_format": bulletin.taf_format, "valid_from": bulletin.valid_from,
            "valid_to": bulletin.valid_to, "n_groups": len(bulletin.groups),
            "n_unparsed": sum(len(group.unparsed) for group in bulletin.groups),
            "text": bulletin.text, "raw_sha256": sha256,
        })  # fmt: skip
    bulletins = pl.DataFrame(bulletin_rows, schema=BULLETIN_SCHEMA).with_columns(
        licence_class=pl.lit(LICENCE)
    )
    period_frame = (
        pl.DataFrame(period_rows, schema=PERIOD_SCHEMA)
        .join(bulletins.select("product_id", "known_time"), on="product_id", how="left")
        .with_columns(station=pl.lit(station), licence_class=pl.lit(LICENCE))
    )
    summary = {
        "bulletins": bulletins.height,
        "unreadable": bulletins["taf_format"].null_count(),
        "old_format": int((bulletins["taf_format"] == "old").sum()),
        "periods": period_frame.height,
        "unparsed_tokens": int(bulletins["n_unparsed"].sum()),
    }
    return (
        _write(bulletins, stage_path("bulletins", station, year, data_root)),
        _write(period_frame, stage_path("periods", station, year, data_root)),
        summary,
    )
