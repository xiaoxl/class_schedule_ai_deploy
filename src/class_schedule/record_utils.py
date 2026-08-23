"""Small data-conversion helpers shared by CSV-backed domain models."""

import datetime
import re
import time
from collections.abc import Mapping


# "unassigned" is ATU's "Course Schedule Report" export's own placeholder
# for "no room/building" (see examples/Course Schedule Report_*.csv) --
# without it, a non-physical row's literal Room="Unassigned" reads as a
# real room and fails HybridClass's requirement that meeting-time presence
# match room presence.
_EMPTY_VALUES = frozenset({"", "none", "nan", "nat", "unassigned"})
_SLOT_PATTERN = re.compile(
    r"^(?P<days>M|T|W|R|F|MW|TR|MWF)\s+"
    r"(?P<clock>(?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:am|pm))$",
    re.IGNORECASE,
)

# Canonical field name -> every column header seen in the wild that means
# the same thing. "Meeting Days"/"Beginning Time"/"Ending Time"/"Schedule
# Type"/"Course Credit Hours"/"Instructor Name"/"XL Group Code" are the
# names used by ATU's Banner "Course_Catalog" export; "Meeting_Days" is
# the same field spelled with an underscore in ATU's "Course Schedule
# Report" export (see examples/Course Schedule Report_*.csv -- that
# export's Meeting_Times column needs its own split, handled separately
# in normalize_columns below, since it packs Start and End into one
# "9:30 am-10:50 am" string rather than two columns); the rest are the
# additional input spellings accepted by the domain model. Cross-List and XL
# Group Code are both accepted as cross-listing signals -- whichever
# column a given file actually populates is the one that counts (see
# normalize_columns' merge behavior below).
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "Subject": ("Subject",),
    "Number": ("Number",),
    "Section": ("Section",),
    "Time Slot": ("Time Slot", "TimeSlot", "time_slot"),
    "Days": ("Days", "Meeting Days", "Meeting_Days"),
    "Start": ("Start", "Beginning Time"),
    "End": ("End", "Ending Time"),
    "Duration": ("Duration", "Duration Minutes", "duration_minutes"),
    "Room": ("Room",),
    "Building": ("Building",),
    "Instructor": ("Instructor", "Instructor Name"),
    "Type": ("Type", "Schedule Type"),
    "Title": ("Title", "Catalog Title", "Section Title"),
    "Credits": ("Credits", "Course Credit Hours"),
    "Cross-List": ("Cross-List", "Cross List", "XL Group Code"),
}


def text(value: object) -> str:
    """Return a stripped string, treating common CSV nulls as empty."""
    if value is None:
        return ""
    cleaned = str(value).strip()
    return "" if cleaned.lower() in _EMPTY_VALUES else cleaned


def value(row: Mapping[str, object], *names: str) -> object:
    """Return the value under the first column name present in ``row``."""
    for name in names:
        if name in row:
            return row[name]
    return None


def split_time_range(value: object) -> tuple[str, str]:
    """Split a combined "9:30 am-10:50 am"-style range into (start, end)
    clock-time text, the shape ``normalize_columns``'s Start/End columns
    already expect. This is ATU's "Course Schedule Report" export's
    Meeting_Times column (see examples/Course Schedule Report_*.csv) --
    unlike Banner's separate Beginning Time/Ending Time columns, it packs
    both into one field, so a rename alone (like Meeting_Days -> Days)
    isn't enough. TBA, blank, or anything without exactly one ``-``
    returns ``("", "")`` -- a blank Start represents an arranged record
    with no physical meeting, so there's no separate
    "unparseable" case to raise on.
    """
    parts = text(value).split("-")
    if len(parts) != 2:
        return "", ""
    return parts[0].strip(), parts[1].strip()


def normalize_columns(row: Mapping[str, object]) -> dict[str, object]:
    """Rename a CSV row's columns to their canonical name.

    Strips stray header whitespace and maps any known alias (see
    ``COLUMN_ALIASES``, e.g. "Meeting Days" or "Instructor Name") onto the
    canonical name callers actually look up. Columns with no known alias
    pass through unchanged, so callers can still reach them by their raw
    name. Cross-list headers additionally ignore case and separators, so
    spellings such as ``Cross-List``, ``cross list``, ``CROSS_LIST``, and
    ``CrossList`` are equivalent. Every column recognized as a
    cross-listing signal is live at once: if a row has both a
    ``Cross-List``-spelled column and an ``XL Group Code`` column, either
    one being non-empty is enough to mark it, so the first non-empty
    value between them wins (rather than one silently shadowing the
    other because of column order). For other duplicate aliases, the
    first value encountered wins. A Meeting_Times column (see
    ``split_time_range``) is split into Start/End as a last step, but
    only when the row has no Start/Time Slot of its own already -- so a
    file that happens to carry a stray "Meeting_Times"-named column
    alongside real Start/Time Slot data is never overridden by it.
    """
    alias_to_canonical = {
        alias: canonical
        for canonical, aliases in COLUMN_ALIASES.items()
        for alias in aliases
    }
    result: dict[str, object] = {}
    for key, item in row.items():
        header = str(key).strip()
        compact_header = re.sub(r"[\s_-]+", "", header).casefold()
        canonical = (
            "Cross-List"
            if compact_header in {"crosslist", "xlgroupcode"}
            else alias_to_canonical.get(header, header)
        )
        if (
            canonical == "Cross-List"
            and canonical in result
            and not text(result[canonical])
            and text(item)
        ):
            result[canonical] = item
            continue
        result.setdefault(canonical, item)
    if (
        "Meeting_Times" in result
        and not text(result.get("Start"))
        and not text(result.get("Time Slot"))
    ):
        start, end = split_time_range(result.pop("Meeting_Times"))
        result["Start"] = start
        result["End"] = end
    return result


def clock(value: object) -> datetime.time:
    """Parse a CSV clock value as a time of day."""
    cleaned = text(value).replace(" ", "")
    # "%H%M" covers bare military time like "1300" (Banner-style exports),
    # which has no colon or am/pm marker for the other formats to match.
    for fmt in ("%I:%M%p", "%H:%M", "%H:%M:%S", "%H%M"):
        try:
            parsed = time.strptime(cleaned, fmt)
            return datetime.time(parsed.tm_hour, parsed.tm_min, parsed.tm_sec)
        except ValueError:
            continue
    raise ValueError(f"Invalid start time: {value!r}")


def format_slot(days: object, start: object) -> str:
    """Combine separate Days and Start values as ``'MWF 8:00am'``."""
    days_text = text(days).upper().replace("TH", "R")
    if not days_text or not text(start):
        return ""
    parsed = clock(start)
    hour = parsed.strftime("%I").lstrip("0") or "0"
    period = parsed.strftime("%p").lower()
    return f"{days_text} {hour}:{parsed:%M}{period}"


def parse_slot(
    value: object,
) -> tuple[str, datetime.time] | tuple[None, None]:
    """Split a slot; ONLINE, TBA, and blank values have no clock."""
    cleaned = text(value)
    if not cleaned or cleaned.upper() in {"ONLINE", "TBA"}:
        return None, None
    match = _SLOT_PATTERN.fullmatch(cleaned)
    if not match:
        raise ValueError(
            f"Invalid Time Slot {value!r}; "
            "expected a value such as 'MWF 8:00am'"
        )
    return match.group("days").upper(), clock(match.group("clock"))


def duration_from_times(start: object, end: object) -> int | None:
    """Calculate minutes between separate Start and End values."""
    if not text(start) or not text(end):
        return None
    start_time = clock(start)
    end_time = clock(end)
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes = end_time.hour * 60 + end_time.minute
    minutes = end_minutes - start_minutes
    return minutes if minutes > 0 else minutes + 24 * 60


def add_minutes(start: datetime.time, duration: int) -> datetime.time:
    """Return the clock time reached after ``duration`` minutes."""
    total = (
        start.hour * 60 + start.minute + duration
    ) % (24 * 60)
    return datetime.time(total // 60, total % 60)
