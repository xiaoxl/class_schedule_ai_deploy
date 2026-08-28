"""Infer a complete editable configuration package from one schedule template."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .class_model import CrossListingClass, FourCreditClass, HybridClass
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

    Same-section rows are classified by the domain model as hybrid or
    four-credit. Cross-listings require a nonblank matching ``Cross-List``
    marker. Corequisites are deliberately not inferred.
    """
    records = read_table(template).dropna(how="all").to_dict(orient="records")
    if not records:
        raise ValueError("Cannot infer configuration from an empty template")
    schedule = Schedule.from_records(
        records,
        infer_legacy_relationships=False,
        infer_marked_cross_lists=True,
    )
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
    relationships = _inferred_relationships(schedule)
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
        relationship_count=len(relationships),
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


def _inferred_relationships(
    schedule: Schedule,
) -> list[tuple[str, list[str], frozenset[str] | None]]:
    relationships = []
    for item in schedule.classes:
        kind = (
            "hybrid" if isinstance(item, HybridClass)
            else "four_credit" if isinstance(item, FourCreditClass)
            else "cross_listing" if isinstance(item, CrossListingClass)
            else None
        )
        if kind is None:
            continue
        members = list(dict.fromkeys(
            f"{section.subject} {section.number} {section.section.upper()}"
            for section in item.sections
        ))
        # A cross-listing's synced_fields is otherwise re-derived from
        # whatever the current rows happen to show every time the schedule
        # is reloaded (see docs/codes.md) -- baking in what the template
        # actually had at inference time turns that one-shot heuristic into
        # a persisted, human-editable decision instead.
        synced_fields = item.synced_fields if isinstance(item, CrossListingClass) else None
        relationships.append((kind, members, synced_fields))
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
    for index, (kind, members, synced_fields) in enumerate(
        _inferred_relationships(schedule), 1,
    ):
        slug = re.sub(r"[^a-z0-9]+", "-", "-".join(members).lower()).strip("-")
        block = (
            "\n[[relationships]]\n"
            f"id = {_quote(f'inferred-{kind}-{slug}-{index}')}\n"
            f"kind = {_quote(kind)}\n"
            f"members = {_array(members)}\n"
        )
        # synced_fields is opt-in, not opt-out (see docs/codes.md): omitting
        # it now defaults to fully locked, so a template where the pair
        # already matches on all three fields needs nothing written at all
        # -- only a template that shows some field diverging needs the
        # explicit, narrower list, to keep that divergence from being
        # silently re-locked by the default.
        if (
            synced_fields is not None
            and synced_fields != CrossListingClass.ALL_SYNCED_FIELDS
        ):
            block += f"synced_fields = {_array(sorted(synced_fields))}\n"
        blocks.append(block)
    return "".join(blocks)
