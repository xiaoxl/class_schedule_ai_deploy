"""Parse and apply reproducible manual schedule edits and solver locks."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

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
    _check_keys(raw, {"edits", "locks", "unassign"}, "top-level override")
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
            instructor=str(item.get("placeholder", "Staff")),
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
    return OverrideFile(tuple(edits), locks)


def apply_overrides(schedule: Schedule, overrides: OverrideFile) -> Schedule:
    """Apply edits to a copy; class validation runs after each atomic edit."""
    result = Schedule(list(schedule.classes))
    for edit in overrides.edits:
        index = result.index_of(edit.course_id)
        item = result.classes[index]
        if edit.record is not None and not 0 <= edit.record < len(item.sections):
            raise IndexError(f"CSV record index out of range for {edit.course_id}: {edit.record}")
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
