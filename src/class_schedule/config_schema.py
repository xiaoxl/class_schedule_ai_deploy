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


# Every rule selector is one value or a list of values, handled the same
# way: an unset selector matches anything, otherwise the meeting's value
# must be one of the listed options (``section_prefix`` matches by prefix).
RULE_SELECTOR_FIELDS = (
    "name", "course", "subject", "number", "section",
    "section_prefix", "room", "building",
)


class RuleSelectorSchema(StrictModel):
    name: str | list[str] | None = None
    course: str | list[str] | None = None
    subject: str | list[str] | None = None
    number: str | list[str] | None = None
    section: str | list[str] | None = None
    section_prefix: str | list[str] | None = None
    room: str | list[str] | None = None
    building: str | list[str] | None = None
    time: TimeWindowSchema | str | None = None

    @field_validator(*RULE_SELECTOR_FIELDS, mode="after")
    @classmethod
    def _normalize_selector(cls, value, info):
        """One list-or-scalar cleanup for every selector field."""
        if value is None:
            return None
        field = info.field_name
        items = [value] if isinstance(value, str) else list(value)
        if not items:
            raise ValueError(f"{field} selector must not be empty")
        cleaned: list[str] = []
        for item in items:
            text = str(item).strip()
            if not text:
                raise ValueError(f"{field} selectors must be nonblank")
            if field == "subject":
                text = text.upper()
                if not text.isalpha():
                    raise ValueError("subject must contain letters only")
            elif field == "number":
                text = text.upper()
                if not re.fullmatch(r"\d+[A-Z]?", text):
                    raise ValueError(
                        "number must be digits with an optional trailing letter"
                    )
            elif field == "course" and not COURSE_PATTERN.fullmatch(text):
                raise ValueError(f"invalid course identifier: {text!r}")
            cleaned.append(text)
        if len(cleaned) != len(set(cleaned)):
            raise ValueError(f"{field} selectors must not contain duplicates")
        return cleaned[0] if isinstance(value, str) else cleaned

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

    @model_validator(mode="after")
    def validate_selectors(self):
        if self.course is not None and (
            self.subject is not None or self.number is not None
        ):
            raise ValueError("use course, or subject/number, but not both")
        if self.section is not None and self.section_prefix is not None:
            raise ValueError("a rule cannot set both section and section_prefix")
        if all(
            getattr(self, field) is None
            for field in (*RULE_SELECTOR_FIELDS, "time")
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
        if (
            self.name is None and self.room is None
            and self.building is None and self.time is None
        ):
            raise ValueError(
                "a constraint rule requires name, room, building, and/or time"
            )
        return self


class WorkloadPenaltiesSchema(StrictModel):
    # Flat cost for a load whose distance from contract lands in
    # ``WorkloadPolicySchema.light`` -- charged once, never reported as a
    # finding. Default 0 keeps the light tier free.
    light_penalty: float = Field(default=0, ge=0)
    # Heavy tier: cost is one of these per-credit rates times the whole
    # distance |load - max_load| (credit hours), reported as a finding.
    #   over  = load above contract, instructor allows overload (permissive)
    #   over_strict = load above contract, instructor does not
    #   under = load below contract
    heavy_unit_over: float = Field(default=10, ge=0)
    heavy_unit_over_strict: float = Field(default=100, ge=0)
    heavy_unit_under: float = Field(default=30, ge=0)


class WorkloadPolicySchema(StrictModel):
    # d = teaching_load - max_load, whole credit hours (may be negative).
    # Every integer d falls in exactly one tier:
    #   d in `ok`     -> no cost, no finding
    #   d in `light`  -> flat `light_penalty`, no finding
    #   otherwise     -> heavy: reported, and costs
    #                    heavy_unit_over[_strict] * |d|   when d > 0
    #                    heavy_unit_under          * |d|   when d < 0
    ok: list[int] = Field(default_factory=lambda: [0])
    light: list[int] = Field(default_factory=list)
    # A load above `max_load + hard_load_cap_tolerance` is hard-infeasible.
    hard_load_cap_tolerance: float = Field(default=6, ge=0)
    # Every workload penalty (light + heavy, over + under) for a New
    # Instructor / New Professor identity is multiplied by this. < 1 makes
    # the solver prefer to put unavoidable under/overload on a new hire
    # rather than a named instructor. 1.0 (default) treats them alike.
    # Does not touch the hard cap or the identity-count policy.
    new_hire_penalty_scale: float = Field(default=1.0, ge=0)
    penalties: WorkloadPenaltiesSchema = Field(default_factory=WorkloadPenaltiesSchema)

    @field_validator("ok", "light")
    @classmethod
    def _sorted_unique(cls, values: list[int]) -> list[int]:
        if values != sorted(set(values)):
            raise ValueError("must be sorted with no duplicates")
        return values

    @model_validator(mode="after")
    def validate_tiers(self):
        if 0 not in self.ok:
            raise ValueError(
                "workload.ok must contain 0 -- being exactly on contract is never penalised"
            )
        overlap = sorted(set(self.ok) & set(self.light))
        if overlap:
            raise ValueError(f"workload.ok and workload.light overlap: {overlap}")
        span = max((abs(k) for k in (*self.ok, *self.light)), default=0)
        if self.hard_load_cap_tolerance < span:
            raise ValueError(
                "hard_load_cap_tolerance must be at least the largest |d| listed in ok/light"
            )
        return self

    @property
    def over_free_credits(self) -> int:
        """Largest positive d that is still ok/light rather than a heavy
        overload. Used only to rank near-equal schedules, not to score."""
        return max((k for k in (*self.ok, *self.light) if k > 0), default=0)

    def tier(self, d: float) -> str:
        """"ok", "light", or "heavy" for a signed credit distance ``d``."""
        rounded = round(d)
        if abs(d - rounded) < 1e-9 and rounded in self.ok:
            return "ok"
        if abs(d - rounded) < 1e-9 and rounded in self.light:
            return "light"
        return "heavy"


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
        "lecture_lab_lecture",
        "lecture_lab_lab",
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
    kind: Literal["coreq", "cross_listing", "four_credit", "hybrid", "lecture_lab"]
    lab_time_editable: bool = False
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
        if any(not re.fullmatch(r"[A-Z]+\s+\d+[A-Z]?(?:\s+\S+)?", value) for value in normalized):
            raise ValueError("relationship members must use 'SUBJECT NUMBER' or 'SUBJECT NUMBER SECTION'")
        if len({len(value.split()) for value in normalized}) != 1:
            raise ValueError("relationship members must all use the same course or section level")
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
        if self.kind == "lecture_lab" and len(self.members) not in (1, 2):
            raise ValueError(
                "lecture_lab relationships require 1 member (shared course "
                "number) or 2 (lecture course then lab course)"
            )
        if self.lab_time_editable and self.kind != "lecture_lab":
            raise ValueError("lab_time_editable is only meaningful for lecture_lab relationships")
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
    def is_course_level(self) -> bool:
        return len(self.members[0].split()) == 2

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

    @property
    def active_relationships(self) -> tuple[CourseRelationshipSchema, ...]:
        """Expand defaults by matching section code; incomplete groups are inactive."""
        sections_by_course = {
            f"{item.subject} {item.number}": set(item.sections)
            for item in self.courses
        }
        offered = {
            f"{course} {section}"
            for course, sections in sections_by_course.items() for section in sections
        }
        explicit = [
            relation for relation in self.relationships
            if not relation.is_course_level and set(relation.members) <= offered
        ]
        reserved = {member for relation in explicit for member in relation.members}
        active = list(explicit)
        for relation in self.relationships:
            if not relation.is_course_level:
                continue
            matching = set.intersection(*(
                sections_by_course.get(course, set()) for course in relation.members
            ))
            for section in sorted(matching):
                members = [f"{course} {section}" for course in relation.members]
                # A specific active section declaration overrides a course default.
                if reserved.intersection(members):
                    continue
                active.append(relation.model_copy(update={"members": members}))
        return tuple(active)

    @model_validator(mode="after")
    def validate_references(self):
        course_keys = [(item.subject, item.number) for item in self.courses]
        if len(course_keys) != len(set(course_keys)):
            raise ValueError("offered course identities must be unique")
        keys = [item.key for item in self.relationships]
        if len(keys) != len(set(keys)):
            raise ValueError("relationship identities must be unique")
        used: set[str] = set()
        for relationship in self.relationships:
            repeated = sorted(set(relationship.members) & used)
            if repeated:
                raise ValueError(
                    f"sections may belong to only one relationship: {repeated}"
                )
            used.update(relationship.members)
        return self
