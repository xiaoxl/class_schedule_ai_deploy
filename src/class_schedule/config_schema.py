"""Strict schemas for the repository's TOML configuration boundary."""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .class_model import infer_credit_hours

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
    staff_count_weight: float = Field(default=10, ge=0, le=100)
    staff_credit_weight: float = Field(default=5, ge=0, le=100)
    instructors: list[InstructorPreferenceSchema] = Field(default_factory=list)
    rules: list[FlatPreferenceRuleSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_names(self):
        names = [item.name for item in self.instructors]
        if len(names) != len(set(names)):
            raise ValueError("preference instructor names must be unique")
        unknown = sorted({rule.name for rule in self.rules if rule.name} - set(names))
        if unknown:
            raise ValueError(f"rules reference instructors without preferences: {unknown}")
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


class WorkloadPenaltiesSchema(StrictModel):
    underload_per_credit: float = Field(default=30, ge=0)
    permissive_overload_per_credit: float = Field(default=10, ge=0)
    strict_overload_per_credit: float = Field(default=100, ge=0)
    far_overload_extra: float = Field(default=50, ge=0)


class WorkloadPolicySchema(StrictModel):
    overload_tolerance: float = Field(default=2, ge=0)
    hard_load_cap_tolerance: float = Field(default=6, ge=0)
    far_overload_threshold: float = Field(default=4, ge=0)
    penalties: WorkloadPenaltiesSchema = Field(default_factory=WorkloadPenaltiesSchema)

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.far_overload_threshold < self.overload_tolerance:
            raise ValueError("far_overload_threshold must be at least overload_tolerance")
        if self.hard_load_cap_tolerance < self.far_overload_threshold:
            raise ValueError("hard_load_cap_tolerance must be at least far_overload_threshold")
        return self


class BackToBackPolicySchema(StrictModel):
    penalty: float = Field(default=10, ge=0)


class NewInstructorPolicySchema(StrictModel):
    contract_load: float = Field(default=15, gt=0)
    max_course_number_exclusive: int = Field(default=2300, gt=0)
    allow_back_to_back: bool = True
    allowed_counts: list[int] = Field(default_factory=lambda: [0, 1, 2], min_length=1)

    @field_validator("allowed_counts")
    @classmethod
    def validate_allowed_counts(cls, values: list[int]) -> list[int]:
        if any(value < 0 for value in values):
            raise ValueError("allowed_counts cannot contain negative values")
        if values != sorted(set(values)):
            raise ValueError("allowed_counts must be sorted with no duplicates")
        return values


class NewProfessorPolicySchema(StrictModel):
    contract_load: float = Field(default=12, gt=0)
    min_course_number_inclusive: int = Field(default=1914, gt=0)
    allow_back_to_back: bool = True
    allowed_counts: list[int] = Field(default_factory=lambda: [0, 1, 2], min_length=1)

    @field_validator("allowed_counts")
    @classmethod
    def validate_allowed_counts(cls, values: list[int]) -> list[int]:
        if any(value < 0 for value in values):
            raise ValueError("allowed_counts cannot contain negative values")
        if values != sorted(set(values)):
            raise ValueError("allowed_counts must be sorted with no duplicates")
        return values


class ConstraintsFileSchema(StrictModel):
    workload: WorkloadPolicySchema = Field(default_factory=WorkloadPolicySchema)
    back_to_back: BackToBackPolicySchema = Field(default_factory=BackToBackPolicySchema)
    new_instructor: NewInstructorPolicySchema = Field(default_factory=NewInstructorPolicySchema)
    new_professor: NewProfessorPolicySchema = Field(default_factory=NewProfessorPolicySchema)
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


class CatalogCourseSchema(StrictModel):
    subject: str
    number: str
    title: str
    credits: float | None = Field(default=None, ge=0)

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str) -> str:
        value = value.strip().upper()
        if not value or not value.isalpha():
            raise ValueError("subject must contain letters only")
        return value

    @field_validator("number")
    @classmethod
    def validate_number(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"\d+[A-Z]?", value):
            raise ValueError("number must be text such as '1113' or '1013L'")
        return value

    @field_validator("title")
    @classmethod
    def require_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @property
    def resolved_credits(self) -> float:
        """Configured credits, or the final numeric course-number digit.

        Shares ``class_model.infer_credit_hours`` -- the fallback used to
        live here too, separately (and, for a trailing-letter number like
        "1013L", differently -- see docs/codes.md), so a course without
        explicit ``credits`` could silently get a different answer
        depending on which code path resolved it.
        """
        if self.credits is not None:
            return self.credits
        return float(infer_credit_hours(self.number))


class CatalogsFileSchema(StrictModel):
    courses: list[CatalogCourseSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_courses(self):
        identities = [(item.subject, item.number) for item in self.courses]
        if len(identities) != len(set(identities)):
            raise ValueError("catalog course identities must be unique")
        return self


class OfferedCourseSchema(StrictModel):
    subject: str
    number: str
    sections: list[str]

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str) -> str:
        return CatalogCourseSchema.normalize_subject(value)

    @field_validator("number")
    @classmethod
    def validate_number(cls, value: str) -> str:
        return CatalogCourseSchema.validate_number(value)

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().upper() for value in values]
        if not normalized or any(not value for value in normalized):
            raise ValueError("sections must contain at least one nonblank section")
        if len(normalized) != len(set(normalized)):
            raise ValueError("sections must not contain duplicates")
        return normalized


class CourseRelationshipSchema(StrictModel):
    # Legacy input compatibility only. Relationship identity is derived from
    # kind + canonical members and never needs to be authored or persisted.
    id: str | None = Field(default=None, exclude=True)
    kind: Literal["coreq", "cross_listing", "four_credit", "hybrid"]
    members: list[str]
    synced_fields: list[Literal["instructor", "room", "time"]] | None = None
    unsynced: list[Literal["instructor", "room", "time"]] | None = None

    @field_validator("id")
    @classmethod
    def require_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("relationship id must not be blank")
        return value

    @field_validator("members")
    @classmethod
    def validate_members(cls, values: list[str]) -> list[str]:
        normalized = [" ".join(value.strip().upper().split()) for value in values]
        if not normalized:
            raise ValueError("relationship members must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("relationship members must be different")
        if any(not re.fullmatch(r"[A-Z]+\s+\d+[A-Z]?\s+\S+", value) for value in normalized):
            raise ValueError("relationship members must use 'SUBJECT NUMBER SECTION'")
        return normalized

    @field_validator("synced_fields")
    @classmethod
    def validate_synced_fields(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("synced_fields must not contain duplicates")
        return value

    @field_validator("unsynced")
    @classmethod
    def validate_unsynced(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("unsynced must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_member_count(self):
        if self.kind == "four_credit" and len(self.members) != 1:
            raise ValueError("four_credit relationships require 1 member")
        if self.kind == "hybrid" and len(self.members) != 1:
            raise ValueError("hybrid relationships require 1 member")
        if self.kind == "coreq" and len(self.members) != 2:
            raise ValueError("coreq relationships require 2 members")
        if self.kind == "cross_listing" and len(self.members) < 2:
            raise ValueError("cross_listing relationships require at least 2 members")
        if self.synced_fields is not None and self.kind != "cross_listing":
            raise ValueError("synced_fields is only meaningful for cross_listing relationships")
        if self.unsynced is not None and self.kind != "cross_listing":
            raise ValueError("unsynced is only meaningful for cross_listing relationships")
        if self.synced_fields is not None and self.unsynced is not None:
            raise ValueError("use unsynced; legacy synced_fields cannot be combined with it")
        return self

    @property
    def key(self) -> str:
        canonical = "\0".join((self.kind, *sorted(self.members)))
        return f"relationship-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:20]}"

    @property
    def display_name(self) -> str:
        return f"{self.kind}: {', '.join(sorted(self.members))}"

    @property
    def locked_fields(self) -> frozenset[str] | None:
        if self.kind != "cross_listing":
            return None
        all_fields = frozenset({"instructor", "room", "time"})
        if self.unsynced is not None:
            return all_fields - frozenset(self.unsynced)
        if self.synced_fields is not None:
            return frozenset(self.synced_fields)
        return all_fields


class CoursesFileSchema(StrictModel):
    courses: list[OfferedCourseSchema] = Field(default_factory=list)
    relationships: list[CourseRelationshipSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self):
        course_keys = [(item.subject, item.number) for item in self.courses]
        if len(course_keys) != len(set(course_keys)):
            raise ValueError("offered course identities must be unique")
        offered = {
            f"{item.subject} {item.number} {section}"
            for item in self.courses for section in item.sections
        }
        keys = [item.key for item in self.relationships]
        if len(keys) != len(set(keys)):
            raise ValueError("relationship identities must be unique")
        used: set[str] = set()
        for relationship in self.relationships:
            unknown = sorted(set(relationship.members) - offered)
            if unknown:
                raise ValueError(
                    f"relationship {relationship.display_name!r} references unknown sections: {unknown}"
                )
            repeated = sorted(set(relationship.members) & used)
            if repeated:
                raise ValueError(
                    f"sections may belong to only one relationship: {repeated}"
                )
            used.update(relationship.members)
        return self
