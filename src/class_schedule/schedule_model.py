"""Schedule: a collection of atomic classes, backed by a DataFrame boundary.

This module owns everything ``class_model`` deliberately does not: grouping
many CSV rows into many atomic classes, and converting the whole collection
to/from a pandas DataFrame. It composes ``class_model``'s public API --
``Section``, the ``Class`` hierarchy, and each kind's recognition predicate
(``is_four_credit``, ``is_hybrid``, ``is_cross_listing``, ``is_coreq_pair``)
-- without re-implementing any of their rules. Editing a class's time, room,
or instructor is delegated straight to that class's own ``change_*`` method,
so kind-specific behavior (``FourCreditClass``'s day-pattern-aware
``change_time``, ``CoreqClass`` requiring an explicit record, ...) applies
automatically -- this module doesn't need to know about any of it.
"""

from __future__ import annotations

import datetime
import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from . import record_utils
from .config_schema import PersonsFileSchema, PreferencesFileSchema
from .class_model import (
    Class,
    CoreqClass,
    CrossListingClass,
    FourCreditClass,
    HybridClass,
    NormalClass,
    Section,
)

_UNSET = object()

# Concurrent (dual-credit/high-school partnership) sections -- these are
# never real classes to schedule, so they're dropped before any grouping
# even sees them, not just excluded from one specific pairing rule.
_IGNORED_SECTION_PREFIXES = ("P", "ET", "A")


class GroupingError(ValueError):
    """Raised when a group of CSV rows can't become a valid class.

    Carries the raw row dicts involved (``records``), not just a message,
    so a caller -- e.g. the web app -- can show the user exactly which
    rows are implicated instead of only a course id buried in text.
    """

    def __init__(self, message: str, records: list[dict]) -> None:
        super().__init__(message)
        self.records = records


class Schedule:
    """An editable collection of atomic classes."""

    def __init__(self, classes: Iterable[Class] = ()) -> None:
        self.classes: list[Class] = list(classes)

    # ---- import (CSV records/DataFrame -> Schedule) ----

    @classmethod
    def from_records(
        cls,
        records: Iterable[Mapping[str, object]],
        *,
        persons: Mapping[str, "PersonRecord"] | None = None,
    ) -> "Schedule":
        """Group a complete table of CSV records into atomic classes."""
        return cls(_group_records(records, persons=persons))

    @classmethod
    def from_dataframe(
        cls,
        dataframe: pd.DataFrame,
        *,
        persons: Mapping[str, "PersonRecord"] | None = None,
    ) -> "Schedule":
        """Group a complete DataFrame into atomic classes."""
        return cls.from_records(dataframe.to_dict(orient="records"), persons=persons)

    # ---- export (Schedule -> CSV records/DataFrame) ----

    def to_records(self) -> list[dict[str, object]]:
        """Flatten every class back into one list of CSV row dicts."""
        return [
            record for item in self.classes for record in item.to_records()
        ]

    def to_dataframe(self) -> pd.DataFrame:
        """Flatten every class into one DataFrame."""
        records = self.to_records()
        if not records:
            return pd.DataFrame()
        return pd.DataFrame.from_records(records)

    # ---- export (Schedule -> Excel workbooks) ----
    #
    # Three operational views, each its own file: the flat as-parsed
    # table, and two weekly-grid workbooks (one worksheet per instructor,
    # one per room). All three still export even when the schedule has
    # conflicts -- see ``_build_weekly_sheet``.

    def to_raw_excel(self, path: str | Path) -> None:
        """One row per CSV record, in the schedule's own column order."""
        _write_raw_excel(self.to_dataframe(), path)

    def to_instructor_excel(self, path: str | Path) -> None:
        """One worksheet per instructor: a Monday-Friday weekly grid."""
        _weekly_workbook(self, group="instructor").save(path)

    def to_room_excel(self, path: str | Path) -> None:
        """One worksheet per room: a Monday-Friday weekly grid."""
        _weekly_workbook(self, group="room").save(path)

    # ---- lookup ----

    def __iter__(self):
        return iter(self.classes)

    def __len__(self) -> int:
        return len(self.classes)

    @property
    def course_ids(self) -> list[str]:
        return [
            course_id
            for item in self.classes
            for course_id in item.course_ids
        ]

    def index_of(self, course_id: str) -> int:
        """Return the index of the class containing ``course_id``."""
        for index, item in enumerate(self.classes):
            if course_id in item.course_ids:
                return index
        raise KeyError(f"Course not found: {course_id}")

    def get(self, course_id: str) -> Class:
        return self.classes[self.index_of(course_id)]

    # ---- collection editing ----

    def add(self, item: Class) -> "Schedule":
        """Add a class, rejecting any course id already present."""
        clashing = set(self.course_ids).intersection(item.course_ids)
        if clashing:
            raise ValueError(f"Course already exists: {sorted(clashing)}")
        self.classes.append(item)
        return self

    def remove(self, course_id: str) -> "Schedule":
        del self.classes[self.index_of(course_id)]
        return self

    # ---- per-class editing: delegates to that class's own change_* ----
    #
    # ``record`` defaults to ``_UNSET`` rather than ``None`` so that an
    # omitted ``record`` is forwarded as *omitted*, not as an explicit
    # ``None``. Some kinds (``CoreqClass``) make ``record`` a required
    # keyword with no default of its own, specifically so a caller must
    # choose which meeting to move; if this wrapper always forwarded
    # ``record=None`` it would silently satisfy that requirement and
    # defeat the whole point.

    def change_time(
        self, course_id: str, time_slot: str, *, record: object = _UNSET
    ) -> "Schedule":
        index = self.index_of(course_id)
        kwargs = {} if record is _UNSET else {"record": record}
        self.classes[index] = self.classes[index].change_time(
            time_slot, **kwargs
        )
        return self

    def change_room(
        self, course_id: str, room: str, *, record: object = _UNSET
    ) -> "Schedule":
        index = self.index_of(course_id)
        kwargs = {} if record is _UNSET else {"record": record}
        self.classes[index] = self.classes[index].change_room(
            room, **kwargs
        )
        return self

    def change_instructor(
        self, course_id: str, instructor: str, *, record: object = _UNSET
    ) -> "Schedule":
        index = self.index_of(course_id)
        kwargs = {} if record is _UNSET else {"record": record}
        self.classes[index] = self.classes[index].change_instructor(
            instructor, **kwargs
        )
        return self


def _group_records(
    records: Iterable[Mapping[str, object]],
    *,
    persons: Mapping[str, "PersonRecord"] | None = None,
) -> list[Class]:
    """Group raw CSV records into atomic classes.

    Classification happens as part of the scan itself -- there is no
    separate "infer" step. Each pass below both finds candidate rows
    *and* decides which kind they become, using that kind's own public
    recognition predicate from ``class_model``. Precedence, highest
    first: same-course pairs (four-credit/HyFlex) beat cross-listed
    pairs, which beat coreq pairs; anything left over is a single class.
    Construction always re-validates through the target class's own
    ``validate`` -- a pair that matches a scan (e.g. the coreq whitelist)
    but fails its finer rules (e.g. bad scheduling) still raises here.

    Rows in a concurrent-enrollment section (see
    ``_IGNORED_SECTION_PREFIXES``) are dropped up front and never appear
    in the resulting classes.
    """
    remaining: list[Section] = []
    for row in records:
        normalized = record_utils.normalize_columns(row)
        if persons:
            instructor = record_utils.text(record_utils.value(normalized, "Instructor"))
            subject = record_utils.text(record_utils.value(normalized, "Subject")).upper()
            resolved = resolve_person_name(instructor, persons, subject=subject)
            if resolved is not None:
                normalized["Instructor"] = resolved
        section_code = record_utils.text(
            record_utils.value(normalized, "Section")
        ).upper()
        if section_code.startswith(_IGNORED_SECTION_PREFIXES):
            continue
        try:
            remaining.append(Section.from_record(normalized))
        except ValueError as error:
            raise GroupingError(str(error), [dict(row)]) from error

    result: list[Class] = []
    same_course, remaining = _take_same_course(remaining)
    result.extend(same_course)
    cross_listed, remaining = _take_cross_listed(remaining)
    result.extend(cross_listed)
    coreqs, remaining = _take_coreqs(remaining)
    result.extend(coreqs)
    result.extend(NormalClass((section,)) for section in remaining)
    return result


def _take_same_course(
    remaining: list[Section],
) -> tuple[list[Class], list[Section]]:
    by_identity: dict[tuple[str, str, str], list[Section]] = {}
    for section in remaining:
        by_identity.setdefault(section.identity, []).append(section)

    found: list[Class] = []
    consumed: set[int] = set()
    for key, group in by_identity.items():
        if len(group) > 2:
            raise GroupingError(
                f"{' '.join(key[:2])}-{key[2]} has more than two CSV records",
                [section.to_record() for section in group],
            )
        if len(group) == 2:
            left, right = group
            target = (
                HybridClass
                if HybridClass.is_hybrid(left, right)
                else FourCreditClass
            )
            try:
                found.append(target((left, right)))
            except ValueError as error:
                raise GroupingError(
                    str(error), [left.to_record(), right.to_record()]
                ) from error
            consumed.update(id(section) for section in group)
    return found, [
        section for section in remaining if id(section) not in consumed
    ]


def _take_cross_listed(
    remaining: list[Section],
) -> tuple[list[Class], list[Section]]:
    found, remaining = _take_cross_list_column(remaining)
    more, remaining = _take_honors_pairs(remaining)
    found.extend(more)
    return found, remaining


def _take_cross_list_column(
    remaining: list[Section],
) -> tuple[list[Class], list[Section]]:
    by_cross_list: dict[str, list[Section]] = {}
    for section in remaining:
        if section.cross_list:
            by_cross_list.setdefault(section.cross_list, []).append(section)

    found: list[Class] = []
    consumed: set[int] = set()
    for cross_list, group in by_cross_list.items():
        if len(group) > 2:
            raise GroupingError(
                f"Cross-List {cross_list!r} has more than two CSV records",
                [section.to_record() for section in group],
            )
        if len(group) == 2:
            left, right = group
            try:
                found.append(CrossListingClass(tuple(group)))
            except ValueError as error:
                raise GroupingError(
                    str(error), [left.to_record(), right.to_record()]
                ) from error
            consumed.update(id(section) for section in group)
    return found, [
        section for section in remaining if id(section) not in consumed
    ]


def _take_honors_pairs(
    remaining: list[Section],
) -> tuple[list[Class], list[Section]]:
    """Pair regular/'H'-prefixed honors sections not already linked by an
    explicit Cross-List value (see ``CrossListingClass.is_honors_pair``)."""
    matches: list[tuple[int, int]] = []
    for left_index, left in enumerate(remaining):
        for right_index in range(left_index + 1, len(remaining)):
            right = remaining[right_index]
            if CrossListingClass.is_honors_pair(left, right):
                matches.append((left_index, right_index))

    involved = [index for pair in matches for index in pair]
    if len(involved) != len(set(involved)):
        raise GroupingError(
            "Ambiguous honors-section pairing: one course matches "
            "multiple pairs",
            [remaining[index].to_record() for index in sorted(set(involved))],
        )

    consumed = set(involved)
    found = []
    for left_index, right_index in matches:
        left, right = remaining[left_index], remaining[right_index]
        try:
            found.append(CrossListingClass((left, right)))
        except ValueError as error:
            raise GroupingError(
                str(error), [left.to_record(), right.to_record()]
            ) from error
    return found, [
        section
        for index, section in enumerate(remaining)
        if index not in consumed
    ]


def _take_coreqs(
    remaining: list[Section],
) -> tuple[list[Class], list[Section]]:
    matches: list[tuple[int, int]] = []
    for left_index, left in enumerate(remaining):
        for right_index in range(left_index + 1, len(remaining)):
            right = remaining[right_index]
            if CoreqClass.is_coreq_pair(left, right):
                matches.append((left_index, right_index))

    involved = [index for pair in matches for index in pair]
    if len(involved) != len(set(involved)):
        raise GroupingError(
            "Ambiguous coreq records: one course matches multiple pairs",
            [remaining[index].to_record() for index in sorted(set(involved))],
        )

    consumed = set(involved)
    found = []
    for left_index, right_index in matches:
        left, right = remaining[left_index], remaining[right_index]
        try:
            found.append(CoreqClass((left, right)))
        except ValueError as error:
            raise GroupingError(
                str(error), [left.to_record(), right.to_record()]
            ) from error
    return found, [
        section
        for index, section in enumerate(remaining)
        if index not in consumed
    ]


# ---- config-driven evaluation (config/persons.toml, config/preferences.toml) ----
#
# persons.toml is contractual fact about a person (currently just
# max_load); preferences.toml is this term's wishes for an instructor.
# Nothing here is a hard requirement any more -- ``check_hard_requirements``
# was deleted; the only hard-violation source left is ``check_conflicts``
# (room/instructor double-booking). Coreq/four-credit/hybrid scheduling
# legality never needs its own runtime check here: it's guaranteed both at
# ``Class`` construction time (each kind's own ``validate()``) and, for the
# solver's output specifically, by ``solver/constraints.py``'s hard pairwise-exclusion
# (an invalid coreq/four-credit/hybrid pairing is never a legal candidate
# combination in the first place).
#
# max_load is a per-instructor TARGET from persons.toml, not just a
# ceiling -- the contract says roughly "you teach max_load credit hours",
# so both going over AND falling short matter, and both are *always* soft
# findings now, never hard:
#   - within OVERLOAD_TOLERANCE credit hours over max_load: fine, not
#     overload at all -- this is the definition of overload, not a
#     leniency knob.
#   - more than that over: a soft "overload" finding, always. Its penalty
#     is ``preference.overload_penalty`` -- derived from ``allow_overload``
#     (this term's per-instructor overload tolerance: ``True`` means
#     "fine with it", ``False`` means "avoid it") -- flat and one-time,
#     deliberately NOT scaled by how many credit hours over: an earlier
#     version tried both a continuous excess-times-rate calculation and a
#     multi-tier cumulative boolean scheme, and both measurably slowed
#     CP-SAT's search on a real schedule (the same problem stopped
#     reaching a proven-optimal solution within the same time budget it
#     used to, and reverting this flat scheme is what brought that back)
#     -- this system doesn't have a way to reward "further over" that
#     doesn't cost real solve performance, at least not one found so far.
#     The one exception: OVERLOAD_FAR_PENALTY, a *second*, independent
#     flat charge (not tiered/cumulative logic) that also applies once an
#     instructor goes more than OVERLOAD_FAR_THRESHOLD credit hours over
#     their own max_load -- identical convention to OVERLOAD_TOLERANCE
#     above (the constant is the last value that's still fine, not the
#     first that triggers), just a second, further-out line -- on top of
#     the base penalty above -- for ``allow_overload=True`` only, since
#     ``allow_overload=False`` already sits at this system's 100-point
#     ceiling and has nowhere higher to go.
#     An instructor with no preferences.toml entry defaults to a penalty
#     of 0 (no opinion on record).
#   - under max_load by any amount: also a soft finding, weighted very
#     high (UNDER_LOAD_PENALTY) -- "must reach max_load" is meant to
#     dominate ordinary soft preferences. It's still soft, though: if
#     every other instructor is already at or over capacity and nothing
#     else is wrong, one instructor coming up short is accepted rather
#     than forced.
OVERLOAD_TOLERANCE = 2.0
# Same convention as OVERLOAD_TOLERANCE: the last credit-hour-over-max_load
# value that does NOT trigger the extra penalty -- 4 is fine, 5 triggers
# it (a strict "more than" comparison, exactly like OVERLOAD_TOLERANCE).
# Stacked on top of the base penalty (10 for allow_overload=True), a
# permissive instructor 5+ credit hours over lands at 60 -- clearly above
# the small fixed penalties elsewhere (disliked_*/back_to_back at 5-10),
# but well under a strict instructor's 100. Tested and confirmed CP-SAT-
# solve-safe on the real production file at this value; 60 (10+60=70)
# reproducibly degraded the same file's solve from OPTIMAL to FEASIBLE
# within a 60s cap -- don't bump this without re-benchmarking.
OVERLOAD_FAR_THRESHOLD = 4
OVERLOAD_FAR_PENALTY = 50.0

# Every penalty in this system shares one 0-100 scale (see
# PreferenceRecord.overload_penalty and PreferenceRule.weight) -- 100 is
# the practical ceiling used throughout, though UNDER_LOAD_PENALTY itself
# is tuned slightly below it.
UNDER_LOAD_PENALTY = 90.0
BACK_TO_BACK_PENALTY = 10.0
DISLIKED_TIME_PENALTY = 5.0
DISLIKED_LOCATION_PENALTY = 5.0
DISLIKED_COURSE_PENALTY = 5.0
# Same mild-nudge tier as the DISLIKED_* penalties above -- prefers_online
# is the same shape of preference (a soft affinity about *how* a section
# is taught), just phrased as a "prefer" instead of a "dislike".
PREFERS_ONLINE_PENALTY = 5.0


def weekday_time_overlap(
    days_a: str | Iterable[str] | None,
    start_a: datetime.time | None,
    end_a: datetime.time | None,
    days_b: str | Iterable[str] | None,
    start_b: datetime.time | None,
    end_b: datetime.time | None,
) -> bool:
    """Shared by ``TimeWindow.overlaps`` and ``overlaps_in_time`` -- true
    when both sides meet on at least one common weekday AND their clock
    ranges overlap on it."""
    if (
        not days_a or not days_b
        or start_a is None or start_b is None
        or end_a is None or end_b is None
    ):
        return False
    return bool(set(days_a) & set(days_b)) and start_a < end_b and start_b < end_a


@dataclass(frozen=True)
class TimeWindow:
    """A recurring weekly window, e.g. "Friday noon" or "no early TR"."""

    days: frozenset[str]
    start: datetime.time
    end: datetime.time
    reason: str = ""

    @classmethod
    def from_config(cls, raw: Mapping[str, object]) -> "TimeWindow":
        """``raw["between"]`` is a two-element ``[start, end]`` array --
        e.g. ``between = ["08:00", "09:00"]`` -- rather than separate
        ``start``/``end`` keys, since a bare "start"/"end" reads
        ambiguously next to a class's own actual start/end time (this is
        a *window* to match against, not one specific meeting)."""
        window_start, window_end = raw["between"]
        return cls(
            days=frozenset(raw.get("days", ())),
            start=record_utils.clock(window_start),
            end=record_utils.clock(window_end),
            reason=str(raw.get("reason", "")),
        )

    def overlaps(
        self,
        days: str | None,
        start: datetime.time | None,
        end: datetime.time | None,
    ) -> bool:
        return weekday_time_overlap(days, start, end, self.days, self.start, self.end)


@dataclass(frozen=True)
class PersonAlias:
    short: str
    subject: str | None = None


@dataclass(frozen=True)
class PersonRecord:
    """One persons.toml entry -- contractual facts about an instructor."""

    name: str
    max_load: float
    courses: tuple[str, ...] = ()
    aliases: tuple[PersonAlias, ...] = ()


@dataclass(frozen=True)
class PreferenceRule:
    """One `[[rules]]` entry (top-level, applies regardless of
    instructor) or `instructors.rules` entry (nested under one
    `[[instructors]]` block, scoped to that instructor).

    ``course`` ("SUBJECT NUMBER", matching persons.toml's own
    convention), ``section``, ``room``, and ``time`` are all optional
    match keys -- an unset key matches anything, so a rule can be as
    broad ("this instructor generally avoids Corley") or as narrow ("this
    exact course-section must land in this exact room") as its fields
    specify. ``section`` only makes sense alongside ``course`` -- a bare
    section code like "F01" repeats across unrelated courses.

    ``direction`` is ``"prefer"`` (subtracts ``weight`` from a matching
    candidate's cost -- a reward the solver seeks out) or ``"dislike"``
    (adds it -- a penalty the solver avoids); ``weight`` is always a
    positive magnitude, on the same 0-100 scale as every other penalty in
    this system -- 100 is this system's practical ceiling, just below
    ``UNDER_LOAD_PENALTY``.
    """

    course: str | None = None
    section: str | None = None
    room: str | None = None
    time: TimeWindow | None = None
    direction: str = "dislike"
    weight: float = 0.0

    def matches(
        self,
        *,
        course: str,
        section: str,
        building: str,
        room: str,
        days: str | None,
        start: datetime.time | None,
        end: datetime.time | None,
    ) -> bool:
        if self.course is not None and self.course != course:
            return False
        if self.section is not None and self.section != section:
            return False
        if self.room is not None and not location_matches(building, room, (self.room,)):
            return False
        if self.time is not None and not self.time.overlaps(days, start, end):
            return False
        return True

    @property
    def signed_weight(self) -> float:
        return -self.weight if self.direction == "prefer" else self.weight


@dataclass(frozen=True)
class PreferenceRecord:
    """One preferences.toml entry for the current term.

    ``allow_overload`` is this instructor's overload tolerance: ``True``
    means fine with it, ``False`` means avoid it (still soft -- see the
    module comment above OVERLOAD_TOLERANCE). ``overload_penalty`` derives
    the actual flat scoring penalty from it -- 10 when ``allow_overload``
    is ``True``, 100 (this system's practical ceiling) when it's
    ``False``.

    ``prefers_online`` is a blanket affinity for online/hyflex sections --
    a mild scored nudge (``PREFERS_ONLINE_PENALTY``) against any
    in-person assignment, on the same tier as the ``disliked_*`` fields.
    It's blanket, not course-scoped -- someone who only wants a *specific*
    course online (not every section they teach) needs a note in
    ``rules`` instead; this field can't express that.

    ``max_back_to_back`` caps how many consecutive same-day meetings this
    instructor tolerates before it's scored -- ``None`` means no cap
    (``allow_back_to_back`` alone decides, as before). It only applies
    when ``allow_back_to_back`` is ``True``: back-to-back is already
    scored at every occurrence when it's ``False``, and a cap can't loosen
    that -- "no back-to-back at all" is a stricter statement than "no more
    than N in a row" ever needs to override. A run of exactly
    ``max_back_to_back`` meetings is fine; each meeting past that is its
    own scored finding (``BACK_TO_BACK_PENALTY`` again), so a longer run
    costs more than a run of ``max_back_to_back + 1``.
    """

    name: str
    allow_overload: bool = True
    allow_back_to_back: bool = True
    max_back_to_back: int | None = None
    prefers_online: bool = False
    preferred_times: tuple[TimeWindow, ...] = ()
    disliked_times: tuple[TimeWindow, ...] = ()
    preferred_locations: tuple[str, ...] = ()
    disliked_locations: tuple[str, ...] = ()
    preferred_courses: tuple[str, ...] = ()
    disliked_courses: tuple[str, ...] = ()
    rules: tuple[PreferenceRule, ...] = ()

    @property
    def overload_penalty(self) -> float:
        return 10.0 if self.allow_overload else 100.0


def load_persons(path: str | Path) -> dict[str, PersonRecord]:
    """Parse ``persons.toml`` into ``{name: PersonRecord}``."""
    with open(path, "rb") as handle:
        raw = PersonsFileSchema.model_validate(tomllib.load(handle))
    return {
        entry.name: PersonRecord(
            name=entry.name,
            max_load=entry.max_load,
            courses=tuple(entry.courses),
            aliases=tuple(
                PersonAlias(alias, None)
                if isinstance(alias, str)
                else PersonAlias(alias.short, alias.subject)
                for alias in entry.aliases
            ),
        )
        for entry in raw.persons
    }


def resolve_person_name(
    value: str, persons: Mapping[str, PersonRecord], *, subject: str | None = None
) -> str | None:
    """Resolve an exact person name or a configured, optionally scoped alias."""
    if value in persons:
        return value
    matches = {
        person.name
        for person in persons.values()
        for alias in person.aliases
        if alias.short == value and (alias.subject is None or alias.subject == subject)
    }
    if len(matches) > 1:
        raise ValueError(f"Ambiguous instructor alias {value!r}: {sorted(matches)}")
    return next(iter(matches), None)


def load_preferences(path: str | Path) -> dict[str, PreferenceRecord]:
    """Parse ``preferences.toml`` into ``{name: PreferenceRecord}``."""
    with open(path, "rb") as handle:
        raw = PreferencesFileSchema.model_validate(tomllib.load(handle))
    return {
        entry.name: PreferenceRecord(
            name=entry.name,
            allow_overload=entry.allow_overload,
            allow_back_to_back=entry.allow_back_to_back,
            max_back_to_back=entry.max_back_to_back,
            prefers_online=entry.prefers_online,
            preferred_times=tuple(
                TimeWindow.from_config(w.model_dump()) for w in entry.preferred_times
            ),
            disliked_times=tuple(
                TimeWindow.from_config(w.model_dump()) for w in entry.disliked_times
            ),
            preferred_locations=tuple(entry.preferred_locations),
            disliked_locations=tuple(entry.disliked_locations),
            preferred_courses=tuple(entry.preferred_courses),
            disliked_courses=tuple(entry.disliked_courses),
            rules=tuple(_parse_rule(r.model_dump(exclude_none=True)) for r in entry.rules),
        )
        for entry in raw.instructors
    }


def load_global_rules(path: str | Path) -> tuple[PreferenceRule, ...]:
    """Parse preferences.toml's top-level ``[[rules]]`` -- rules that
    apply no matter which instructor ends up teaching the match (see
    ``PreferenceRecord.rules`` for the per-instructor equivalent, nested
    under ``instructors.rules``)."""
    with open(path, "rb") as handle:
        raw = PreferencesFileSchema.model_validate(tomllib.load(handle))
    return tuple(_parse_rule(r.model_dump(exclude_none=True)) for r in raw.rules)


def _parse_rule(raw: Mapping[str, object]) -> PreferenceRule:
    direction = str(raw.get("direction", "dislike"))
    if direction not in ("prefer", "dislike"):
        raise ValueError(
            f"Rule direction must be 'prefer' or 'dislike', got {direction!r}"
        )
    section = raw.get("section")
    if section is not None and "course" not in raw:
        raise ValueError("A rule's 'section' requires 'course' to also be set")
    return PreferenceRule(
        course=str(raw["course"]) if "course" in raw else None,
        section=str(section) if section is not None else None,
        room=str(raw["room"]) if "room" in raw else None,
        time=TimeWindow.from_config(raw["time"]) if "time" in raw else None,
        direction=direction,
        weight=float(raw.get("weight", 0.0)),
    )


@dataclass(frozen=True)
class HardViolation:
    rule: str
    subject: str
    message: str


@dataclass(frozen=True)
class SoftFinding:
    rule: str
    instructor: str
    message: str
    penalty: float


def _teaching_loads(schedule: "Schedule") -> dict[str, float]:
    """Total credit hours per instructor.

    Matches the webapp UI's per-instructor aggregation: a class's hours
    count once per distinct instructor teaching it, no matter how many
    CSV rows (sections) it has.
    """
    totals: dict[str, float] = {}
    for item in schedule:
        instructors = {s.instructor for s in item.sections if s.instructor}
        for instructor in instructors:
            totals[instructor] = totals.get(instructor, 0.0) + item.credit_hours
    return totals


def location_matches(building: str, room: str, locations: Iterable[str]) -> bool:
    """True if ``building``, ``room``, or "building room" combined is in
    ``locations`` -- accepts either form, matching how preferences.toml
    documents writing a location (e.g. "Corley" or "Corley 101")."""
    full = f"{building} {room}".strip()
    return bool({building, room, full} & set(locations))


def is_back_to_back(left: Section, right: Section) -> bool:
    if not (set(left.days or "") & set(right.days or "")):
        return False
    return left.end == right.start or right.end == left.start


_WEEKDAY_LETTERS = "MTWRF"


def _capped_back_to_back_findings(
    instructor: str, sections: list[Section], cap: int
) -> list[SoftFinding]:
    """Flag every meeting past the ``cap``-th in an instructor's own
    consecutive same-day run.

    Unlike ``is_back_to_back`` (any shared weekday between two possibly
    multi-day sections), a "run" here is built per single calendar day --
    the only way to walk a chain of 3+ meetings in order without a
    multi-day section like "MWF" ambiguously joining two unrelated runs.
    A run of exactly ``cap`` is unflagged; the (cap+1)-th meeting is one
    finding, the (cap+2)-th is another, and so on -- so a longer run
    always scores strictly more than a shorter one, same as stacking
    ``BACK_TO_BACK_PENALTY`` per over-cap join.

    A multi-day pattern like "MWF" walks the same run once per letter it
    spans (M, then W, then F) and finds the identical join each time --
    deduped by the course-id pair involved, so a genuine MWF run is one
    finding, not three, matching how the plain (uncapped) pairwise check
    already treats one back-to-back class-pair as a single finding
    regardless of how many shared weekdays it recurs on.
    """
    findings: list[SoftFinding] = []
    seen_joins: set[tuple[str, str]] = set()
    for day in _WEEKDAY_LETTERS:
        day_sections = sorted(
            (s for s in sections if s.days and day in s.days and s.start is not None),
            key=lambda s: (s.start.hour, s.start.minute),
        )
        run: list[Section] = []
        for section in day_sections:
            if run and run[-1].end == section.start:
                run.append(section)
            else:
                run = [section]
            if len(run) > cap:
                join = (run[-2].course_id, run[-1].course_id)
                if join in seen_joins:
                    continue
                seen_joins.add(join)
                findings.append(SoftFinding(
                    "back_to_back", instructor,
                    f"{instructor}: {run[-2].course_id} and "
                    f"{run[-1].course_id} extend a same-day run past "
                    f"the {cap}-in-a-row cap",
                    BACK_TO_BACK_PENALTY,
                ))
    return findings


@dataclass(frozen=True)
class _OverloadStatus:
    instructor: str
    load: float
    max_load: float
    penalty: float


def _overload_statuses(
    schedule: "Schedule",
    persons: dict[str, PersonRecord],
    preferences: dict[str, PreferenceRecord],
) -> list[_OverloadStatus]:
    """The single source of truth for "is this instructor overloaded".

    Anything within ``OVERLOAD_TOLERANCE`` credit hours of max_load isn't
    included at all -- it doesn't count as overload, so it's never
    reported by ``check_soft_preferences``. Everything this returns *is*
    overload, always soft -- ``penalty`` is ``preference.overload_penalty``
    (``0.0`` when there's no preferences.toml entry for that instructor),
    plus ``OVERLOAD_FAR_PENALTY`` on top when they're *also* more than
    ``OVERLOAD_FAR_THRESHOLD`` credit hours over their own max_load *and*
    ``allow_overload`` -- see the module comment above
    ``OVERLOAD_TOLERANCE``. Mirrors ``solver/constraints.py``'s load model
    exactly so the web UI's reported penalty matches what the solver
    actually optimized for.
    """
    statuses: list[_OverloadStatus] = []
    for instructor, load in sorted(_teaching_loads(schedule).items()):
        person = persons.get(instructor)
        if person is None:
            continue
        excess = load - person.max_load
        if excess <= OVERLOAD_TOLERANCE:
            continue
        preference = preferences.get(instructor)
        penalty = preference.overload_penalty if preference else 0.0
        if preference is not None and preference.allow_overload and excess > OVERLOAD_FAR_THRESHOLD:
            penalty += OVERLOAD_FAR_PENALTY
        statuses.append(_OverloadStatus(
            instructor=instructor,
            load=load,
            max_load=person.max_load,
            penalty=penalty,
        ))
    return statuses


def overlaps_in_time(left: Section, right: Section) -> bool:
    return weekday_time_overlap(
        left.days, left.start, left.end, right.days, right.start, right.end
    )


def check_conflicts(schedule: "Schedule") -> list[HardViolation]:
    """The sole source of hard violations: double-booking -- two different
    classes using the same room, or assigned to the same instructor, at an
    overlapping time.

    Independent of any config file -- this is a structural conflict in
    the schedule itself. A class's own multiple rows (FourCreditClass,
    HybridClass, CrossListingClass, CoreqClass) are never compared
    against each other here, since e.g. a genuine cross-listing is
    *meant* to share room/time/instructor -- it's one physical meeting
    filed under two catalog numbers, not a double-booking. Coreq/
    four-credit/hybrid scheduling legality doesn't need its own check
    here either -- see the module comment above ``OVERLOAD_TOLERANCE``.
    """
    entries = [
        (item, section)
        for item in schedule
        for section in item.sections
        if not section.is_online
    ]
    violations: list[HardViolation] = []
    for index, (item_a, a) in enumerate(entries):
        for item_b, b in entries[index + 1:]:
            if item_a is item_b or not overlaps_in_time(a, b):
                continue
            if a.room and a.building == b.building and a.room == b.room:
                location = f"{a.building} {a.room}".strip()
                violations.append(HardViolation(
                    "room_conflict", location,
                    f"{a.course_id} and {b.course_id} both use {location} "
                    f"at an overlapping time ({a.time_slot} / {b.time_slot})",
                ))
            if a.instructor and a.instructor == b.instructor:
                violations.append(HardViolation(
                    "instructor_conflict", a.instructor,
                    f"{a.course_id} and {b.course_id} both assign "
                    f"{a.instructor} at an overlapping time "
                    f"({a.time_slot} / {b.time_slot})",
                ))
    return violations


def check_soft_preferences(
    schedule: "Schedule",
    preferences: dict[str, PreferenceRecord],
    persons: dict[str, PersonRecord],
    global_rules: tuple[PreferenceRule, ...] = (),
) -> tuple[float, list[SoftFinding]]:
    """Score a schedule against preferences.toml.

    Returns ``(total_penalty, findings)`` -- 0 means every preference was
    honored, lower is always better. Every rule here is soft, including
    ``max_load`` -- see the module comment above ``OVERLOAD_TOLERANCE`` for
    the full over/under contract. Being outside a
    ``preferred_times``/``preferred_locations``/``preferred_courses``
    window is not scored: those are informational affinities, not
    something whose *absence* is treated as a violation.
    ``disliked_courses`` (subject + number, e.g. "MATH 0903", matching
    persons.toml's own ``courses`` convention) mirrors
    ``disliked_locations`` -- a mild nudge (``DISLIKED_COURSE_PENALTY``)
    when an instructor teaches a course they've listed as disliked.

    ``global_rules`` plus each matching instructor's own ``rules`` (see
    ``PreferenceRule``) are checked too, but only their ``"dislike"``
    side -- a matching ``"prefer"`` rule still steers the solver (it's
    scored in ``solver/candidates.py``'s ``preference_cost``) but isn't reported
    here, since a *satisfied* preference isn't a violation to surface
    next to everything else this function returns.
    """
    findings: list[SoftFinding] = [
        SoftFinding(
            "overload", status.instructor,
            f"{status.instructor}: {status.load:g} credit hours exceeds "
            f"max_load {status.max_load:g}",
            status.penalty,
        )
        for status in _overload_statuses(schedule, persons, preferences)
    ]

    loads = _teaching_loads(schedule)
    for instructor, person in sorted(persons.items()):
        load = loads.get(instructor, 0.0)
        if load < person.max_load:
            findings.append(SoftFinding(
                "under_load", instructor,
                f"{instructor}: {load:g} credit hours is under max_load "
                f"{person.max_load:g}",
                UNDER_LOAD_PENALTY,
            ))

    sections = [
        section
        for item in schedule
        for section in item.sections
        if section.instructor
    ]

    for section in sections:
        preference = preferences.get(section.instructor)
        course = f"{section.subject} {section.number}"
        applicable_rules = list(global_rules)
        if preference is not None:
            applicable_rules.extend(preference.rules)
        for rule in applicable_rules:
            if rule.direction != "dislike":
                continue
            if rule.matches(
                course=course, section=section.section,
                building=section.building, room=section.room,
                days=section.days, start=section.start, end=section.end,
            ):
                findings.append(SoftFinding(
                    "custom_rule", section.instructor,
                    f"{section.course_id}: matches a custom dislike rule "
                    f"(weight {rule.weight:g})",
                    rule.weight,
                ))
        if preference is None:
            continue
        for window in preference.disliked_times:
            if window.overlaps(section.days, section.start, section.end):
                findings.append(SoftFinding(
                    "disliked_time", section.instructor,
                    f"{section.course_id}: falls in a disliked time "
                    f"({window.reason or section.time_slot})",
                    DISLIKED_TIME_PENALTY,
                ))
        if course in preference.disliked_courses:
            findings.append(SoftFinding(
                "disliked_course", section.instructor,
                f"{section.course_id}: {section.instructor} dislikes "
                f"teaching {course}",
                DISLIKED_COURSE_PENALTY,
            ))
        if preference.prefers_online and not section.is_online:
            findings.append(SoftFinding(
                "online_preference", section.instructor,
                f"{section.course_id}: {section.instructor} prefers "
                f"online/hyflex sections but this one meets in person",
                PREFERS_ONLINE_PENALTY,
            ))
        if section.is_online:
            continue
        if preference.disliked_locations and location_matches(
            section.building, section.room, preference.disliked_locations
        ):
            findings.append(SoftFinding(
                "disliked_location", section.instructor,
                f"{section.course_id}: room "
                f"{f'{section.building} {section.room}'.strip()!r} is a "
                f"disliked location",
                DISLIKED_LOCATION_PENALTY,
            ))

    by_instructor: dict[str, list[Section]] = {}
    for section in sections:
        if not section.is_online:
            by_instructor.setdefault(section.instructor, []).append(section)
    for instructor, instructor_sections in by_instructor.items():
        preference = preferences.get(instructor)
        if preference is None:
            continue
        if not preference.allow_back_to_back:
            for i, left in enumerate(instructor_sections):
                for right in instructor_sections[i + 1:]:
                    if is_back_to_back(left, right):
                        findings.append(SoftFinding(
                            "back_to_back", instructor,
                            f"{instructor}: {left.course_id} and "
                            f"{right.course_id} are back-to-back",
                            BACK_TO_BACK_PENALTY,
                        ))
        elif preference.max_back_to_back is not None:
            findings.extend(_capped_back_to_back_findings(
                instructor, instructor_sections, preference.max_back_to_back
            ))

    total = sum(finding.penalty for finding in findings)
    return total, findings


# ---- Excel workbook builders ----
#
# Adapted from the archived ``.dep/class_schedule_old/reports.py`` (``export_excel`` /
# ``export_schedule_views`` / ``_weekly_workbook``), which did the same
# job against the old pandas-row model. Working from ``Section`` objects
# directly here instead needs none of that code's ``pd.notna`` guarding.

_WEEKDAYS = (
    ("M", "Monday"), ("T", "Tuesday"), ("W", "Wednesday"),
    ("R", "Thursday"), ("F", "Friday"),
)


def _write_raw_excel(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Schedule", index=False)
        if df.empty:
            return
        ws = writer.book["Schedule"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="305496")
            cell.alignment = Alignment(horizontal="center")
        for column in ws.columns:
            width = max(
                (len(str(cell.value)) if cell.value is not None else 0)
                for cell in column
            )
            ws.column_dimensions[column[0].column_letter].width = min(
                35, max(10, width + 2)
            )


def _weekly_workbook(schedule: "Schedule", *, group: str) -> Workbook:
    """``group`` is ``"instructor"`` or ``"room"``."""
    # Keep each section paired with the atomic class (``Class``) it came
    # from -- ``_build_weekly_sheet`` needs that to tell a real
    # double-booking from a HybridClass/CrossListingClass companion
    # meeting that's *meant* to land on the same slot.
    entries = [(item, section) for item in schedule for section in item.sections]

    def key_of(section: Section) -> str:
        if group == "instructor":
            return section.instructor
        return f"{section.building} {section.room}".strip()

    groups: dict[str, list[tuple[Class, Section]]] = {}
    for item, section in entries:
        if group == "room" and section.is_online:
            continue  # nowhere to place an online meeting on a room grid
        key = key_of(section)
        if not key:
            continue
        groups.setdefault(key, []).append((item, section))

    workbook = Workbook()
    workbook.remove(workbook.active)
    if not groups:
        ws = workbook.create_sheet("No scheduled data")
        ws["A1"] = f"No rows with {group} assignments."
        return workbook

    used_titles: set[str] = set()
    for resource in sorted(groups):
        title = _safe_sheet_title(resource, used_titles)
        ws = workbook.create_sheet(title)
        _build_weekly_sheet(ws, resource, groups[resource], group)
    return workbook


def _merged_anchor(ws, row: int, column: int):
    """The writable top-left cell for ``(row, column)`` -- itself if it
    isn't part of a merge, otherwise that merged range's own anchor cell
    (the only one of its cells whose ``.value`` isn't read-only)."""
    cell = ws.cell(row, column)
    if not isinstance(cell, MergedCell):
        return cell
    for merged_range in ws.merged_cells.ranges:
        if (
            merged_range.min_row <= row <= merged_range.max_row
            and merged_range.min_col <= column <= merged_range.max_col
        ):
            return ws.cell(merged_range.min_row, merged_range.min_col)
    return cell  # pragma: no cover -- a MergedCell always belongs to some range


def _build_weekly_sheet(
    ws, resource: str, entries: list[tuple[Class, Section]], group: str
) -> None:
    # Restart the old ten-colour palette for every instructor/room sheet.
    # Colour belongs to the atomic Class object, so all of its component
    # sections and meeting rows stay visually tied together.
    color_by_class: dict[int, str] = {}
    for item, _section in entries:
        class_key = id(item)
        if class_key not in color_by_class:
            color_by_class[class_key] = _ATOMIC_CLASS_COLORS[
                len(color_by_class) % len(_ATOMIC_CLASS_COLORS)
            ]

    physical = [(item, s) for item, s in entries if not s.is_online]
    starts = [_minutes(s.start) for _, s in physical if s.start is not None]
    ends = [_minutes(s.end) for _, s in physical if s.end is not None]
    first_minute = min([8 * 60, *(starts or [8 * 60])])
    last_minute = max([17 * 60, *(ends or [17 * 60])])
    # Meeting blocks round up to the half-hour grid: 50 minutes occupies
    # 60 visual minutes, 80 occupies 90.
    first_minute = first_minute // 30 * 30
    last_minute = (last_minute + 29) // 30 * 30

    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B3"
    ws.merge_cells("A1:F1")
    resource_label = "Instructor" if group == "instructor" else "Room"
    ws["A1"] = f"{resource_label} Schedule -- {resource}"
    ws["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="1F4E78")
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    headers = ["Time", *(day_label for _, day_label in _WEEKDAYS)]
    for column, value in enumerate(headers, start=1):
        cell = ws.cell(2, column, value)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="5B9BD5")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.column_dimensions["A"].width = 13
    for letter in "BCDEF":
        ws.column_dimensions[letter].width = 23

    slots = list(range(first_minute, last_minute, 30))
    light_border = Border(
        bottom=Side(style="hair", color="D9E2F3"),
        right=Side(style="hair", color="D9E2F3"),
    )
    for offset, minute in enumerate(slots, start=3):
        ws.cell(offset, 1, _clock(minute))
        ws.cell(offset, 1).alignment = Alignment(horizontal="right", vertical="top")
        ws.row_dimensions[offset].height = 18
        for column in range(1, 7):
            ws.cell(offset, column).border = light_border

    # Cells are claimed per atomic class, not per raw section -- a
    # HybridClass/CrossListingClass companion meeting landing on the same
    # slot as its own sibling is expected by design (one physical meeting
    # filed under two rows), not a double-booking. Only a slot already
    # claimed by a *different* class is a real conflict.
    occupied: dict[tuple[int, int], int] = {}
    ordered = sorted(
        physical, key=lambda pair: (pair[1].start or datetime.time(0, 0), pair[1].course_id)
    )
    for item, section in ordered:
        secondary = (
            f"{section.building} {section.room}".strip()
            if group == "instructor" else section.instructor
        )
        text = f"{section.course_id}\n{secondary or ''}\n{_clock_range(section)}"
        fill = color_by_class[id(item)]
        start_row = 3 + (_minutes(section.start) - first_minute) // 30
        duration = _minutes(section.end) - _minutes(section.start)
        visual_slots = max(1, (duration + 29) // 30)
        end_row = start_row + visual_slots - 1
        for day, _day_label in _WEEKDAYS:
            if day not in (section.days or ""):
                continue
            column = 2 + [w[0] for w in _WEEKDAYS].index(day)
            cells = {(r, column) for r in range(start_row, end_row + 1)}
            occupants = {occupied[c] for c in cells if c in occupied}
            if occupants == {id(item)}:
                # The same atomic class's own companion meeting -- merge
                # into the existing block instead of flagging anything.
                # start_row is this meeting's *own* row, which can land
                # inside (not at the top of) an already-merged block --
                # e.g. an 80-minute meeting rounds up to a 90-visual-minute
                # block (see visual_slots above), so a back-to-back
                # companion meeting immediately after it starts at a row
                # already swallowed by that rounding. ws.cell() on such a
                # row returns a read-only MergedCell, so resolve to the
                # block's real top-left anchor first.
                anchor = _merged_anchor(ws, start_row, column)
                if section.course_id not in (anchor.value or ""):
                    anchor.value = f"{anchor.value}\n/ {section.course_id}".strip()
                occupied |= {cell: id(item) for cell in cells}
                continue
            if occupants:
                # A genuinely different class landed on the same cell --
                # a real scheduling conflict. Keep both visible rather
                # than silently overwriting one: append to the existing
                # cell and flag it red instead of creating a second block.
                # Same MergedCell hazard as above.
                anchor = _merged_anchor(ws, start_row, column)
                anchor.value = f"{anchor.value or ''}\nCONFLICT: {text}".strip()
                anchor.fill = PatternFill("solid", fgColor="FF0000")
                anchor.font = Font(size=9, bold=True, color="FFFFFF")
                continue
            occupied |= {cell: id(item) for cell in cells}
            ws.merge_cells(
                start_row=start_row, start_column=column,
                end_row=end_row, end_column=column,
            )
            cell = ws.cell(start_row, column, text)
            cell.fill = PatternFill("solid", fgColor=fill)
            cell.font = Font(size=9, color="1F1F1F")
            cell.alignment = Alignment(
                horizontal="center", vertical="center", wrap_text=True
            )
            cell.border = Border(
                left=Side(style="thin", color="7F8C8D"),
                right=Side(style="thin", color="7F8C8D"),
                top=Side(style="thin", color="7F8C8D"),
                bottom=Side(style="thin", color="7F8C8D"),
            )

    if group == "instructor":
        unscheduled = [s for _, s in entries if s.is_online]
        if unscheduled:
            row_number = 3 + len(slots) + 2
            ws.cell(row_number, 1, "Online / TBA")
            ws.cell(row_number, 1).font = Font(bold=True, color="FFFFFF")
            ws.cell(row_number, 1).fill = PatternFill("solid", fgColor="7F8C8D")
            ws.merge_cells(
                start_row=row_number, start_column=2,
                end_row=row_number, end_column=6,
            )
            ws.cell(row_number, 2, ", ".join(s.course_id for s in unscheduled))
            ws.cell(row_number, 2).alignment = Alignment(wrap_text=True)

    ws.auto_filter.ref = f"A2:F{2 + len(slots)}"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = "1:2"


def _safe_sheet_title(value: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "_", value).strip("'") or "Schedule"
    base = base[:31]
    candidate = base
    counter = 2
    while candidate.casefold() in used:
        suffix = f" ({counter})"
        candidate = f"{base[:31 - len(suffix)]}{suffix}"
        counter += 1
    used.add(candidate.casefold())
    return candidate


_ATOMIC_CLASS_COLORS = (
    "E6F3FF",  # Light blue
    "E6FFE6",  # Light green
    "FFF2E6",  # Light orange
    "F0E6FF",  # Light purple
    "FFE6F2",  # Light pink
    "E6FFFF",  # Light cyan
    "FFFACD",  # Light yellow
    "F5F5DC",  # Light beige
    "E6E6FA",  # Light lavender
    "F0F8E6",  # Light mint
)


def _minutes(value: datetime.time) -> int:
    return value.hour * 60 + value.minute


def _clock(minutes: int) -> str:
    hour, minute = divmod(minutes, 60)
    suffix = "AM" if hour < 12 else "PM"
    shown = hour % 12 or 12
    return f"{shown}:{minute:02d} {suffix}"


def _clock_range(section: Section) -> str:
    if section.start is None or section.end is None:
        return ""
    return f"{_clock(_minutes(section.start))}-{_clock(_minutes(section.end))}"
