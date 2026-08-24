"""Strict schemas for the repository's TOML configuration boundary."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


COURSE_PATTERN = re.compile(r"^[A-Z]+\s+\d+[A-Z]?$")


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


class WeightedTimeWindowSchema(TimeWindowSchema):
    weight: float = Field(ge=0, le=100)


class WeightedLocationSchema(StrictModel):
    location: str
    weight: float = Field(ge=0, le=100)

    @field_validator("location")
    @classmethod
    def require_location(cls, location: str) -> str:
        if not location.strip():
            raise ValueError("weighted location must not be blank")
        return location


class WeightedCourseSchema(StrictModel):
    course: str
    weight: float = Field(ge=0, le=100)

    @field_validator("course")
    @classmethod
    def validate_course(cls, course: str) -> str:
        if not COURSE_PATTERN.fullmatch(course):
            raise ValueError(f"invalid course identifier: {course!r}")
        return course


class WeightedFlagSchema(StrictModel):
    weight: float = Field(ge=0, le=100)


class RuleSchema(StrictModel):
    course: str | None = None
    section: str | None = None
    section_prefix: str | None = None
    room: str | None = None
    time: TimeWindowSchema | None = None
    direction: Literal["prefer", "dislike"] = "dislike"
    weight: float = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def section_requires_course(self):
        if self.section is not None and self.course is None:
            raise ValueError("a rule's section requires course")
        if self.section is not None and self.section_prefix is not None:
            raise ValueError("a rule cannot set both section and section_prefix")
        if self.section_prefix is not None and not self.section_prefix.strip():
            raise ValueError("a rule's section_prefix must not be blank")
        if self.course is not None and not COURSE_PATTERN.fullmatch(self.course):
            raise ValueError(f"invalid course identifier: {self.course!r}")
        return self


class InstructorPreferenceSchema(StrictModel):
    name: str
    allow_overload: bool = True
    allow_back_to_back: bool = True
    max_back_to_back: int | None = Field(default=None, ge=0)
    prefers_online: WeightedFlagSchema | None = None
    preferred_times: list[WeightedTimeWindowSchema] = Field(default_factory=list)
    disliked_times: list[WeightedTimeWindowSchema] = Field(default_factory=list)
    preferred_locations: list[WeightedLocationSchema] = Field(default_factory=list)
    disliked_locations: list[WeightedLocationSchema] = Field(default_factory=list)
    preferred_courses: list[WeightedCourseSchema] = Field(default_factory=list)
    disliked_courses: list[WeightedCourseSchema] = Field(default_factory=list)
    rules: list[RuleSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_weighted_selectors(self):
        for field, attribute in (
            ("preferred_locations", "location"),
            ("disliked_locations", "location"),
            ("preferred_courses", "course"),
            ("disliked_courses", "course"),
        ):
            values = [getattr(item, attribute) for item in getattr(self, field)]
            if len(values) != len(set(values)):
                raise ValueError(f"{field} must not contain duplicate selectors")
        for rule in self.rules:
            selector_count = sum(
                value is not None
                for value in (rule.course, rule.section, rule.room, rule.time)
            )
            if rule.section_prefix is None and selector_count < 2:
                raise ValueError(
                    "single-selector instructor rules belong in a weighted "
                    "time, location, or course preference list"
                )
        return self


class PreferencesFileSchema(StrictModel):
    instructors: list[InstructorPreferenceSchema] = Field(default_factory=list)
    rules: list[RuleSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_names(self):
        names = [item.name for item in self.instructors]
        if len(names) != len(set(names)):
            raise ValueError("preference instructor names must be unique")
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
