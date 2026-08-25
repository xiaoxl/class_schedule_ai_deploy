"""Parse and apply reproducible manual schedule edits and solver locks."""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from .class_model import HybridClass
from .schedule_model import Schedule


LOCK_FIELDS = frozenset({"instructor", "time", "room", "building"})
LockMap = dict[tuple[str, int | None], frozenset[str]]


@dataclass(frozen=True)
class OverrideEdit:
    course_id: str
    record: int | None = None
    instructor: str | None = None
    time_slot: str | None = None
    room: str | None = None
    building: str | None = None


@dataclass(frozen=True)
class OverrideFile:
    edits: tuple[OverrideEdit, ...] = ()
    locks: LockMap | None = None
    term: str | None = None
    source_version: str | None = None


def _check_keys(table: Mapping[str, object], allowed: set[str], label: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ValueError(f"Unknown {label} key(s): {unknown}")


def _record_number(item: Mapping[str, object], label: str) -> int | None:
    value = item.get("record")
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
        raise ValueError(f"{label}.record must be a non-negative integer")
    return value


def load_overrides(path: str | Path) -> OverrideFile:
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)
    _check_keys(
        raw,
        {"term", "source_version", "edits", "locks", "unassign"},
        "top-level override",
    )
    term = raw.get("term")
    if term is not None and (not isinstance(term, str) or not term.strip()):
        raise ValueError("term must be a non-empty string")
    source_version = raw.get("source_version")
    if source_version is not None and (
        not isinstance(source_version, str)
        or re.fullmatch(r"ver\d+", source_version) is None
    ):
        raise ValueError("source_version must have the form 'verN'")
    edits: list[OverrideEdit] = []
    for index, item in enumerate(raw.get("edits", []), start=1):
        _check_keys(
            item,
            {"course_id", "record", "instructor", "time_slot", "room", "building"},
            f"edits[{index}]",
        )
        if not item.get("course_id"):
            raise ValueError(f"edits[{index}] requires course_id")
        fields = {name: item.get(name) for name in ("instructor", "time_slot", "room", "building")}
        if all(value is None for value in fields.values()):
            raise ValueError(f"edits[{index}] does not change any field")
        if any(value is not None and not isinstance(value, str) for value in fields.values()):
            raise ValueError(f"edits[{index}] field values must be strings")
        edits.append(OverrideEdit(
            course_id=str(item["course_id"]), record=_record_number(item, f"edits[{index}]"), **fields
        ))
    for index, item in enumerate(raw.get("unassign", []), start=1):
        _check_keys(item, {"course_id", "record", "placeholder"}, f"unassign[{index}]")
        if not item.get("course_id"):
            raise ValueError(f"unassign[{index}] requires course_id")
        edits.append(OverrideEdit(
            course_id=str(item["course_id"]),
            record=_record_number(item, f"unassign[{index}]"),
            instructor=str(item.get("placeholder", "new_instructor")),
        ))
    locks: dict[tuple[str, int | None], frozenset[str]] = {}
    for index, item in enumerate(raw.get("locks", []), start=1):
        _check_keys(item, {"course_id", "record", "fields"}, f"locks[{index}]")
        course_id = str(item.get("course_id", ""))
        raw_fields = item.get("fields", [])
        if not isinstance(raw_fields, list) or any(not isinstance(value, str) for value in raw_fields):
            raise ValueError(f"locks[{index}].fields must be an array of strings")
        fields = frozenset(raw_fields)
        if not course_id or not fields:
            raise ValueError(f"locks[{index}] requires course_id and fields")
        invalid = sorted(fields - LOCK_FIELDS)
        if invalid:
            raise ValueError(f"locks[{index}] has invalid fields: {invalid}")
        key = (course_id, _record_number(item, f"locks[{index}]"))
        locks[key] = locks.get(key, frozenset()) | fields
    return OverrideFile(
        edits=tuple(edits),
        locks=locks,
        term=term.strip() if isinstance(term, str) else None,
        source_version=source_version,
    )


def validate_override_context(
    overrides: OverrideFile,
    *,
    term: str,
    source_version: str | None,
) -> None:
    """Reject a revision file applied to a different term or source version."""
    if overrides.term is not None and overrides.term != term:
        raise ValueError(
            f"Override term {overrides.term!r} does not match requested term {term!r}"
        )
    if overrides.source_version is not None and overrides.source_version != source_version:
        actual = source_version or "an unversioned input"
        raise ValueError(
            f"Override source_version {overrides.source_version!r} does not match {actual!r}"
        )


def render_override_template(
    schedule: Schedule,
    *,
    term: str,
    source_version: str,
) -> str:
    """Render a no-op TOML revision file plus a record-index reference map."""
    quoted_term = json.dumps(term, ensure_ascii=True)
    quoted_version = json.dumps(source_version, ensure_ascii=True)
    lines = [
        f"# Final publication source: {term}/{source_version}",
        "# Reproducible manual revision. All examples below are commented out.",
        "# Apply with:",
        f"# class-schedule --config config final {term} {source_version}",
        "",
        f"term = {quoted_term}",
        f"source_version = {quoted_version}",
        "",
        "# Edit values first, then lock every field the solver must preserve.",
        "# [[edits]]",
        '# course_id = "MATH 1113-F01"',
        '# instructor = "Instructor, Example"',
        '# time_slot = "TR 9:30am"',
        '# building = "Corley"',
        '# room = "269"',
        "",
        "# [[locks]]",
        '# course_id = "MATH 1113-F01"',
        '# fields = ["instructor", "time", "building", "room"]',
        "",
        "# [[unassign]]",
        '# course_id = "STAT 2163-004"',
        '# placeholder = "new_instructor"',
        "",
        "# Atomic-class record map. record is zero-based and is only needed",
        "# when an edit or lock should target one row of a two-row class.",
    ]
    for item in schedule.classes:
        atomic_id = item.course_ids[0]
        for record, section in enumerate(item.sections):
            lines.append(
                f"# {atomic_id} | record={record} | {section.course_id} | "
                f"{section.instructor or '(blank)'} | {section.time_slot or '(blank)'} | "
                f"{section.building} {section.room}".rstrip()
            )
    lines.append("")
    return "\n".join(lines)


def apply_overrides(schedule: Schedule, overrides: OverrideFile) -> Schedule:
    """Apply edits to a copy; class validation runs after each atomic edit."""
    result = Schedule(list(schedule.classes))
    for edit in overrides.edits:
        index = result.index_of(edit.course_id)
        item = result.classes[index]
        if edit.record is not None and not 0 <= edit.record < len(item.sections):
            raise IndexError(f"CSV record index out of range for {edit.course_id}: {edit.record}")
        hybrid_physical = (
            item.sections.index(item.physical_section)
            if isinstance(item, HybridClass) else None
        )
        changed = []
        for record, section in enumerate(item.sections):
            if edit.record is not None and edit.record != record:
                changed.append(section)
                continue
            values: dict[str, object] = {}
            for source, target in (
                ("instructor", "instructor"), ("time_slot", "time_slot"),
                ("room", "room"), ("building", "building"),
            ):
                value = getattr(edit, source)
                if value is not None:
                    if (
                        hybrid_physical is not None
                        and edit.record is None
                        and source != "instructor"
                        and record != hybrid_physical
                    ):
                        continue
                    values[target] = value
            changed.append(replace(section, **values))
        result.classes[index] = replace(item, sections=tuple(changed))
    for course_id, _record in (overrides.locks or {}):
        result.index_of(course_id)
    return result


def locks_for_section(
    locks: LockMap | None,
    course_ids: tuple[str, ...],
    record: int,
) -> frozenset[str]:
    fields: set[str] = set()
    for course_id in course_ids:
        if locks:
            fields.update(locks.get((course_id, None), ()))
            fields.update(locks.get((course_id, record), ()))
    return frozenset(fields)
