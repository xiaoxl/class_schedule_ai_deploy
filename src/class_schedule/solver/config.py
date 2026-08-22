"""Load and cross-validate catalog and term solver configuration."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .. import record_utils
from ..config_schema import LocationsFileSchema, TimeslotFileSchema
from ..schedule_model import (
    PersonRecord,
    PreferenceRecord,
    PreferenceRule,
    TimeWindow,
    load_global_rules,
    load_persons,
    load_preferences,
)
from .types import MeetingPattern, RoomRecord


_CONFIG_FILES = ("persons.toml", "preferences.toml", "timeslot.toml", "locations.toml")


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
    }
    resolved: dict[str, Path] = {}
    for name in _CONFIG_FILES:
        resolved[name] = next((path for path in candidates[name] if path.is_file()), candidates[name][0])
    missing = [str(path) for path in resolved.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing configuration file(s): " + ", ".join(missing))
    return resolved


def load_meeting_patterns(path: str | Path) -> list[MeetingPattern]:
    with open(path, "rb") as handle:
        raw = TimeslotFileSchema.model_validate(tomllib.load(handle))
    return [
        MeetingPattern(
            days=entry.days,
            duration_minutes=entry.duration_minutes,
            starts=tuple(record_utils.clock(start) for start in entry.starts),
            types=frozenset(entry.types),
        )
        for entry in raw.calendar.meeting_patterns
    ]


def load_blackouts(path: str | Path) -> list[TimeWindow]:
    with open(path, "rb") as handle:
        raw = TimeslotFileSchema.model_validate(tomllib.load(handle))
    return [
        TimeWindow.from_config(window.model_dump())
        for window in raw.calendar.blackouts
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


@dataclass(frozen=True)
class SolverConfig:
    persons: dict[str, PersonRecord]
    preferences: dict[str, PreferenceRecord]
    meeting_patterns: list[MeetingPattern]
    rooms: list[RoomRecord]
    blackouts: list[TimeWindow]
    global_rules: tuple[PreferenceRule, ...] = ()
    version: str = ""
    source_paths: tuple[str, ...] = ()

    @classmethod
    def load(cls, config_dir: str | Path, term: str | None = None) -> "SolverConfig":
        resolved = resolve_config_paths(config_dir, term)
        paths = tuple(resolved[name] for name in _CONFIG_FILES)
        config = cls(
            persons=load_persons(paths[0]),
            preferences=load_preferences(paths[1]),
            meeting_patterns=load_meeting_patterns(paths[2]),
            rooms=load_rooms(paths[3]),
            blackouts=load_blackouts(paths[2]),
            global_rules=load_global_rules(paths[1]),
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
            for location in (
                *preference.preferred_locations,
                *preference.disliked_locations,
                *(rule.room for rule in preference.rules if rule.room),
            )
        } | {rule.room for rule in self.global_rules if rule.room}
        invalid = sorted(referenced - known_locations)
        if invalid:
            raise ValueError(f"Preferences reference unknown rooms: {invalid}")
