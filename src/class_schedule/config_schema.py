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


class WeightedFlagSchema(StrictModel):
    weight: float = Field(ge=0, le=100)


class FlatPreferenceRuleSchema(StrictModel):
    name: str | None = None
    preferred_course: str | None = None
    preferred_section: str | None = None
    preferred_section_prefix: str | None = None
    preferred_room: str | None = None
    preferred_time: TimeWindowSchema | str | None = None
    disliked_course: str | None = None
    disliked_section: str | None = None
    disliked_section_prefix: str | None = None
    disliked_room: str | None = None
    disliked_time: TimeWindowSchema | str | None = None
    weight: float = Field(ge=0, le=100)

    @field_validator("preferred_time", "disliked_time")
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

    @field_validator("preferred_course", "disliked_course")
    @classmethod
    def validate_course(cls, value: str | None) -> str | None:
        if value is not None and not COURSE_PATTERN.fullmatch(value):
            raise ValueError(f"invalid course identifier: {value!r}")
        return value

    @model_validator(mode="after")
    def exactly_one_direction(self):
        if self.name is not None and not self.name.strip():
            raise ValueError("a rule's name must not be blank")
        directions = []
        for prefix in ("preferred", "disliked"):
            values = self.selector_values(prefix)
            if values:
                directions.append(prefix)
            section = values.get("section")
            section_prefix = values.get("section_prefix")
            if section is not None and "course" not in values:
                raise ValueError(f"{prefix}_section requires {prefix}_course")
            if section is not None and section_prefix is not None:
                raise ValueError(
                    f"a rule cannot set both {prefix}_section and "
                    f"{prefix}_section_prefix"
                )
            if section_prefix is not None and not str(section_prefix).strip():
                raise ValueError(f"{prefix}_section_prefix must not be blank")
        if len(directions) != 1:
            raise ValueError(
                "a rule must contain preferred_* fields or disliked_* fields, "
                "but not both"
            )
        return self

    def selector_values(self, prefix: str) -> dict[str, object]:
        return {
            field: value
            for field in ("course", "section", "section_prefix", "room", "time")
            if (value := getattr(self, f"{prefix}_{field}")) is not None
        }


class InstructorPreferenceSchema(StrictModel):
    name: str
    allow_overload: bool = True
    allow_back_to_back: bool = True
    max_back_to_back: int | None = Field(default=None, ge=0)
    prefers_online: WeightedFlagSchema | None = None


class PreferencesFileSchema(StrictModel):
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


class RequiredInstructorSchema(StrictModel):
    course: str
    section: str | None = None
    instructor: str

    @field_validator("course")
    @classmethod
    def validate_course(cls, course: str) -> str:
        if not COURSE_PATTERN.fullmatch(course):
            raise ValueError(f"invalid course identifier: {course!r}")
        return course

    @field_validator("section", "instructor")
    @classmethod
    def require_nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("constraint values must not be blank")
        return value


class ConstraintsFileSchema(StrictModel):
    required_instructors: list[RequiredInstructorSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_assignments(self):
        selectors = [(item.course, item.section) for item in self.required_instructors]
        if len(selectors) != len(set(selectors)):
            raise ValueError("required instructor selectors must be unique")
        return self


class MeetingPatternSchema(StrictModel):
    days: str
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
    def validate_days(cls, days: str) -> str:
        if not days or any(day not in "MTWRF" for day in days):
            raise ValueError(f"invalid meeting days: {days!r}")
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


class BlackoutSchema(TimeWindowSchema):
    pass


class CalendarSchema(StrictModel):
    meeting_patterns: list[MeetingPatternSchema] = Field(default_factory=list)
    blackouts: list[BlackoutSchema] = Field(default_factory=list)


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
