"""Reconcile an imported template to the package's declared offerings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping

from . import record_utils
from .instructor_identity import is_new_instructor
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


def _pattern(config: SolverConfig, course: str, role: str, atomic: frozenset[str]):
    return next(
        pattern for pattern in config.meeting_patterns
        if role in pattern.roles
        and (not pattern.courses or course in pattern.courses)
        and (not pattern.atomic_courses or pattern.atomic_courses == atomic)
    )


def _record(config: SolverConfig, identity: str, role: str, atomic: frozenset[str], index: int = 0) -> dict[str, object]:
    subject, number, section = identity.split(maxsplit=2)
    catalog = next(
        item for item in config.catalogs.courses
        if item.subject == subject and item.number == number
    )
    if section.startswith("TC") and role not in {"hybrid_physical", "four_credit_primary", "four_credit_partial"}:
        time_slot, duration, building, room = "ONLINE", None, "", ""
    else:
        pattern = _pattern(config, f"{subject} {number}", role, atomic)
        location = config.rooms[0] if config.rooms else None
        time_slot, duration = _slot(pattern, index), pattern.duration_minutes
        building = location.building if location else ""
        room = location.room if location else ""
    return {
        "Subject": subject, "Number": number, "Section": section,
        "Type": "Lecture", "Title": catalog.title, "Credits": catalog.credits,
        "Time Slot": time_slot, "Duration": duration,
        "Building": building, "Room": room, "Instructor": "new_instructor",
    }


def _synthesize_relationship(config: SolverConfig, relationship) -> list[dict[str, object]]:
    atomic = frozenset(" ".join(member.split()[:2]) for member in relationship.members)
    if relationship.kind == "hybrid":
        return [_record(config, relationship.members[0], "hybrid_physical", atomic)]
    if relationship.kind == "four_credit":
        member = relationship.members[0]
        return [
            _record(config, member, "four_credit_primary", atomic),
            _record(config, member, "four_credit_partial", atomic),
        ]
    if relationship.kind == "cross_listing":
        return [
            _record(config, member, "cross_listing", atomic)
            for member in relationship.members
        ]
    credits = {
        f"{item.subject} {item.number}": item.credits
        for item in config.catalogs.courses
    }
    member_courses = [" ".join(member.split()[:2]) for member in relationship.members]
    values = [credits[course] for course in member_courses]
    roles = [
        "coreq_supplement" if min(values) < max(values) and value == min(values)
        else "coreq" for value in values
    ]
    rows = [
        _record(config, member, role, atomic, index)
        for index, (member, role) in enumerate(zip(relationship.members, roles))
    ]
    # Equal-credit same-day coreqs need adjacent starts in the same room.
    if roles == ["coreq", "coreq"] and rows[0]["Time Slot"] != "ONLINE":
        pattern = _pattern(config, member_courses[1], "coreq", atomic)
        if len(pattern.starts) > 1:
            rows[1]["Time Slot"] = _slot(pattern, 1)
    return rows


def reconcile_records(
    records: list[Mapping[str, object]], config: SolverConfig,
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
    for raw in records:
        row = record_utils.normalize_columns(raw)
        identity = _identity(row)
        if identity not in desired:
            if identity.strip():
                removed.add(identity)
            continue
        instructor = record_utils.text(record_utils.value(row, "Instructor"))
        if instructor and instructor not in config.persons and not is_new_instructor(instructor):
            row["Instructor"] = "new_instructor"
            reassigned.add(identity)
        kept.append(row)
        present.add(identity)

    missing = desired - present
    relationship_by_member = {
        member: relationship
        for relationship in config.courses.relationships
        for member in relationship.members
    }
    generated_relationships: set[str] = set()
    added: set[str] = set()
    for identity in sorted(missing):
        relationship = relationship_by_member.get(identity)
        if relationship is not None:
            if relationship.id in generated_relationships:
                continue
            absent_members = set(relationship.members) - present
            if absent_members != set(relationship.members):
                raise ValueError(
                    f"Imported template contains only part of relationship {relationship.id}"
                )
            kept.extend(_synthesize_relationship(config, relationship))
            added.update(relationship.members)
            generated_relationships.add(relationship.id)
        else:
            course = " ".join(identity.split()[:2])
            kept.append(_record(config, identity, "normal", frozenset({course})))
            added.add(identity)

    schedule = Schedule.from_records(
        kept, persons=config.persons,
        relationships=tuple(config.courses.relationships),
        catalogs=tuple(config.catalogs.courses),
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
        ("reassigned_to_new_instructor", report.reassigned),
    ):
        rendered = ", ".join(f'"{value}"' for value in values)
        lines.append(f"{action} = [{rendered}]")
    return "\n".join(lines) + "\n"
