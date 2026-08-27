"""Optional package templates and atomically rebuilt working views."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from .reconciliation import reconcile_records, render_reconciliation
from .instructor_identity import new_instructor_name, new_professor_name
from .pattern_rules import pattern_applies
from .schedule_model import Schedule
from .schedule_model import overlaps_in_time
from .schedule_io import read_table
from .solver import SolverConfig

TEMPLATE_SUFFIXES = {".csv", ".xlsx"}


def template_directory(package_root: Path) -> Path:
    return package_root / "template"


def find_template(package_root: Path) -> Path | None:
    folder = template_directory(package_root)
    if not folder.is_dir():
        return None
    files = sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in TEMPLATE_SUFFIXES
    )
    return files[0] if files else None


def require_unique_template(package_root: Path) -> Path:
    """Return the package's sole CSV/XLSX file, regardless of its filename."""
    files = sorted(
        path for path in package_root.rglob("*")
        if path.is_file() and path.suffix.lower() in TEMPLATE_SUFFIXES
    )
    if not files:
        raise FileNotFoundError(
            f"Configuration {package_root.name!r} contains no CSV/XLSX template"
        )
    if len(files) > 1:
        names = ", ".join(path.relative_to(package_root).as_posix() for path in files)
        raise ValueError(
            f"Configuration {package_root.name!r} contains multiple table files: {names}"
        )
    return files[0]


def template_summary(package_root: Path, work_root: Path) -> dict:
    template = find_template(package_root)
    manifest_path = work_root / package_root.name / "initial" / "manifest.json"
    manifest = None
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = None
    return {
        "present": template is not None,
        "filename": template.name if template else None,
        "size": template.stat().st_size if template else None,
        "uploaded_at": (
            datetime.fromtimestamp(template.stat().st_mtime, UTC).isoformat()
            if template else None
        ),
        "work_views_present": manifest is not None,
        "work_views": manifest,
    }


def install_template(package_root: Path, filename: str, content: bytes) -> Path:
    suffix = Path(filename).suffix.lower()
    if suffix not in TEMPLATE_SUFFIXES or Path(filename).name != filename:
        raise ValueError("Template must be one CSV or XLSX file")
    with tempfile.TemporaryDirectory() as folder:
        candidate = Path(folder) / filename
        candidate.write_bytes(content)
        read_table(candidate).dropna(how="all")
    destination = template_directory(package_root)
    staging = package_root / f".template-staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True)
    try:
        target = staging / filename
        target.write_bytes(content)
        old = None
        if destination.exists():
            old = package_root / f".template-backup-{uuid.uuid4().hex}"
            destination.replace(old)
        try:
            staging.replace(destination)
        except Exception:
            if old is not None and old.exists() and not destination.exists():
                old.replace(destination)
            raise
        finally:
            if old is not None and old.exists():
                shutil.rmtree(old)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination / filename


def rebuild_work_views(
    package_root: Path,
    *,
    config_root: Path,
    work_root: Path,
) -> dict:
    """Rebuild from the original template, or synthesize from courses config."""
    template = find_template(package_root)
    courses_path = package_root / "courses.toml"
    if template is None and not courses_path.is_file():
        return template_summary(package_root, work_root)

    source = "template_only"
    config = None
    if courses_path.is_file():
        try:
            config = SolverConfig.load(config_root, package=package_root.name)
        except (FileNotFoundError, ValueError):
            if template is None:
                return template_summary(package_root, work_root)

    if template is not None:
        records = read_table(template).dropna(how="all").to_dict(orient="records")
    else:
        records = []
        source = "generated_default"

    if config is not None:
        schedule, report = reconcile_records(
            records, config,
            # A config-only seed must use only the relationships explicitly
            # declared in its inferred courses.toml. In particular, do not
            # resurrect legacy corequisites that inference intentionally omits.
            infer_legacy_relationships=template is not None,
        )
        if template is None:
            schedule = _assign_default_instructors(schedule, config)
        audit = render_reconciliation(report)
        source = "template_and_courses" if template is not None else source
        config_version = config.version
        differences = {
            "available": True,
            "removed": list(report.removed),
            "added": list(report.added),
            "reassigned": list(report.reassigned),
        }
    else:
        schedule = Schedule.from_records(
            records, infer_legacy_relationships=False,
            infer_marked_cross_lists=True,
        )
        audit = (
            "# Generated reconciliation audit. Do not edit.\n\n"
            'source = "template_only"\n'
            'courses_configuration = "missing"\n'
            "removed = []\nadded = []\n"
        )
        config_version = None
        differences = {
            "available": False,
            "removed": [], "added": [], "reassigned": [],
        }

    destination = work_root / package_root.name / "initial"
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".initial-staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        initial = staging / "initial.csv"
        instructor = staging / "initial_instructor.xlsx"
        location = staging / "initial_room.xlsx"
        reconciliation = staging / "reconciliation.toml"
        schedule.to_dataframe().to_csv(initial, index=False)
        schedule.to_instructor_excel(instructor)
        schedule.to_room_excel(location)
        reconciliation.write_text(audit, encoding="utf-8")
        template_hash = hashlib.sha256(template.read_bytes()).hexdigest() if template else None
        generated_files = (initial, instructor, location, reconciliation)
        manifest = {
            "schema_version": 4,
            "role": "initial",
            "package_id": package_root.name,
            "source": source,
            "generated_at": datetime.now(UTC).isoformat(),
            "configuration_version": config_version,
            "configuration": ({
                "package_id": config.package_id,
                "version": config.version,
                "files": [
                    {
                        "path": str(path),
                        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    }
                    for path in config.source_paths
                ],
            } if config is not None else {
                "package_id": package_root.name,
                "version": None,
                "files": [],
            }),
            "template": {
                "filename": template.name if template else None,
                "sha256": template_hash,
            },
            "reconciliation": {
                "snapshot": reconciliation.name,
                "sha256": hashlib.sha256(reconciliation.read_bytes()).hexdigest(),
                "source": "courses.toml" if config is not None else "template_only",
            },
            "initial": {
                "path": initial.name,
                "sha256": hashlib.sha256(initial.read_bytes()).hexdigest(),
            },
            "differences": differences,
            "files": {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in generated_files
            },
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8",
        )
        backup = None
        if destination.exists():
            backup = destination.parent / f".initial-backup-{uuid.uuid4().hex}"
            destination.replace(backup)
        try:
            staging.replace(destination)
        except Exception:
            if backup is not None and backup.exists() and not destination.exists():
                backup.replace(destination)
            raise
        finally:
            if backup is not None and backup.exists():
                shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return template_summary(package_root, work_root)


def _assign_default_instructors(schedule: Schedule, config: SolverConfig) -> Schedule:
    """Build a deterministic, preference-free seed with no basic collisions."""
    result = Schedule([])
    names = list(config.persons)
    loads = {name: 0.0 for name in names}
    dynamic_loads: dict[str, float] = {}
    # The seed may temporarily use as many numbered placeholders as needed.
    # SolverConfig.allowed_counts is enforced by the authoritative solver.
    placeholder_limit = max(1, len(schedule.classes))

    for item in schedule.classes:
        courses = {f"{section.subject} {section.number}" for section in item.sections}
        qualified = [
            name for name in names
            if courses.issubset(set(config.persons[name].courses))
            and loads[name] + item.credit_hours <= config.persons[name].max_load
        ]
        candidates = qualified[:]
        numbers = [int(section.number) for section in item.sections]
        instructor_ok = all(
            number < config.new_instructor_policy.max_course_number_exclusive
            for number in numbers
        )
        professor_ok = all(
            number >= config.new_professor_policy.min_course_number_inclusive
            for number in numbers
        )
        pool = "new_instructor" if instructor_ok else "new_professor" if professor_ok else None
        limit = placeholder_limit
        target = (
            config.new_instructor_policy.contract_load
            if pool == "new_instructor" else config.new_professor_policy.contract_load
        ) if pool else 0
        for rank in range(1, limit + 1):
            candidate = (
                new_instructor_name(rank) if pool == "new_instructor"
                else new_professor_name(rank)
            )
            if dynamic_loads.get(candidate, 0.0) + item.credit_hours <= target:
                candidates.append(candidate)
        if not candidates:
            candidates = ["new_instructor" if instructor_ok else "new_professor"]

        placed = None
        for candidate in candidates:
            placed = _first_basic_placement(item, candidate, result, config)
            if placed is not None:
                if candidate in loads:
                    loads[candidate] += item.credit_hours
                else:
                    dynamic_loads[candidate] = (
                        dynamic_loads.get(candidate, 0.0) + item.credit_hours
                    )
                break
        if placed is None:
            # Keep a complete seed even when the basic greedy pass is exhausted;
            # the real solver remains authoritative for final feasibility.
            placed = _with_assignment(item, candidates[0], None, None)
        result.add(placed)
    return result


def _first_basic_placement(item, instructor: str, assigned: Schedule, config: SolverConfig):
    """First free configured time, then first free room, for one instructor."""
    physical = [section for section in item.sections if not section.is_online]
    if not physical:
        return _with_assignment(item, instructor, None, None)
    anchor = physical[0]
    patterns = [
        pattern for pattern in config.meeting_patterns
        if pattern_applies(item, anchor, pattern)
        and pattern.days == anchor.days
        and pattern.duration_minutes == anchor.duration
    ]
    slots = [
        (pattern.days, start, pattern.duration_minutes)
        for pattern in patterns for start in pattern.starts
    ] or [(anchor.days, anchor.start, anchor.duration)]
    for days, start, duration in slots:
        if start is None:
            continue
        time_spec = (days, start, duration)
        timed = _with_assignment(item, instructor, time_spec, None)
        if _instructor_busy(timed, assigned, instructor):
            continue
        for room in config.rooms or [None]:
            placed = _with_assignment(item, instructor, time_spec, room)
            if not _room_busy(placed, assigned):
                return placed
    return None


def _with_assignment(item, instructor: str, time_spec, room):
    """Shift an atomic class as a unit, preserving its internal time offsets."""
    physical = [section for section in item.sections if not section.is_online]
    anchor = physical[0] if physical else None
    delta = None
    if time_spec is not None and anchor is not None and anchor.start is not None:
        _, start, _ = time_spec
        delta = (
            start.hour * 60 + start.minute
            - anchor.start.hour * 60 - anchor.start.minute
        )
    sections = []
    for section in item.sections:
        changes = {"instructor": instructor}
        if not section.is_online and time_spec is not None:
            days, start, duration = time_spec
            if section is anchor:
                shifted = start
                shifted_days = days
                changes["duration"] = duration
            else:
                minutes = section.start.hour * 60 + section.start.minute + (delta or 0)
                shifted = start.replace(hour=(minutes // 60) % 24, minute=minutes % 60)
                shifted_days = section.days
            changes["time_slot"] = (
                f"{shifted_days} {shifted.strftime('%I:%M%p').lstrip('0').lower()}"
            )
        if not section.is_online and room is not None:
            changes.update(building=room.building, room=room.room)
        sections.append(replace(section, **changes))
    placed = copy.copy(item)
    placed.sections = tuple(sections)
    if hasattr(item, "schedule_issues"):
        placed.schedule_issues = ()
    return placed


def _instructor_busy(candidate, assigned: Schedule, instructor: str) -> bool:
    return any(
        left.instructor == instructor and right.instructor == instructor
        and overlaps_in_time(left, right)
        for left in candidate.sections if not left.is_online
        for prior in assigned.classes
        for right in prior.sections if not right.is_online
    )


def _room_busy(candidate, assigned: Schedule) -> bool:
    return any(
        left.room and left.room == right.room and left.building == right.building
        and overlaps_in_time(left, right)
        for left in candidate.sections if not left.is_online
        for prior in assigned.classes
        for right in prior.sections if not right.is_online
    )
