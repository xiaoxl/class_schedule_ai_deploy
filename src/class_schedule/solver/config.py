"""Load and cross-validate catalog and term solver configuration."""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .. import record_utils
from ..config_schema import (
    CatalogsFileSchema,
    ConstraintsFileSchema,
    CoursesFileSchema,
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


_CONFIG_PATHS = {
    "catalogs.toml": Path("basicinfo/catalogs.toml"),
    "locations.toml": Path("basicinfo/locations.toml"),
    "timeslot.toml": Path("basicinfo/timeslot.toml"),
    "persons.toml": Path("basicinfo/persons.toml"),
    "courses.toml": Path("courses.toml"),
    "preferences.toml": Path("preferences.toml"),
    "constraints.toml": Path("constraints.toml"),
}
_CONFIG_FILES = tuple(_CONFIG_PATHS)
_PACKAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class ConfigPackage:
    id: str
    root: Path

    @property
    def display_name(self) -> str:
        return self.id


def list_config_packages(config_dir: str | Path) -> tuple[ConfigPackage, ...]:
    """Discover self-contained seven-file packages directly below config_dir."""
    root = Path(config_dir)
    if not root.is_dir():
        return ()
    packages = []
    for child in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_dir() or not _PACKAGE_ID.fullmatch(child.name):
            continue
        if all((child / relative).is_file() for relative in _CONFIG_PATHS.values()):
            packages.append(ConfigPackage(child.name, child))
    return tuple(packages)


def resolve_config_package(config_dir: str | Path, package: str) -> ConfigPackage:
    requested = package.strip()
    if not _PACKAGE_ID.fullmatch(requested):
        raise ValueError(f"Invalid configuration package name: {requested!r}")
    packages = {item.id: item for item in list_config_packages(config_dir)}
    if requested not in packages:
        raise FileNotFoundError(f"Unknown or incomplete configuration package: {requested}")
    return packages[requested]


def resolve_config_paths(
    config_dir: str | Path, package: str,
) -> dict[str, Path]:
    """Resolve the seven fixed paths inside one isolated package."""
    root = resolve_config_package(config_dir, package).root
    return {name: root / relative for name, relative in _CONFIG_PATHS.items()}


def load_catalogs(path: str | Path) -> CatalogsFileSchema:
    with open(path, "rb") as handle:
        return CatalogsFileSchema.model_validate(tomllib.load(handle))


def load_courses(path: str | Path) -> CoursesFileSchema:
    with open(path, "rb") as handle:
        return CoursesFileSchema.model_validate(tomllib.load(handle))


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
    package_id: str = ""
    package_root: str = ""
    catalogs: CatalogsFileSchema | None = None
    courses: CoursesFileSchema | None = None

    @classmethod
    def load(
        cls, config_dir: str | Path, package: str,
    ) -> "SolverConfig":
        package_info = resolve_config_package(config_dir, package)
        resolved = resolve_config_paths(config_dir, package)
        paths = tuple(resolved[name] for name in _CONFIG_FILES)
        catalogs = load_catalogs(resolved["catalogs.toml"])
        courses = load_courses(resolved["courses.toml"])
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
            constraint_rules=load_constraint_rules(resolved["constraints.toml"]),
            version=hashlib.sha256(
                b"\0".join(path.read_bytes() for path in paths)
            ).hexdigest()[:12],
            source_paths=tuple(str(path) for path in paths),
            package_id=package_info.id,
            package_root=str(package_info.root),
            catalogs=catalogs,
            courses=courses,
        )
        config.validate_references()
        return config

    def validate_references(self) -> None:
        assert self.catalogs is not None and self.courses is not None
        catalog_ids = {(item.subject, item.number) for item in self.catalogs.courses}
        offered_ids = {(item.subject, item.number) for item in self.courses.courses}
        missing_catalog = sorted(offered_ids - catalog_ids)
        if missing_catalog:
            raise ValueError(f"Offered courses are missing from catalogs.toml: {missing_catalog}")
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
