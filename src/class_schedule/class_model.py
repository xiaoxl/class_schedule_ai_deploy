"""Atomic class model backed by one or two CSV records.

This module has no dependency on Schedule and knows nothing about
collections of classes -- it only models a single table row (``Section``) and
a single normalized atomic class of one or two rows. ``NormalClass`` (one row)
is the base of the hierarchy; ``SpecialClass`` (two normalized rows) is the base
for the four two-row kinds -- ``FourCreditClass``, ``HybridClass``,
``CrossListingClass``, ``CoreqClass`` -- each of which owns its own
recognition rule and validation. Grouping many rows into many classes (and
back) is a collection-level concern that belongs to whatever owns the full
table -- e.g. ``Schedule`` -- not to this module.
"""

from __future__ import annotations

import datetime
from enum import StrEnum
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import ClassVar

from . import record_utils
from .instructor_identity import canonical_instructor

# Course numbers encode credit hours in their last digit by convention
# (e.g. "1914" -> 4 credits, "0803" -> 3 credits). These full-course
# exceptions are authoritative and are applied while constructing Section,
# before the record enters an atomic class or is flattened back to a draft.
_CREDIT_HOUR_OVERRIDES: dict[str, float] = {"MATH 1110": 2.0}


class DeliveryMode(StrEnum):
    """How a section is delivered, independent of whether its time is known."""

    IN_PERSON = "in_person"
    ONLINE = "online"
    ARRANGED = "arranged"


def _infer_credit_hours(number: str) -> int:
    return int(number[-1]) if number and number[-1].isdigit() else 0


@dataclass(slots=True)
class Section:
    """One CSV record inside an atomic class."""

    subject: str
    number: str
    section: str
    time_slot: str
    duration: int | None
    room: str
    instructor: str
    building: str = ""
    type: str = ""
    title: str = ""
    credits: float | None = None
    cross_list: str = ""

    def __post_init__(self) -> None:
        self.subject = record_utils.text(self.subject).upper()
        self.number = record_utils.text(self.number)
        self.section = record_utils.text(self.section)
        self.instructor = canonical_instructor(record_utils.text(self.instructor))
        self.time_slot = record_utils.text(self.time_slot)
        if not self.subject or not self.number or not self.section:
            raise ValueError("Each record requires Subject, Number, and Section")
        credit_override = _CREDIT_HOUR_OVERRIDES.get(
            f"{self.subject} {self.number}"
        )
        if credit_override is not None:
            self.credits = credit_override
        record_utils.parse_slot(self.time_slot)
        if not self.is_online and self.duration is None:
            raise ValueError(
                "Each physical record requires a Duration in minutes"
            )
        if self.duration is not None and self.duration <= 0:
            raise ValueError("Duration in minutes must be positive")

    @property
    def course_id(self) -> str:
        return f"{self.subject} {self.number}-{self.section}"

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.subject, self.number, self.section)

    @property
    def delivery_mode(self) -> DeliveryMode:
        """The single source of truth for online/arranged/in-person.

        Every other "does this need a physical slot" check in the codebase
        (``is_online`` here, and every caller of it) derives from this
        property instead of re-parsing ``time_slot`` itself -- see
        ``docs/codes.md`` for the full rule.
        """
        if self.time_slot.upper() == "ONLINE":
            return DeliveryMode.ONLINE
        if self.time_slot.upper() in {"", "TBA"}:
            return DeliveryMode.ARRANGED
        return DeliveryMode.IN_PERSON

    @property
    def is_online(self) -> bool:
        """Shorthand for "no physical time/room to schedule".

        Derived from ``delivery_mode``, not a separate check: true for
        ONLINE, TBA, and blank alike. Use ``delivery_mode`` when those three
        must be told apart.
        """
        return self.delivery_mode is not DeliveryMode.IN_PERSON

    @property
    def has_meeting_time(self) -> bool:
        return self.days is not None and self.start is not None

    @property
    def credit_hours(self) -> float:
        """Credits normalized at construction, otherwise inferred by number."""
        return (
            self.credits
            if self.credits is not None
            else _infer_credit_hours(self.number)
        )

    @property
    def days(self) -> str | None:
        return record_utils.parse_slot(self.time_slot)[0]

    @property
    def start(self) -> datetime.time | None:
        return record_utils.parse_slot(self.time_slot)[1]

    @property
    def end(self) -> datetime.time | None:
        if self.start is None or self.duration is None:
            return None
        return record_utils.add_minutes(self.start, self.duration)

    @classmethod
    def from_record(cls, row: Mapping[str, object]) -> "Section":
        row = record_utils.normalize_columns(row)
        get = record_utils.value
        text = record_utils.text
        slot = text(get(row, "Time Slot"))
        if not slot:
            slot = record_utils.format_slot(
                get(row, "Days"), get(row, "Start")
            )
        raw_duration = get(row, "Duration")
        duration = (
            int(float(raw_duration))
            if text(raw_duration)
            else record_utils.duration_from_times(
                get(row, "Start"), get(row, "End")
            )
        )
        raw_credits = get(row, "Credits")
        return cls(
            subject=text(get(row, "Subject")),
            number=text(get(row, "Number")),
            section=text(get(row, "Section")),
            time_slot=slot,
            duration=duration,
            room=text(get(row, "Room")),
            instructor=text(get(row, "Instructor")),
            building=text(get(row, "Building")),
            type=text(get(row, "Type")),
            title=text(get(row, "Title")),
            credits=float(raw_credits) if text(raw_credits) else None,
            cross_list=text(get(row, "Cross-List")),
        )

    def to_record(self) -> dict[str, object]:
        days, start = record_utils.parse_slot(self.time_slot)
        end = (
            record_utils.add_minutes(start, self.duration)
            if start is not None and self.duration is not None
            else None
        )
        return {
            "Subject": self.subject,
            "Number": self.number,
            "Section": self.section,
            "Type": self.type or None,
            "Title": self.title or None,
            "Credits": self.credits,
            "Instructor": self.instructor or None,
            "Time Slot": self.time_slot or None,
            "Duration": self.duration,
            "Days": days,
            "Start": start,
            "End": end,
            "Room": self.room or None,
            "Building": self.building or None,
            "Cross-List": self.cross_list or None,
            "Delivery Mode": self.delivery_mode.value,
        }


@dataclass(slots=True)
class NormalClass:
    """A class represented by exactly one CSV record.

    Base of the whole hierarchy: ``SpecialClass`` (two CSV records) and its
    four kinds inherit from this class and override ``validate`` to add
    their own recognition rule, plus ``num_of_rows``. A class's kind is its
    Python type -- ``isinstance``/``type()`` -- there is no separate tag.
    """

    sections: tuple[Section, ...]

    num_of_rows: ClassVar[int] = 1

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise ``ValueError`` unless ``self.sections`` is legal.

        Subclasses call ``super().validate()`` first, then add their own
        recognition rule. This base check is just the row count -- each
        individual ``Section`` is already guaranteed legal on its own by
        the time it gets here, since ``Section.__post_init__`` validates
        it at construction; an invalid ``Section`` can't exist to be
        passed in.
        """
        if len(self.sections) != self.num_of_rows:
            detail = (
                f" ({self.sections[0].course_id})" if self.sections else ""
            )
            raise ValueError(
                f"{type(self).__name__} requires exactly "
                f"{self.num_of_rows} CSV record(s){detail}"
            )

    # ---- import (CSV records -> objects) ----

    @classmethod
    def from_records(
        cls, records: Iterable[Mapping[str, object]]
    ) -> "NormalClass":
        """Convert CSV records into a single atomic class of type ``cls``.

        The kind is ``cls`` itself -- call it on the specific class you
        want, e.g. ``CoreqClass.from_records(records)``. ``validate`` (via
        ``__post_init__``) is what actually rejects a wrong row count or
        content; this only parses.
        """
        sections = tuple(Section.from_record(row) for row in records)
        return cls(sections)

    # ---- export (objects -> CSV records) ----

    @property
    def course_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.course_id for item in self.sections))

    @property
    def credit_hours(self) -> float:
        """Credit hours for this atomic class.

        A class always represents one course a student enrolls in once,
        even when it's built from two CSV records (FourCreditClass,
        HybridClass, CrossListingClass) -- so this counts once, inferred
        from the first section's course number. ``CoreqClass`` overrides
        this since it links two distinct courses.
        """
        return self.sections[0].credit_hours

    def to_records(self) -> list[dict[str, object]]:
        """Return one or two dictionaries ready for ``csv.DictWriter``."""
        return [section.to_record() for section in self.sections]

    # ---- solver integration ----

    def pairwise_predicate(self) -> Callable[[Section, Section], bool] | None:
        """The two-row legality check ``validate`` also enforces, if any.

        An instance method (not a classmethod) because a subclass -- see
        ``CrossListingClass`` -- may need per-instance state to decide the
        rule, not just its type. ``solver/constraints.py`` compiles
        whatever this returns into CP-SAT constraints ahead of the search,
        once per candidate pair -- it is the one place besides ``validate``
        that needs this rule, and it
        gets it from here rather than keeping a second, separately
        maintained mapping of kind -> predicate.
        """
        return None

    # ---- modification (subclasses may enforce kind-specific behavior) ----

    def change_time(
        self, time_slot: str, *, record: int | None = None
    ) -> "NormalClass":
        """Change a slot on every row, or on one zero-based record."""
        record_utils.parse_slot(time_slot)
        return self._change(
            record, time_slot=record_utils.text(time_slot)
        )

    def change_room(self, room: str, *, record: int | None = None) -> "NormalClass":
        """Change the room on every row, or on one zero-based record."""
        return self._change(record, room=record_utils.text(room))

    def change_instructor(
        self, instructor: str, *, record: int | None = None
    ) -> "NormalClass":
        """Change the instructor on every row, or on one zero-based record."""
        return self._change(
            record, instructor=record_utils.text(instructor)
        )

    def _change(self, record: int | None, **changes: object) -> "NormalClass":
        if record is not None and not 0 <= record < len(self.sections):
            raise IndexError(f"CSV record index out of range: {record}")
        updated = tuple(
            replace(section, **changes)
            if record is None or index == record
            else section
            for index, section in enumerate(self.sections)
        )
        return replace(self, sections=updated)

    # ---- unified web/API editing ----
    #
    # The single source of truth for what a live editor (the web UI, or
    # any future API caller) calls "linking": does editing "instructor",
    # "time", or "room" on one row also have to touch the class's other
    # row? See docs/codes.md's linking matrix. Callers must never
    # re-derive this from current field values or duplicate it per kind
    # themselves (that was the bug this replaced -- e.g. inferring
    # linkage from whether the two rows' Time Slot currently happens to
    # match, which conflates "are they the same right now" with "are
    # they required to be").

    def edit_targets(self, field: str, record_index: int) -> tuple[int, ...]:
        """Which record indices an edit to ``field`` must also touch,
        given the row the edit was made through. Default: only that row.
        """
        return (record_index,)

    def apply_edit(
        self, field: str, record_index: int, **changes: object,
    ) -> "NormalClass":
        """Apply one field edit through ``edit_targets``, returning a new
        instance. ``changes`` are the actual ``Section`` attribute(s)
        this field touches (already resolved by the caller -- e.g. a
        "room" edit supplies both ``room`` and ``building``).
        """
        if not 0 <= record_index < len(self.sections):
            raise IndexError(f"CSV record index out of range: {record_index}")
        targets = self.edit_targets(field, record_index)
        updated = tuple(
            replace(section, **changes) if index in targets else section
            for index, section in enumerate(self.sections)
        )
        return replace(self, sections=updated)


@dataclass(slots=True)
class SpecialClass(NormalClass):
    """Base of the four kinds represented by exactly two CSV records."""

    num_of_rows: ClassVar[int] = 2


@dataclass(slots=True)
class FourCreditClass(SpecialClass):
    """Two same-course rows: one MWF, one T or R, same instructor."""

    MAX_START_DIFFERENCE_MINUTES: ClassVar[int] = 90
    schedule_issue_rule: ClassVar[str] = "four_credit_invalid"
    schedule_issues: tuple[str, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        super(FourCreditClass, self).__post_init__()
        left, right = self.sections
        self.schedule_issues = self._issues(left, right)

    @classmethod
    def _issues(cls, left: Section, right: Section) -> tuple[str, ...]:
        """Every reason ``is_valid_schedule`` might fail, as a report.

        Construction never rejects a row-level adjustment (see
        ``docs/codes.md``); this is what ``validate`` calls to detect and
        describe an illegal state after the fact instead.
        """
        if left.identity != right.identity:
            return (
                f"{left.course_id} / {right.course_id} four-credit rows "
                "are not the same course",
            )
        if not cls.is_four_credit(left, right):
            return (
                f"{left.course_id} four-credit rows must share an "
                "instructor and pair one MWF meeting with one T or R "
                "meeting",
            )
        difference = cls.start_difference_minutes(left, right)
        if difference > cls.MAX_START_DIFFERENCE_MINUTES:
            return (
                f"{left.course_id} four-credit meetings start {difference} "
                f"minutes apart; maximum is "
                f"{cls.MAX_START_DIFFERENCE_MINUTES} minutes",
            )
        return ()

    @staticmethod
    def is_four_credit(left: Section, right: Section) -> bool:
        if left.is_online or right.is_online:
            return False
        if left.instructor != right.instructor:
            return False
        return {left.days, right.days} in ({"MWF", "T"}, {"MWF", "R"})

    @staticmethod
    def start_difference_minutes(left: Section, right: Section) -> int:
        """Absolute difference between the two physical start times."""
        if left.start is None or right.start is None:
            return 0
        left_minutes = left.start.hour * 60 + left.start.minute
        right_minutes = right.start.hour * 60 + right.start.minute
        return abs(left_minutes - right_minutes)

    @classmethod
    def is_valid_schedule(cls, left: Section, right: Section) -> bool:
        """The full rule the solver enforces (via ``pairwise_predicate``)."""
        return not cls._issues(left, right)

    def pairwise_predicate(self) -> Callable[[Section, Section], bool] | None:
        return self.is_valid_schedule

    def edit_targets(self, field: str, record_index: int) -> tuple[int, ...]:
        # Instructor must match (is_four_credit); the MWF and T/R meetings
        # are never the same time or necessarily the same room.
        return (0, 1) if field == "instructor" else (record_index,)

    def change_time(
        self, time_slot: str, *, record: int | None = None
    ) -> "FourCreditClass":
        """Change one meeting.

        Without ``record``, the target is inferred from whether
        ``time_slot`` is an MWF slot or a T/R slot -- whichever of the two
        existing meetings shares that role gets replaced. Pass ``record``
        to override this and address a meeting by index directly.
        """
        if record is None:
            new_days, _ = record_utils.parse_slot(time_slot)
            left = self.sections[0]
            record = 0 if (new_days == "MWF") == (left.days == "MWF") else 1
        return super(FourCreditClass, self).change_time(time_slot, record=record)


@dataclass(slots=True)
class HybridClass(SpecialClass):
    """An M- or F-prefixed physical meeting plus its derived ONLINE row.

    Import may provide only the physical row or may include a stale companion;
    construction always rebuilds the companion from the physical authority.
    The normalized atomic object and its flattened export both contain two rows.
    """

    schedule_issue_rule: ClassVar[str] = "hybrid_invalid"
    schedule_issues: tuple[str, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        physical = [section for section in self.sections if section.has_meeting_time]
        if len(physical) == 1 and len(self.sections) in (1, 2):
            meeting = physical[0]
            companion = self._online_companion(meeting)
            if len(self.sections) == 1:
                self.sections = (companion, meeting)
            else:
                self.sections = tuple(
                    section if section.has_meeting_time else companion
                    for section in self.sections
                )
        super(HybridClass, self).__post_init__()
        left, right = self.sections
        self.schedule_issues = () if self.is_valid_schedule(left, right) else (
            f"{left.course_id} rows do not form a valid hybrid pairing: "
            "need the same course, one M- or F-prefixed physical meeting "
            "with a room and a companion without one, and a shared "
            "instructor",
        )

    @staticmethod
    def _online_companion(physical: Section) -> Section:
        return replace(
            physical,
            time_slot="ONLINE",
            duration=None,
            room="",
            building="",
            cross_list="",
        )

    @property
    def physical_section(self) -> Section:
        """The row with a real meeting time, if any.

        Falls back to the first row rather than raising when neither (or
        both) rows qualify -- ``is_hybrid`` no longer guarantees exactly
        one match (see ``schedule_issues``), but this class must stay
        readable/exportable regardless.
        """
        for section in self.sections:
            if section.has_meeting_time:
                return section
        return self.sections[0]

    @property
    def online_section(self) -> Section:
        """The row without a real meeting time, if any -- see ``physical_section``."""
        for section in self.sections:
            if not section.has_meeting_time:
                return section
        return self.sections[1]

    @property
    def building(self) -> str:
        return self.physical_section.building

    @property
    def room(self) -> str:
        return self.physical_section.room

    @property
    def time_slot(self) -> str:
        return self.physical_section.time_slot

    @staticmethod
    def is_hybrid(left: Section, right: Section) -> bool:
        if left.instructor != right.instructor:
            return False
        physical = left if left.has_meeting_time else right
        if not HybridClass.is_hybrid_physical(physical):
            return False
        return (
            left.has_meeting_time != right.has_meeting_time
            and all(
                section.has_meeting_time == bool(section.room)
                for section in (left, right)
            )
        )

    @staticmethod
    def is_hybrid_physical(section: Section) -> bool:
        """Return whether one imported row is sufficient to build a Hybrid."""
        return (
            section.section.upper().startswith(("M", "F"))
            and section.has_meeting_time
            and bool(section.room)
        )

    @staticmethod
    def is_valid_schedule(left: Section, right: Section) -> bool:
        """The full rule the solver enforces (via ``pairwise_predicate``)."""
        return left.identity == right.identity and HybridClass.is_hybrid(left, right)

    def pairwise_predicate(self) -> Callable[[Section, Section], bool] | None:
        return self.is_valid_schedule

    def edit_targets(self, field: str, record_index: int) -> tuple[int, ...]:
        # Instructor must match; the companion row has no time/room of its
        # own to edit at all (see docs/codes.md -- callers should disable
        # those controls for it), so route either row's time/room edit to
        # the physical one.
        if field == "instructor":
            return (0, 1)
        return (self.sections.index(self.physical_section),)

    def to_records(self) -> list[dict[str, object]]:
        """Flatten with an ONLINE row regenerated from the physical row."""
        physical = self.physical_section
        companion = self._online_companion(physical)
        return [
            (companion if not section.has_meeting_time else physical).to_record()
            for section in self.sections
        ]

    def change_time(
        self, time_slot: str, *, record: int | None = None
    ) -> "HybridClass":
        target = self.sections.index(self.physical_section) if record is None else record
        return super(HybridClass, self).change_time(time_slot, record=target)

    def change_room(
        self, room: str, *, record: int | None = None
    ) -> "HybridClass":
        target = self.sections.index(self.physical_section) if record is None else record
        return super(HybridClass, self).change_room(room, record=target)


@dataclass(slots=True)
class CrossListingClass(SpecialClass):
    """Two catalog rows that represent one cross-listed offering."""

    COURSE_PAIRS: ClassVar[list[set[str]]] = [
        {"MATH 5173", "STAT 4173"},
    ]
    schedule_issue_rule: ClassVar[str] = "cross_listing_invalid"
    synced_fields: frozenset[str] = field(init=False, default=frozenset())
    schedule_issues: tuple[str, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        super(CrossListingClass, self).__post_init__()
        left, right = self.sections
        self.synced_fields = self._synced_fields(left, right)
        self.schedule_issues = self._issues(left, right)

    @staticmethod
    def _synced_fields(left: Section, right: Section) -> frozenset[str]:
        """Which of {instructor, room, time} this specific pair's source
        data already had matching -- decided once at construction and
        fixed for the life of the instance (see docs/codes.md). Only
        locked fields are enforced (by ``pairwise_predicate``, hence by
        the solver); an unlocked field is free to diverge independently.
        A field with no evidence either way (both sides simply equal,
        e.g. two freshly synthesized rows) still counts as locked --
        "no information" defaults to "must match", never to "may differ".
        """
        locked = set()
        if left.instructor == right.instructor:
            locked.add("instructor")
        if left.room == right.room and left.building == right.building:
            locked.add("room")
        if left.time_slot == right.time_slot and left.duration == right.duration:
            locked.add("time")
        return frozenset(locked)

    @classmethod
    def from_configured_sections(
        cls,
        sections: tuple[Section, Section],
        *,
        synced_fields: frozenset[str] | None = None,
    ) -> "CrossListingClass":
        """Build an explicitly configured pair without a course whitelist.

        ``synced_fields`` lets a ``courses.toml`` relationship declare which
        fields to keep in sync as a persisted decision (see docs/codes.md)
        instead of re-deriving it from whatever the current rows happen to
        show; omitted, it falls back to the same auto-detection every other
        construction path uses.
        """
        item = cls.__new__(cls)
        item.sections = sections
        SpecialClass.validate(item)
        left, right = sections
        item.synced_fields = (
            synced_fields if synced_fields is not None
            else cls._synced_fields(left, right)
        )
        item.schedule_issues = cls._issues(left, right)
        return item

    @classmethod
    def _issues(cls, left: Section, right: Section) -> tuple[str, ...]:
        """Every reason ``is_valid_schedule`` might fail, as a report.

        Construction never rejects a row-level adjustment (see
        docs/codes.md); this is what a caller uses to detect and describe
        an illegal state after the fact instead.
        """
        if left.identity == right.identity:
            return (
                f"{left.course_id} cross-listing rows must be two "
                "different courses",
            )
        if not cls.is_cross_listing(left, right):
            return (
                f"{left.course_id} / {right.course_id} rows are not "
                "recognized as one cross-listing (no shared Cross-List "
                "value, known course pair, or honors-section pairing)",
            )
        return ()

    @classmethod
    def is_valid_schedule(cls, left: Section, right: Section) -> bool:
        """The full rule the solver enforces (via ``pairwise_predicate``),
        combined with whichever fields this instance's ``synced_fields``
        locked -- see ``pairwise_predicate``.
        """
        return not cls._issues(left, right)

    @staticmethod
    def is_cross_listing(left: Section, right: Section) -> bool:
        if bool(left.cross_list) and left.cross_list == right.cross_list:
            return True
        return (
            CrossListingClass.is_known_pair(left, right)
            or CrossListingClass.is_honors_pair(left, right)
        )

    @classmethod
    def is_known_pair(cls, left: Section, right: Section) -> bool:
        courses = {
            f"{left.subject} {left.number}",
            f"{right.subject} {right.number}",
        }
        return (
            left.section == right.section
            and any(courses == pair for pair in cls.COURSE_PAIRS)
        )

    @staticmethod
    def is_shared_meeting(left: Section, right: Section) -> bool:
        """Whether two cross-listed records currently describe one physical
        meeting -- true exactly when all of ``synced_fields``' fields
        would be, i.e. instructor, time, duration, room, and building all
        match. Purely descriptive; ``synced_fields``/``pairwise_predicate``
        are what actually get enforced (see ``docs/codes.md``).
        """
        return (
            left.instructor == right.instructor
            and left.time_slot == right.time_slot
            and left.duration == right.duration
            and left.room == right.room
            and left.building == right.building
        )

    def pairwise_predicate(self) -> Callable[[Section, Section], bool] | None:
        """Recognition (``is_cross_listing``) always holds, plus only the
        fields this specific pair started out sharing.

        Unlike the other two-row kinds' scheduling rules, field-matching
        isn't one fixed rule for the whole type -- ``synced_fields`` was
        decided per instance at construction (see docs/codes.md), so a
        pair that started matching stays matching, while a pair that
        started independent (e.g. two different rooms) stays free to
        diverge further.
        """
        locked = self.synced_fields

        def _predicate(left: Section, right: Section) -> bool:
            if not self.is_valid_schedule(left, right):
                return False
            if "instructor" in locked and left.instructor != right.instructor:
                return False
            if "room" in locked and (
                left.room != right.room or left.building != right.building
            ):
                return False
            if "time" in locked and (
                left.time_slot != right.time_slot or left.duration != right.duration
            ):
                return False
            return True

        return _predicate

    def edit_targets(self, field: str, record_index: int) -> tuple[int, ...]:
        # The one kind whose linking is per-instance, not per-kind -- see
        # synced_fields (docs/codes.md): a field the source data already
        # had matching stays linked, one that didn't stays independent.
        return (0, 1) if field in self.synced_fields else (record_index,)

    def apply_edit(
        self, field: str, record_index: int, **changes: object,
    ) -> "CrossListingClass":
        # NormalClass.apply_edit ends in replace(self, sections=...), which
        # reruns __post_init__ -- and __post_init__ always *auto-detects*
        # synced_fields from the (now-edited) rows. Left alone, that would
        # silently override this instance's real synced_fields (whatever
        # from_configured_sections was given, or whatever construction
        # auto-detected) with a fresh guess from the post-edit values --
        # exactly the "re-guessed every time" failure mode synced_fields
        # exists to prevent (see docs/codes.md). synced_fields is a fixed,
        # per-instance decision for the life of the instance; only a fresh
        # load (from_configured_sections) is allowed to set it.
        updated = super(CrossListingClass, self).apply_edit(
            field, record_index, **changes,
        )
        updated.synced_fields = self.synced_fields
        return updated

    @staticmethod
    def is_honors_pair(left: Section, right: Section) -> bool:
        """Same course, one regular section and one 'H'-prefixed honors
        section with the same trailing digits (e.g. '001' / 'H01').

        Recognition is purely structural -- it does not require the two
        rows to share an instructor/room/time; see ``is_shared_meeting``.
        """
        if left.subject != right.subject or left.number != right.number:
            return False
        a, b = left.section.upper(), right.section.upper()
        honors, regular = (a, b) if a.startswith("H") else (b, a)
        if not honors.startswith("H") or regular.startswith("H"):
            return False
        return honors[1:] == regular[1:]


@dataclass(slots=True)
class CoreqClass(SpecialClass):
    """Two different-course rows in the same section, matching the coreq whitelist."""

    COURSE_PAIRS: ClassVar[list[set[str]]] = [
        {"MATH 1003", "MATH 0803"},
        {"MATH 1113", "MATH 0903"},
        {"MATH 1113", "MATH 1110"},
    ]
    schedule_issue_rule: ClassVar[str] = "coreq_invalid"
    schedule_issues: tuple[str, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        super(CoreqClass, self).__post_init__()
        left, right = self.sections
        self.schedule_issues = self._issues(left, right)

    @classmethod
    def from_configured_sections(
        cls, sections: tuple[Section, Section],
    ) -> "CoreqClass":
        """Build an explicitly configured pair while retaining coreq behavior."""
        item = cls.__new__(cls)
        item.sections = sections
        SpecialClass.validate(item)
        left, right = sections
        item.schedule_issues = cls._issues(left, right)
        return item

    @property
    def credit_hours(self) -> float:
        # Unlike the other two-record kinds, a coreq pair is two distinct
        # courses a student enrolls in separately, so their hours add up.
        left, right = self.sections
        return sum(
            section.credit_hours
            for section in (left, right)
        )

    @classmethod
    def is_coreq_pair(cls, left: Section, right: Section) -> bool:
        # A "TC"-prefixed section is otherwise a concurrent (dual-credit)
        # web course, but the same whitelist + same-section-number match
        # used below is trustworthy enough on its own -- there are only
        # three whitelisted course-number pairs total, so a TC pair that
        # happens to match one of them by section number is a genuine
        # online coreq, not a coincidence. (P/ET/A-prefixed
        # concurrent-enrollment sections are a different, unrelated
        # pattern -- those are dropped even earlier, before Schedule's
        # grouping ever sees them -- see
        # ``schedule_model._IGNORED_SECTION_PREFIXES``.)
        course_ids = {
            f"{left.subject} {left.number}", f"{right.subject} {right.number}"
        }
        return left.section == right.section and course_ids in cls.COURSE_PAIRS

    @staticmethod
    def _back_to_back(left: Section, right: Section) -> bool:
        """Shared weekday, and a gap of 15 minutes or less either way."""
        if left.start is None or right.start is None:
            return False
        left_start = left.start.hour * 60 + left.start.minute
        right_start = right.start.hour * 60 + right.start.minute
        left_end = left_start + (left.duration or 0)
        right_end = right_start + (right.duration or 0)
        shared_days = bool(set(left.days or "") & set(right.days or ""))
        return shared_days and (
            0 <= right_start - left_end <= 15
            or 0 <= left_start - right_end <= 15
        )

    @classmethod
    def _issues(cls, left: Section, right: Section) -> tuple[str, ...]:
        """Every reason ``is_valid_schedule`` might fail, as a report.

        Construction never rejects a row-level adjustment (see
        docs/codes.md); this is what a caller uses to detect and describe
        an illegal state after the fact instead. The coreq whitelist
        (``is_coreq_pair``) plays no role here -- it is only ever
        consulted at grouping time, to decide whether two rows become a
        CoreqClass in the first place.
        """
        if left.identity == right.identity:
            return (f"{left.course_id} coreq rows must be two different courses",)
        label = f"{left.course_id} / {right.course_id}"
        if left.instructor != right.instructor:
            return (f"{label} coreq meetings do not share an instructor",)
        if left.is_online and right.is_online:
            return ()
        if left.is_online or right.is_online:
            return (
                f"{label} coreq meetings must both be online or both have "
                "a physical meeting",
            )
        if left.start is None or right.start is None:
            return (f"{label} coreq meetings require a valid time",)
        left_start = left.start.hour * 60 + left.start.minute
        right_start = right.start.hour * 60 + right.start.minute
        shared_days = bool(set(left.days or "") & set(right.days or ""))
        back_to_back = cls._back_to_back(left, right)
        if shared_days and not back_to_back:
            # Same weekday on both sides but not back-to-back: the two
            # meetings would overlap or nearly overlap on a shared day --
            # a real conflict, not a valid coreq pairing.
            return (
                f"{label} coreq meetings conflict on a shared weekday "
                "without being back-to-back",
            )
        if back_to_back:
            if not (
                bool(left.room)
                and left.room == right.room
                and left.building == right.building
            ):
                return (
                    f"{label} coreq meetings are back-to-back but not in "
                    f"the same room ({left.building} {left.room} / "
                    f"{right.building} {right.room})",
                )
            return ()
        gap = abs(left_start - right_start)
        if gap > 30:
            return (
                f"{label} coreq meetings start {gap} minutes apart on "
                "different weekdays; maximum is 30 minutes",
            )
        return ()

    @classmethod
    def is_valid_schedule(cls, left: Section, right: Section) -> bool:
        """The full rule the solver enforces (via ``pairwise_predicate``):
        both sides online, or same instructor and either back-to-back in
        the same room on a shared weekday or starting within 30 minutes
        of each other on disjoint weekdays.
        """
        return not cls._issues(left, right)

    def pairwise_predicate(self) -> Callable[[Section, Section], bool] | None:
        return self.is_valid_schedule

    def edit_targets(self, field: str, record_index: int) -> tuple[int, ...]:
        # Instructor must match; the two meetings are never the same
        # time. Room only has to match when the pair is currently
        # back-to-back on a shared weekday (is_valid_schedule's rule) --
        # otherwise each meeting's room is independent.
        if field == "instructor":
            return (0, 1)
        if field == "room" and self._back_to_back(*self.sections):
            return (0, 1)
        return (record_index,)

    def apply_edit(
        self, field: str, record_index: int, **changes: object,
    ) -> "CoreqClass":
        updated = super(CoreqClass, self).apply_edit(field, record_index, **changes)
        if field != "time":
            return updated
        left, right = updated.sections
        if self._back_to_back(left, right) and not (
            left.room and left.room == right.room and left.building == right.building
        ):
            # This edit just made the pair back-to-back on a shared
            # weekday, which requires a matching room (is_valid_schedule)
            # -- follow whichever row wasn't just moved, rather than
            # immediately reporting a fresh coreq_invalid room mismatch.
            other = updated.sections[1 - record_index]
            matched = tuple(
                replace(section, room=other.room, building=other.building)
                if index == record_index else section
                for index, section in enumerate(updated.sections)
            )
            updated = replace(updated, sections=matched)
        return updated

    def change_time(
        self, time_slot: str, *, record: int | None
    ) -> "CoreqClass":
        """Change one meeting's time.

        ``record`` (0 or 1) is required -- coreq's two meetings can never
        share the same time (they must be back-to-back or up to 30
        minutes apart), so there is no sensible "change both" default.
        """
        return super(CoreqClass, self).change_time(time_slot, record=record)


# Every atomic class kind derives from NormalClass, so this is the shared
# root type used by collection and solver annotations.
Class = NormalClass
