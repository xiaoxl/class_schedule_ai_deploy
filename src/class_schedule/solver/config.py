"""Load and cross-validate catalog and term solver configuration."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .. import record_utils
from ..config_schema import (
    ConstraintsFileSchema,
    LocationsFileSchema,
    PreferencesFileSchema,
    TimeslotFileSchema,
)
from ..schedule_model import (
    ConstraintRule,
    PersonRecord,
    PreferenceRecord,
    PreferenceRule,
    load_global_rules,
    load_persons,
    load_preferences,
    parse_rule_time,
)
from .types import MeetingPattern, RoomRecord


_REQUIRED_CONFIG_FILES = (
    "persons.toml", "preferences.toml", "timeslot.toml", "locations.toml",
)
_OPTIONAL_CONFIG_FILES = ("constraints.toml",)
_CONFIG_FILES = _REQUIRED_CONFIG_FILES + _OPTIONAL_CONFIG_FILES


def resolve_config_paths(
    config_dir: str | Path, term: str | None = None
) -> dict[str, Path]:
    """Resolve the recommended layered layout with flat-layout fallback."""
    root = Path(config_dir)
    candidates = {
        "persons.toml": (root / "catalog" / "persons.toml", root / "persons.toml"),
        "locations.toml": (root / "catalog" / "locations.toml", root / "locations.toml"),
        "preferences.toml": (
            *((root / "terms" / term / "preferences.toml",) if term else ()),
            root / "preferences.toml",
        ),
        "timeslot.toml": (
            *((root / "terms" / term / "timeslot.toml",) if term else ()),
            root / "timeslot.toml",
        ),
        "constraints.toml": (
            *((root / "terms" / term / "constraints.toml",) if term else ()),
            root / "constraints.toml",
        ),
    }
    resolved: dict[str, Path] = {}
    for name in _CONFIG_FILES:
        path = next((path for path in candidates[name] if path.is_file()), None)
        if path is not None:
            resolved[name] = path
    missing = [
        str(candidates[name][0]) for name in _REQUIRED_CONFIG_FILES
        if name not in resolved
    ]
    if missing:
        raise FileNotFoundError("Missing configuration file(s): " + ", ".join(missing))
    return resolved


def load_meeting_patterns(path: str | Path) -> list[MeetingPattern]:
    with open(path, "rb") as handle:
        raw = TimeslotFileSchema.model_validate(tomllib.load(handle))
    return [
        MeetingPattern(
            days=days,
            duration_minutes=entry.duration_minutes,
            starts=tuple(record_utils.clock(start) for start in entry.starts),
            roles=frozenset(entry.roles),
            courses=frozenset(course.strip().upper() for course in entry.courses),
            atomic_courses=frozenset(
                course.strip().upper() for course in entry.atomic_courses
            ),
        )
        for entry in raw.calendar.meeting_patterns
        for days in entry.days
    ]


def load_rooms(path: str | Path) -> list[RoomRecord]:
    with open(path, "rb") as handle:
        raw = LocationsFileSchema.model_validate(tomllib.load(handle))
    rooms = []
    for entry in raw.rooms:
        if not entry.available:
            continue
        room = (
            entry.name[len(entry.location):].strip()
            if entry.location and entry.name.startswith(entry.location)
            else entry.name
        )
        rooms.append(RoomRecord(building=entry.location, room=room))
    return rooms


def load_constraint_rules(path: str | Path) -> tuple[ConstraintRule, ...]:
    with open(path, "rb") as handle:
        raw = ConstraintsFileSchema.model_validate(tomllib.load(handle))
    return tuple(
        ConstraintRule(
            direction=entry.direction,
            name=entry.name,
            course=entry.course,
            section=entry.section,
            section_prefix=entry.section_prefix,
            room=(
                None if entry.room is None
                else (entry.room,) if isinstance(entry.room, str)
                else tuple(entry.room)
            ),
            time=(
                parse_rule_time(entry.time)
                if entry.time is not None else None
            ),
        )
        for entry in raw.rules
    )


def load_staff_count_weight(path: str | Path) -> float:
    with open(path, "rb") as handle:
        raw = PreferencesFileSchema.model_validate(tomllib.load(handle))
    return raw.staff_count_weight


def load_staff_credit_weight(path: str | Path) -> float:
    with open(path, "rb") as handle:
        raw = PreferencesFileSchema.model_validate(tomllib.load(handle))
    return raw.staff_credit_weight


@dataclass(frozen=True)
class SolverConfig:
    persons: dict[str, PersonRecord]
    preferences: dict[str, PreferenceRecord]
    meeting_patterns: list[MeetingPattern]
    rooms: list[RoomRecord]
    global_rules: tuple[PreferenceRule, ...] = ()
    staff_count_weight: float = 10.0
    staff_credit_weight: float = 5.0
    constraint_rules: tuple[ConstraintRule, ...] = ()
    version: str = ""
    source_paths: tuple[str, ...] = ()

    @classmethod
    def load(cls, config_dir: str | Path, term: str | None = None) -> "SolverConfig":
        resolved = resolve_config_paths(config_dir, term)
        paths = tuple(resolved[name] for name in _CONFIG_FILES if name in resolved)
        constraint_rules = (
            load_constraint_rules(resolved["constraints.toml"])
            if "constraints.toml" in resolved else ()
        )
        config = cls(
            persons=load_persons(resolved["persons.toml"]),
            preferences=load_preferences(resolved["preferences.toml"]),
            meeting_patterns=load_meeting_patterns(resolved["timeslot.toml"]),
            rooms=load_rooms(resolved["locations.toml"]),
            global_rules=load_global_rules(resolved["preferences.toml"]),
            staff_count_weight=load_staff_count_weight(
                resolved["preferences.toml"]
            ),
            staff_credit_weight=load_staff_credit_weight(
                resolved["preferences.toml"]
            ),
            constraint_rules=constraint_rules,
            version=hashlib.sha256(
                b"\0".join(path.read_bytes() for path in paths)
            ).hexdigest()[:12],
            source_paths=tuple(str(path) for path in paths),
        )
        config.validate_references()
        return config

    def validate_references(self) -> None:
        unknown = sorted(set(self.preferences) - set(self.persons))
        if unknown:
            raise ValueError(f"Preferences reference unknown instructors: {unknown}")
        room_names = {room.room for room in self.rooms}
        buildings = {room.building for room in self.rooms}
        full_names = {f"{room.building} {room.room}".strip() for room in self.rooms}
        known_locations = room_names | buildings | full_names
        referenced = {
            location
            for preference in self.preferences.values()
            for rule in preference.rules
            for location in rule.rooms
        } | {
            location for rule in self.global_rules for location in rule.rooms
        }
        invalid = sorted(referenced - known_locations)
        if invalid:
            raise ValueError(f"Preferences reference unknown rooms: {invalid}")
        constraint_locations = {
            location
            for rule in self.constraint_rules
            for location in rule.rooms
        }
        invalid_constraints = sorted(constraint_locations - known_locations)
        if invalid_constraints:
            raise ValueError(
                f"Constraint rules reference unknown rooms: "
                f"{invalid_constraints}"
            )
        for rule in self.constraint_rules:
            if rule.name is None:
                continue
            person = self.persons.get(rule.name)
            selector = (
                f"{rule.course}-{rule.section}"
                if rule.course and rule.section
                else rule.course or rule.section_prefix or "all sections"
            )
            if person is None:
                raise ValueError(
                    f"Constraint instructor for {selector} is unknown: {rule.name}"
                )
            if rule.course is not None and rule.course not in person.courses:
                raise ValueError(
                    f"Constraint instructor {rule.name} is not qualified for {selector}"
                )
        for index, left in enumerate(self.constraint_rules):
            for right in self.constraint_rules[index + 1:]:
                selectors_overlap = not (
                    left.course is not None
                    and right.course is not None
                    and left.course != right.course
                ) and not (
                    left.section is not None
                    and right.section is not None
                    and left.section != right.section
                )
                if (
                    selectors_overlap
                    and left.direction == "+"
                    and right.direction == "+"
                    and left.name is not None
                    and right.name is not None
                    and left.name != right.name
                ):
                    raise ValueError(
                        f"Conflicting instructor constraints for "
                        f"{left.course or 'matching sections'}: {left.name} and "
                        f"{right.name}"
                    )

    def constraints_for(
        self, course: str, section: str,
    ) -> tuple[ConstraintRule, ...]:
        return tuple(
            rule for rule in self.constraint_rules
            if rule.applies_to(course, section)
        )
