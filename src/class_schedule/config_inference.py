"""Infer a complete editable configuration package from one schedule template."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .class_model import CoreqClass, CrossListingClass, FourCreditClass, HybridClass, Section
from .config_schema import CourseRelationshipSchema, CoursesFileSchema
from .instructor_identity import is_new_instructor, is_new_professor
from .pattern_rules import section_pattern_role
from .schedule_io import read_table
from .schedule_model import Schedule, teaching_loads


@dataclass(frozen=True)
class InferredConfiguration:
    files: dict[str, bytes]
    course_count: int
    section_count: int
    relationship_count: int
    room_count: int
    time_pattern_count: int
    person_count: int


def infer_configuration_from_template(
    template: str | Path,
    *,
    package: str,
) -> InferredConfiguration:
    """Return seven TOML files inferred from a CSV/XLSX schedule template.

    Four-credit and Hybrid classes use intrinsic recognition. Corequisite
    and cross-listing relationships are inferred here exactly once and are
    then persisted as explicit configuration; ordinary schedule loading does
    not repeat these guesses.
    """
    records = read_table(template).dropna(how="all").to_dict(orient="records")
    if not records:
        raise ValueError("Cannot infer configuration from an empty template")
    base = Schedule.from_records(records)
    relationships = infer_relationships_from_template(base)
    schedule = Schedule.from_records(records, relationships=relationships)
    sections = [section for item in schedule.classes for section in item.sections]
    if not sections:
        raise ValueError("Template contains no schedulable course sections")

    header = f"# Configuration package: {package}\n# Inferred from template; review before use.\n"
    files = {
        "catalogs.toml": _catalogs_toml(sections, header),
        "locations.toml": _locations_toml(sections, header),
        "timeslot.toml": _timeslot_toml(schedule, header),
        "persons.toml": _persons_toml(schedule, header),
        "courses.toml": _courses_toml(schedule, header),
        "preferences.toml": _preferences_toml(sections, header),
        "constraints.toml": (
            header
            + "\n# No inferred hard rules. Schema defaults remain active.\n"
        ),
    }
    encoded = {name: text.encode("utf-8") for name, text in files.items()}
    for name, content in encoded.items():
        tomllib.loads(content.decode("utf-8"))

    courses = {(section.subject, section.number) for section in sections}
    offerings = {
        (section.subject, section.number, section.section.upper())
        for section in sections
    }
    inferred_relationships = _inferred_relationships(schedule)
    rooms = {
        (section.building, section.room)
        for section in sections if section.room
    }
    patterns = {
        (section.days, section.duration, section_pattern_role(item, section))
        for item in schedule.classes for section in item.sections
        if section.has_meeting_time and section.duration
    }
    people = {
        section.instructor for section in sections
        if _is_named_person(section.instructor)
    }
    return InferredConfiguration(
        files=encoded,
        course_count=len(courses),
        section_count=len(offerings),
        relationship_count=len(inferred_relationships),
        room_count=len(rooms),
        time_pattern_count=len(patterns),
        person_count=len(people),
    )


def _quote(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _array(values) -> str:
    return "[" + ", ".join(_quote(value) for value in values) + "]"


def _catalogs_toml(sections, header: str) -> str:
    by_course = {}
    for section in sections:
        key = (section.subject, section.number)
        current = by_course.setdefault(key, {
            "title": section.title or f"{section.subject} {section.number}",
            "credits": section.credit_hours,
        })
        if abs(float(current["credits"]) - float(section.credit_hours)) > 1e-9:
            raise ValueError(
                f"Template has conflicting credits for {section.subject} {section.number}"
            )
        if not current["title"] and section.title:
            current["title"] = section.title
    blocks = [header]
    for (subject, number), details in sorted(by_course.items()):
        credits = float(details["credits"])
        credit_text = str(int(credits)) if credits.is_integer() else str(credits)
        blocks.append(
            "\n[[courses]]\n"
            f"subject = {_quote(subject)}\n"
            f"number = {_quote(number)}\n"
            f"title = {_quote(details['title'])}\n"
            f"credits = {credit_text}\n"
        )
    return "".join(blocks)


def _locations_toml(sections, header: str) -> str:
    rooms = sorted({
        (section.building.strip(), section.room.strip())
        for section in sections if section.room.strip()
    })
    blocks = [header]
    for building, room in rooms:
        name = " ".join(value for value in (building, room) if value)
        blocks.append(
            "\n[[rooms]]\n"
            f"name = {_quote(name)}\n"
            f"location = {_quote(building)}\n"
            "available = true\n"
        )
    return "".join(blocks)


def _timeslot_toml(schedule: Schedule, header: str) -> str:
    """Infer time domains without losing each meeting's structural role."""
    grouped: dict[tuple[str, int, str], set[str]] = {}
    for item in schedule.classes:
        for section in item.sections:
            if not section.has_meeting_time or not section.duration:
                continue
            key = (
                section.days or "", section.duration,
                section_pattern_role(item, section),
            )
            grouped.setdefault(key, set()).add(section.start.strftime("%H:%M"))
    if not grouped:
        raise ValueError("Template contains no physical meeting times to infer")
    blocks = [header]
    for (days, duration, role), starts in sorted(grouped.items()):
        blocks.append(
            "\n[[calendar.meeting_patterns]]\n"
            f"days = {_array([days])}\n"
            f"duration_minutes = {duration}\n"
            f"starts = {_array(sorted(starts))}\n"
            f"roles = {_array([role])}\n"
        )
    return "".join(blocks)


def _is_named_person(name: str) -> bool:
    clean = name.strip()
    return bool(clean) and clean.lower() not in {"unassigned", "tba"} and not (
        is_new_instructor(clean) or is_new_professor(clean)
    )


def _person_courses(sections) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for section in sections:
        if _is_named_person(section.instructor):
            result.setdefault(section.instructor, set()).add(
                f"{section.subject} {section.number}"
            )
    return result


def _persons_toml(schedule: Schedule, header: str) -> str:
    sections = [section for item in schedule.classes for section in item.sections]
    loads = teaching_loads(schedule)
    blocks = [header]
    for name, courses in sorted(_person_courses(sections).items()):
        load = max(1.0, float(loads.get(name, 0.0)))
        load_text = str(int(load)) if load.is_integer() else str(load)
        blocks.append(
            "\n[[persons]]\n"
            f"name = {_quote(name)}\n"
            f"max_load = {load_text}\n"
            f"courses = {_array(sorted(courses))}\n"
        )
    return "".join(blocks)


def _preferences_toml(sections, header: str) -> str:
    blocks = [header, "\nstaff_count_weight = 10\nstaff_credit_weight = 5\n"]
    for name in sorted(_person_courses(sections)):
        blocks.append(
            "\n[[instructors]]\n"
            f"name = {_quote(name)}\n"
            "allow_overload = true\n"
            "allow_back_to_back = true\n"
        )
    return "".join(blocks)


def _member(section: Section) -> str:
    return f"{section.subject} {section.number} {section.section.upper()}"


def _same_assignment(sections: list[Section]) -> bool:
    first, *rest = sections
    if all(section.is_online for section in sections):
        return all(
            section.instructor == first.instructor
            and not section.has_meeting_time
            and not section.room
            and not section.building
            for section in sections
        )
    return all(
        not section.is_online
        and section.instructor == first.instructor
        and section.time_slot == first.time_slot
        and section.duration == first.duration
        and section.room == first.room
        and section.building == first.building
        for section in rest
    )


def _cross_unsynced(sections: list[Section]) -> list[str]:
    first, *rest = sections
    result = []
    if any(section.instructor != first.instructor for section in rest):
        result.append("instructor")
    if any(
        section.room != first.room or section.building != first.building
        for section in rest
    ):
        result.append("room")
    if any(
        section.time_slot != first.time_slot or section.duration != first.duration
        for section in rest
    ):
        result.append("time")
    return result


def infer_relationships_from_template(
    schedule: Schedule,
) -> tuple[CourseRelationshipSchema, ...]:
    """Infer explicit relationships from a template-only Schedule."""
    relationships: list[CourseRelationshipSchema] = []
    consumed: set[str] = set()

    # Intrinsic kinds were already recognized without configuration.
    for item in schedule.classes:
        kind = (
            "hybrid" if isinstance(item, HybridClass)
            else "four_credit" if isinstance(item, FourCreditClass)
            else None
        )
        if kind is None:
            continue
        members = list(dict.fromkeys(_member(section) for section in item.sections))
        relationships.append(CourseRelationshipSchema(kind=kind, members=members))
        consumed.update(members)

    sections = [
        section for item in schedule.classes for section in item.sections
        if _member(section) not in consumed
    ]

    # A nonblank source marker is strongest and may identify N members.
    marked: dict[str, list[Section]] = {}
    for section in sections:
        if section.cross_list:
            marked.setdefault(section.cross_list, []).append(section)
    for group in marked.values():
        members = list(dict.fromkeys(_member(section) for section in group))
        if len(members) < 2 or any(member in consumed for member in members):
            continue
        relationships.append(CourseRelationshipSchema(
            kind="cross_listing", members=members,
            unsynced=_cross_unsynced(group),
        ))
        consumed.update(members)

    # Honors and the known MATH 5173 / STAT 4173 pair require a truly
    # shared assignment; online rows qualify only when time/location are empty.
    for left_index, left in enumerate(sections):
        left_member = _member(left)
        if left_member in consumed:
            continue
        for right in sections[left_index + 1:]:
            right_member = _member(right)
            if right_member in consumed:
                continue
            recognized = (
                CrossListingClass.is_honors_pair(left, right)
                or CrossListingClass.is_known_pair(left, right)
            )
            if recognized and _same_assignment([left, right]):
                relationships.append(CourseRelationshipSchema(
                    kind="cross_listing",
                    members=[left_member, right_member],
                    unsynced=[],
                ))
                consumed.update((left_member, right_member))
                break

    # Coreq defaults are inference-only; runtime uses the emitted config.
    for left_index, left in enumerate(sections):
        left_member = _member(left)
        if left_member in consumed:
            continue
        for right in sections[left_index + 1:]:
            right_member = _member(right)
            if right_member in consumed:
                continue
            if CoreqClass.is_coreq_pair(left, right):
                relationships.append(CourseRelationshipSchema(
                    kind="coreq", members=[left_member, right_member],
                ))
                consumed.update((left_member, right_member))
                break
    return tuple(relationships)


def _inferred_relationships(schedule: Schedule) -> list[CourseRelationshipSchema]:
    relationships: list[CourseRelationshipSchema] = []
    for item in schedule.classes:
        kind = (
            "hybrid" if isinstance(item, HybridClass)
            else "four_credit" if isinstance(item, FourCreditClass)
            else "cross_listing" if isinstance(item, CrossListingClass)
            else "coreq" if isinstance(item, CoreqClass)
            else None
        )
        if kind is None:
            continue
        members = list(dict.fromkeys(_member(section) for section in item.sections))
        unsynced = (
            sorted(CrossListingClass.ALL_SYNCED_FIELDS - item.synced_fields)
            if isinstance(item, CrossListingClass) else None
        )
        relationships.append(CourseRelationshipSchema(
            kind=kind, members=members, unsynced=unsynced,
        ))
    return relationships


def _courses_toml(schedule: Schedule, header: str) -> str:
    sections = [section for item in schedule.classes for section in item.sections]
    offerings: dict[tuple[str, str], set[str]] = {}
    for section in sections:
        offerings.setdefault((section.subject, section.number), set()).add(
            section.section.upper()
        )
    blocks = [header]
    for (subject, number), values in sorted(offerings.items()):
        blocks.append(
            "\n[[courses]]\n"
            f"subject = {_quote(subject)}\n"
            f"number = {_quote(number)}\n"
            f"sections = {_array(sorted(values))}\n"
        )
    inferred = _inferred_relationships(schedule)
    for relationship in inferred:
        block = (
            "\n[[relationships]]\n"
            f"kind = {_quote(relationship.kind)}\n"
            f"members = {_array(relationship.members)}\n"
        )
        if relationship.kind == "cross_listing":
            block += f"unsynced = {_array(relationship.unsynced or [])}\n"
        blocks.append(block)
    text = "".join(blocks)
    parsed = CoursesFileSchema.model_validate(tomllib.loads(text))
    # Round-trip verification: the generated explicit relationships must
    # reconstruct exactly the same atomic kind/member partition.
    rebuilt = Schedule.from_records(
        [record for item in schedule.classes for record in item.to_records()],
        relationships=parsed.relationships,
    )
    expected = sorted((type(item).__name__, tuple(sorted(item.course_ids))) for item in schedule.classes)
    actual = sorted((type(item).__name__, tuple(sorted(item.course_ids))) for item in rebuilt.classes)
    if actual != expected:
        raise ValueError("Inferred courses.toml failed relationship round-trip verification")
    return text
