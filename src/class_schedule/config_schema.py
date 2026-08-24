"""Strict schemas for the repository's TOML configuration boundary."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


COURSE_PATTERN = re.compile(r"^[A-Z]+\s+\d+[A-Z]?$")
TIME_RANGE_PATTERN = re.compile(
    r"^\s*(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*-\s*"
    r"(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*$"
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AliasSchema(StrictModel):
    short: str
    subject: str | None = None


class PersonSchema(StrictModel):
    name: str
    max_load: float = Field(gt=0)
    aliases: list[str | AliasSchema] = Field(default_factory=list)
    courses: list[str] = Field(default_factory=list)

    @field_validator("courses")
    @classmethod
    def validate_courses(cls, courses: list[str]) -> list[str]:
        invalid = [course for course in courses if not COURSE_PATTERN.fullmatch(course)]
        if invalid:
            raise ValueError(f"invalid course identifiers: {invalid}")
        if len(courses) != len(set(courses)):
            raise ValueError("courses must not contain duplicates")
        return courses


class PersonsFileSchema(StrictModel):
    persons: list[PersonSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_names(self):
        names = [person.name for person in self.persons]
        if len(names) != len(set(names)):
            raise ValueError("person names must be unique")
        aliases: list[tuple[str, str | None, str]] = []
        for person in self.persons:
            for raw in person.aliases:
                alias = AliasSchema(short=raw) if isinstance(raw, str) else raw
                if alias.short in names and alias.short != person.name:
                    raise ValueError(
                        f"alias {alias.short!r} conflicts with an exact person name"
                    )
                for short, subject, owner in aliases:
                    scopes_overlap = subject is None or alias.subject is None or subject == alias.subject
                    if short == alias.short and owner != person.name and scopes_overlap:
                        raise ValueError(
                            f"ambiguous alias {short!r} for {owner!r} and {person.name!r}"
                        )
                aliases.append((alias.short, alias.subject, person.name))
        return self


class TimeWindowSchema(StrictModel):
    days: list[str] = Field(default_factory=list)
    between: tuple[str, str]
    reason: str = ""

    @field_validator("days")
    @classmethod
    def validate_days(cls, days: list[str]) -> list[str]:
        invalid = [day for day in days if day not in "MTWRF" or len(day) != 1]
        if invalid:
            raise ValueError(f"invalid weekday codes: {invalid}")
        return days


class RuleSelectorSchema(StrictModel):
    name: str | None = None
    course: str | None = None
    section: str | None = None
    section_prefix: str | None = None
    room: str | list[str] | None = None
    time: TimeWindowSchema | str | None = None

    @field_validator("time")
    @classmethod
    def validate_time_shorthand(
        cls, value: TimeWindowSchema | str | None,
    ) -> TimeWindowSchema | str | None:
        if isinstance(value, str) and not TIME_RANGE_PATTERN.fullmatch(value):
            raise ValueError(
                "time shorthand must be a 24-hour range such as '8-12' or "
                "'09:00-13:00'"
            )
        return value

    @field_validator("course")
    @classmethod
    def validate_course(cls, value: str | None) -> str | None:
        if value is not None and not COURSE_PATTERN.fullmatch(value):
            raise ValueError(f"invalid course identifier: {value!r}")
        return value

    @field_validator("room")
    @classmethod
    def validate_rooms(
        cls, value: str | list[str] | None,
    ) -> str | list[str] | None:
        if value is None:
            return None
        rooms = [value] if isinstance(value, str) else value
        if not rooms or any(not room.strip() for room in rooms):
            raise ValueError("room selectors must contain nonblank room names")
        if len(rooms) != len(set(rooms)):
            raise ValueError("room selectors must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_selectors(self):
        if self.name is not None and not self.name.strip():
            raise ValueError("a rule's name must not be blank")
        if self.section is not None and self.course is None:
            raise ValueError("section requires course")
        if self.section is not None and self.section_prefix is not None:
            raise ValueError("a rule cannot set both section and section_prefix")
        if self.section_prefix is not None and not self.section_prefix.strip():
            raise ValueError("section_prefix must not be blank")
        if all(
            value is None
            for value in (
                self.course, self.section, self.section_prefix, self.room, self.time,
            )
        ):
            raise ValueError("a rule must contain at least one selector")
        return self


class FlatPreferenceRuleSchema(RuleSelectorSchema):
    weight: float = Field(ge=-100, le=100)

    @model_validator(mode="after")
    def require_nonzero_weight(self):
        if self.weight == 0:
            raise ValueError("a rule's weight must be positive or negative, not zero")
        return self


class InstructorPreferenceSchema(StrictModel):
    name: str
    allow_overload: bool = True
    allow_back_to_back: bool = True
    max_back_to_back: int | None = Field(default=None, ge=0)


class PreferencesFileSchema(StrictModel):
    staff_count_weight: float = Field(default=100, ge=0, le=100)
    instructors: list[InstructorPreferenceSchema] = Field(default_factory=list)
    rules: list[FlatPreferenceRuleSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_names(self):
        names = [item.name for item in self.instructors]
        if len(names) != len(set(names)):
            raise ValueError("preference instructor names must be unique")
        unknown = sorted({rule.name for rule in self.rules if rule.name} - set(names))
        if unknown:
            raise ValueError(f"rules reference instructors without profiles: {unknown}")
        return self


class ConstraintRuleSchema(RuleSelectorSchema):
    direction: Literal["+", "-"]

    @model_validator(mode="after")
    def require_hard_value(self):
        if self.name is None and self.room is None and self.time is None:
            raise ValueError(
                "a constraint rule requires name, room, and/or time"
            )
        return self


class ConstraintsFileSchema(StrictModel):
    rules: list[ConstraintRuleSchema] = Field(default_factory=list)


class MeetingPatternSchema(StrictModel):
    days: list[str]
    duration_minutes: int = Field(gt=0)
    starts: list[str]
    roles: list[Literal[
        "normal",
        "hybrid_physical",
        "cross_listing",
        "coreq",
        "coreq_supplement",
        "four_credit_primary",
        "four_credit_partial",
    ]]
    courses: list[str] = Field(default_factory=list)
    atomic_courses: list[str] = Field(default_factory=list)

    @field_validator("days")
    @classmethod
    def validate_days(cls, days: list[str]) -> list[str]:
        if not days:
            raise ValueError("meeting pattern requires at least one days option")
        invalid = [
            option for option in days
            if not option
            or any(day not in "MTWRF" for day in option)
            or len(option) != len(set(option))
        ]
        if invalid:
            raise ValueError(f"invalid meeting days options: {invalid!r}")
        if len(days) != len(set(days)):
            raise ValueError("meeting pattern days options must not contain duplicates")
        return days

    @field_validator("starts")
    @classmethod
    def require_starts(cls, starts: list[str]) -> list[str]:
        if not starts:
            raise ValueError("meeting pattern requires at least one start")
        return starts

    @field_validator("roles")
    @classmethod
    def require_roles(cls, roles: list[str]) -> list[str]:
        if not roles:
            raise ValueError("meeting pattern requires at least one role")
        if len(roles) != len(set(roles)):
            raise ValueError("meeting pattern roles must not contain duplicates")
        return roles

    @field_validator("courses", "atomic_courses")
    @classmethod
    def validate_course_selectors(cls, courses: list[str]) -> list[str]:
        invalid = [
            course for course in courses
            if not COURSE_PATTERN.fullmatch(course)
        ]
        if invalid:
            raise ValueError(f"invalid course identifiers: {invalid}")
        if len(courses) != len(set(courses)):
            raise ValueError("course selectors must not contain duplicates")
        return courses

    @model_validator(mode="after")
    def validate_selector_relationship(self):
        if self.courses and self.atomic_courses:
            outside = sorted(set(self.courses) - set(self.atomic_courses))
            if outside:
                raise ValueError(
                    "courses must be contained in atomic_courses when both "
                    f"selectors are set: {outside}"
                )
        return self


class CalendarSchema(StrictModel):
    meeting_patterns: list[MeetingPatternSchema] = Field(default_factory=list)


class TimeslotFileSchema(StrictModel):
    calendar: CalendarSchema = Field(default_factory=CalendarSchema)


class RoomSchema(StrictModel):
    name: str
    location: str
    available: bool = True

    @model_validator(mode="after")
    def name_contains_location(self):
        if self.location and not self.name.startswith(self.location):
            raise ValueError("room name must start with its location")
        return self


class LocationsFileSchema(StrictModel):
    rooms: list[RoomSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_names(self):
        names = [room.name for room in self.rooms]
        if len(names) != len(set(names)):
            raise ValueError("room names must be unique")
        return self
