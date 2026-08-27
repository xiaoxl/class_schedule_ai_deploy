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
from collections.abc import Iterable, Mapping
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


@dataclass(slots=True)
class SpecialClass(NormalClass):
    """Base of the four kinds represented by exactly two CSV records."""

    num_of_rows: ClassVar[int] = 2


@dataclass(slots=True)
class FourCreditClass(SpecialClass):
    """Two same-course rows: one MWF, one T or R, same instructor."""

    MAX_START_DIFFERENCE_MINUTES: ClassVar[int] = 90
    schedule_issues: tuple[str, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        super(FourCreditClass, self).__post_init__()
        difference = self.start_difference_minutes(*self.sections)
        self.schedule_issues = (
            (
                f"{self.course_ids[0]} four-credit meetings start "
                f"{difference} minutes apart; maximum is "
                f"{self.MAX_START_DIFFERENCE_MINUTES} minutes"
            ),
        ) if difference > self.MAX_START_DIFFERENCE_MINUTES else ()

    def validate(self) -> None:
        super(FourCreditClass, self).validate()
        left, right = self.sections
        if left.identity != right.identity:
            raise ValueError(
                f"{type(self).__name__} requires two records for the same "
                f"course ({left.course_id} / {right.course_id})"
            )
        if not self.is_four_credit(left, right):
            raise ValueError(
                "Four-credit class requires one MWF and one T or R "
                "meeting, with the same instructor "
                f"({left.course_id})"
            )

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
        """Strict pairing rule used when generating an adjusted schedule."""
        return (
            cls.is_four_credit(left, right)
            and cls.start_difference_minutes(left, right)
            <= cls.MAX_START_DIFFERENCE_MINUTES
        )

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
        return next(
            section for section in self.sections if section.has_meeting_time
        )

    @property
    def online_section(self) -> Section:
        return next(
            section for section in self.sections if not section.has_meeting_time
        )

    @property
    def building(self) -> str:
        return self.physical_section.building

    @property
    def room(self) -> str:
        return self.physical_section.room

    @property
    def time_slot(self) -> str:
        return self.physical_section.time_slot

    def validate(self) -> None:
        super(HybridClass, self).validate()
        left, right = self.sections
        if left.identity != right.identity:
            raise ValueError(
                f"{type(self).__name__} requires two records for the same "
                f"course ({left.course_id} / {right.course_id})"
            )
        if not self.is_hybrid(left, right):
            raise ValueError(
                "Hybrid requires an M- or F-prefixed section with one "
                "physical record having a room and one ONLINE/TBA/blank "
                "record without a room "
                f"({left.course_id})"
            )

    @staticmethod
    def is_hybrid(left: Section, right: Section) -> bool:
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

    @classmethod
    def from_configured_sections(
        cls, sections: tuple[Section, Section],
    ) -> "CrossListingClass":
        """Build an explicitly configured pair without a course whitelist."""
        item = cls.__new__(cls)
        item.sections = sections
        SpecialClass.validate(item)
        left, right = sections
        if left.identity == right.identity:
            raise ValueError("Configured cross-listing requires different identities")
        if not cls.is_shared_meeting(left, right):
            raise ValueError("Configured cross-listing rows must share one meeting")
        return item

    def validate(self) -> None:
        super(CrossListingClass, self).validate()
        left, right = self.sections
        if left.identity == right.identity:
            raise ValueError(
                "Cross-listing requires two different course identities "
                f"({left.course_id})"
            )
        if not self.is_cross_listing(left, right):
            raise ValueError(
                "Cross-listing rows require the same non-empty Cross-List "
                "value, a known course pair with the same section, or an "
                "honors-section pair (e.g. '001'/'H01') with the same "
                "instructor, room, and time "
                f"({left.course_id} / {right.course_id})"
            )

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
        """Whether two cross-listed records describe one physical meeting."""
        return (
            left.instructor == right.instructor
            and left.time_slot == right.time_slot
            and left.duration == right.duration
            and left.room == right.room
            and left.building == right.building
        )

    @staticmethod
    def is_honors_pair(left: Section, right: Section) -> bool:
        """Same course, one regular section and one 'H'-prefixed honors
        section with the same trailing digits (e.g. '001' / 'H01'),
        meeting at the same time, room, and instructor."""
        if left.subject != right.subject or left.number != right.number:
            return False
        a, b = left.section.upper(), right.section.upper()
        honors, regular = (a, b) if a.startswith("H") else (b, a)
        if not honors.startswith("H") or regular.startswith("H"):
            return False
        if honors[1:] != regular[1:]:
            return False
        return (
            left.instructor == right.instructor
            and left.room == right.room
            and left.time_slot == right.time_slot
        )


@dataclass(slots=True)
class CoreqClass(SpecialClass):
    """Two different-course rows in the same section, matching the coreq whitelist."""

    COURSE_PAIRS: ClassVar[list[set[str]]] = [
        {"MATH 1003", "MATH 0803"},
        {"MATH 1113", "MATH 0903"},
        {"MATH 1113", "MATH 1110"},
    ]

    @classmethod
    def from_configured_sections(
        cls, sections: tuple[Section, Section],
    ) -> "CoreqClass":
        """Build an explicitly configured pair while retaining coreq behavior."""
        item = cls.__new__(cls)
        item.sections = sections
        SpecialClass.validate(item)
        left, right = sections
        if left.identity == right.identity:
            raise ValueError("Configured coreq requires two different courses")
        if not cls.is_valid_schedule(left, right):
            raise ValueError(
                "Configured coreq does not satisfy the CoreqClass schedule rules"
            )
        return item

    def validate(self) -> None:
        super(CoreqClass, self).validate()
        left, right = self.sections
        if not self.is_coreq_pair(left, right):
            raise ValueError(
                "Unsupported coreq course pair "
                f"({left.course_id} / {right.course_id})"
            )
        if not self.is_valid_schedule(left, right):
            raise ValueError(
                "Coreq meetings must share an instructor, and (unless "
                "both lack a physical meeting) be either back-to-back with a gap of "
                "15 minutes or less in the same non-empty building/room "
                "on a shared weekday, or start within 30 minutes of each "
                "other on disjoint weekdays "
                f"({left.course_id} / {right.course_id})"
            )

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
    def is_valid_schedule(left: Section, right: Section) -> bool:
        """Same instructor, plus:

        - both sides lack a physical meeting (ONLINE, TBA, or blank): no
          time or room to check, so same-instructor alone is sufficient;
        - otherwise, either back-to-back on at least one shared weekday in
          the same building/room (gap of 15 minutes or less), or starting
          within 30 minutes of each other on disjoint weekdays in any room --
          the latter covers the common MWF+TR/MW lecture pattern, which
          routinely uses two different rooms.
        """
        if left.instructor != right.instructor:
            return False
        if left.is_online and right.is_online:
            return True
        if left.start is None or right.start is None:
            return False
        left_start = left.start.hour * 60 + left.start.minute
        right_start = right.start.hour * 60 + right.start.minute
        left_end = left_start + (left.duration or 0)
        right_end = right_start + (right.duration or 0)
        shared_days = bool(set(left.days or "") & set(right.days or ""))
        back_to_back = shared_days and (
            0 <= right_start - left_end <= 15
            or 0 <= left_start - right_end <= 15
        )
        if back_to_back:
            return (
                bool(left.room)
                and left.room == right.room
                and left.building == right.building
            )
        if shared_days:
            # Same weekday on both sides but not back-to-back: the two
            # meetings would overlap or nearly overlap on a shared day --
            # a real conflict, not a valid coreq pairing.
            return False
        return abs(left_start - right_start) <= 30

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
