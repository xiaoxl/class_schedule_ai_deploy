"""Reconcile an imported template to the package's declared offerings."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping

from . import record_utils
from .instructor_identity import is_new_instructor, is_new_professor
from .schedule_model import Schedule
if TYPE_CHECKING:
    from .solver.config import SolverConfig


@dataclass(frozen=True)
class ReconciliationReport:
    removed: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    reassigned: tuple[str, ...] = ()


def _identity(row: Mapping[str, object]) -> str:
    normalized = record_utils.normalize_columns(row)
    subject = record_utils.text(record_utils.value(normalized, "Subject")).upper()
    number = record_utils.text(record_utils.value(normalized, "Number")).upper()
    section = record_utils.text(record_utils.value(normalized, "Section")).upper()
    return f"{subject} {number} {section}"


def _slot(pattern, index: int = 0) -> str:
    start = pattern.starts[index % len(pattern.starts)]
    return f"{pattern.days} {start.strftime('%I:%M%p').lstrip('0').lower()}"


def _placeholder(config: SolverConfig, identities: tuple[str, ...] | list[str]) -> str:
    """Choose the lower-cost initial pool; the overlap defaults to instructor."""
    numbers = [int(identity.split()[1]) for identity in identities]
    if all(
        number < config.new_instructor_policy.max_course_number_exclusive
        for number in numbers
    ):
        return "new_instructor"
    if all(
        number >= config.new_professor_policy.min_course_number_inclusive
        for number in numbers
    ):
        return "new_professor"
    raise ValueError(f"No dynamic position is eligible for: {', '.join(identities)}")


def _pattern(config: SolverConfig, course: str, role: str, atomic: frozenset[str]):
    return next(
        pattern for pattern in config.meeting_patterns
        if role in pattern.roles
        and (not pattern.courses or course in pattern.courses)
        and (not pattern.atomic_courses or pattern.atomic_courses == atomic)
    )


def _record(config: SolverConfig, identity: str, role: str, atomic: frozenset[str], index: int = 0, placeholder: str | None = None) -> dict[str, object]:
    subject, number, section = identity.split(maxsplit=2)
    catalog = next(
        item for item in config.catalogs.courses
        if item.subject == subject and item.number == number
    )
    if section.startswith("TC") and role not in {"hybrid_physical", "four_credit_primary", "four_credit_partial"}:
        time_slot, duration, building, room = "ONLINE", None, "", ""
    else:
        pattern = _pattern(config, f"{subject} {number}", role, atomic)
        location = config.rooms[index % len(config.rooms)] if config.rooms else None
        time_slot, duration = _slot(pattern, index), pattern.duration_minutes
        building = location.building if location else ""
        room = location.room if location else ""
    return {
        "Subject": subject, "Number": number, "Section": section,
        "Type": "Lecture", "Title": catalog.title, "Credits": catalog.resolved_credits,
        "Time Slot": time_slot, "Duration": duration,
        "Building": building, "Room": room,
        "Instructor": placeholder or _placeholder(config, [identity]),
    }


def _synthesize_relationship(config: SolverConfig, relationship) -> list[dict[str, object]]:
    atomic = frozenset(" ".join(member.split()[:2]) for member in relationship.members)
    placeholder = _placeholder(config, relationship.members)
    if relationship.kind == "hybrid":
        return [_record(config, relationship.members[0], "hybrid_physical", atomic, placeholder=placeholder)]
    if relationship.kind == "four_credit":
        member = relationship.members[0]
        return [
            _record(config, member, "four_credit_primary", atomic, placeholder=placeholder),
            _record(config, member, "four_credit_partial", atomic, placeholder=placeholder),
        ]
    if relationship.kind == "cross_listing":
        return [
            _record(config, member, "cross_listing", atomic, placeholder=placeholder)
            for member in relationship.members
        ]
    credits = {
        f"{item.subject} {item.number}": item.resolved_credits
        for item in config.catalogs.courses
    }
    member_courses = [" ".join(member.split()[:2]) for member in relationship.members]
    values = [credits[course] for course in member_courses]
    roles = [
        "coreq_supplement" if min(values) < max(values) and value == min(values)
        else "coreq" for value in values
    ]
    rows = [
        _record(config, member, role, atomic, index, placeholder)
        for index, (member, role) in enumerate(zip(relationship.members, roles))
    ]
    if roles != ["coreq", "coreq"] and all(row["Time Slot"] != "ONLINE" for row in rows):
        right_days = str(rows[1]["Time Slot"]).split(maxsplit=1)[0]
        left_start = str(rows[0]["Time Slot"]).split(maxsplit=1)[1]
        rows[1]["Time Slot"] = f"{right_days} {left_start}"
    # Equal-credit same-day coreqs need adjacent starts in the same room.
    if roles == ["coreq", "coreq"] and rows[0]["Time Slot"] != "ONLINE":
        rows[1]["Building"] = rows[0]["Building"]
        rows[1]["Room"] = rows[0]["Room"]
        pattern = _pattern(config, member_courses[1], "coreq", atomic)
        if len(pattern.starts) > 1:
            rows[1]["Time Slot"] = _slot(pattern, 1)
        else:
            start = pattern.starts[0]
            minutes = start.hour * 60 + start.minute + pattern.duration_minutes + 10
            adjacent = datetime.time((minutes // 60) % 24, minutes % 60)
            rows[1]["Time Slot"] = (
                f"{pattern.days} {adjacent.strftime('%I:%M%p').lstrip('0').lower()}"
            )
    return rows


def reconcile_records(
    records: list[Mapping[str, object]], config: SolverConfig,
    *, infer_legacy_relationships: bool = False,
) -> tuple[Schedule, ReconciliationReport]:
    """Make the imported template exactly match courses.toml."""
    desired = {
        f"{item.subject} {item.number} {section}"
        for item in config.courses.courses for section in item.sections
    }
    kept: list[dict[str, object]] = []
    removed: set[str] = set()
    reassigned: set[str] = set()
    present: set[str] = set()
    relationship_by_member = {
        member: relationship
        for relationship in config.courses.relationships
        for member in relationship.members
    }
    for raw in records:
        row = record_utils.normalize_columns(raw)
        identity = _identity(row)
        if identity not in desired:
            if identity.strip():
                removed.add(identity)
            continue
        relationship = relationship_by_member.get(identity)
        section = identity.split(maxsplit=2)[2]
        if section.startswith("TC") and (
            relationship is None
            or relationship.kind not in {"hybrid", "four_credit"}
        ):
            # TC sections are web sections. Banner exports may describe them
            # as arranged/unscheduled; normalize them explicitly so neither
            # rebuilding nor solving can turn them into physical meetings.
            row.update({
                "Time Slot": "ONLINE", "Duration": None,
                "Days": "", "Start": "", "End": "",
                "Building": "", "Room": "",
            })
        instructor = record_utils.text(record_utils.value(row, "Instructor"))
        if (
            instructor and instructor not in config.persons
            and not is_new_instructor(instructor)
            and not is_new_professor(instructor)
        ):
            identities = relationship.members if relationship is not None else [identity]
            row["Instructor"] = _placeholder(config, identities)
            reassigned.add(identity)
        kept.append(row)
        present.add(identity)

    missing = desired - present
    generated_relationships: set[str] = set()
    added: set[str] = set()
    for identity in sorted(missing):
        relationship = relationship_by_member.get(identity)
        if relationship is not None:
            if relationship.key in generated_relationships:
                continue
            absent_members = set(relationship.members) - present
            if absent_members != set(relationship.members):
                raise ValueError(
                    "Imported template contains only part of relationship "
                    f"{relationship.display_name}"
                )
            kept.extend(_synthesize_relationship(config, relationship))
            added.update(relationship.members)
            generated_relationships.add(relationship.key)
        else:
            course = " ".join(identity.split()[:2])
            kept.append(_record(
                config, identity, "normal", frozenset({course}), len(added),
            ))
            added.add(identity)

    schedule = Schedule.from_records(
        kept, persons=config.persons,
        relationships=tuple(config.courses.relationships),
        catalogs=tuple(config.catalogs.courses),
        infer_legacy_relationships=infer_legacy_relationships,
    )
    return schedule, ReconciliationReport(
        removed=tuple(sorted(removed)), added=tuple(sorted(added)),
        reassigned=tuple(sorted(reassigned)),
    )


def render_reconciliation(report: ReconciliationReport) -> str:
    lines = [
        "# Generated reconciliation audit. Do not edit as configuration.",
        "",
    ]
    for action, values in (
        ("removed", report.removed), ("added", report.added),
        ("reassigned_to_dynamic_position", report.reassigned),
    ):
        rendered = ", ".join(f'"{value}"' for value in values)
        lines.append(f"{action} = [{rendered}]")
    return "\n".join(lines) + "\n"
