"""Shared, atomic publisher for solver and manually edited schedule versions."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .overrides import render_override_template
from .schedule_model import Schedule
from .solver import diff_schedules


@dataclass(frozen=True)
class PublishedPaths:
    output_dir: Path
    schedule_path: Path
    instructor_path: Path
    room_path: Path
    report_path: Path
    attempts_path: Path
    changes_path: Path
    baseline_path: Path
    manifest_path: Path
    overrides_path: Path
    applied_overrides_path: Path
    applied_changes_path: Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish_version(
    *,
    term: str,
    version: str,
    destination: Path,
    schedule: Schedule,
    baseline: Schedule,
    baseline_bytes: bytes,
    attempts_rows: list[dict[str, object]],
    report: str,
    manifest: dict[str, object],
    applied_overrides: bytes,
    applied_changes: bytes,
    final: bool = False,
    replace_destination: bool = False,
) -> PublishedPaths:
    """Write one complete verN/final bundle, then install it atomically."""
    if destination.exists() and not replace_destination:
        raise FileExistsError(f"Refusing to overwrite existing result: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{version}-staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        base = f"{term}_{version}"
        schedule_path = staging / f"{base}.csv"
        instructor_path = staging / f"{base}_instructor.xlsx"
        room_path = staging / f"{base}_room.xlsx"
        report_path = staging / "report.md"
        attempts_path = staging / "attempts.csv"
        changes_path = staging / "changes.csv"
        baseline_path = staging / "baseline.csv"
        manifest_path = staging / "manifest.json"
        overrides_path = staging / "overrides.toml"
        applied_overrides_path = staging / "applied_overrides.toml"
        applied_changes_path = staging / "applied_changes.toml"

        schedule.to_dataframe().to_csv(schedule_path, index=False)
        schedule.to_instructor_excel(instructor_path)
        schedule.to_room_excel(room_path)
        pd.DataFrame(attempts_rows).to_csv(attempts_path, index=False)
        baseline_path.write_bytes(baseline_bytes)
        changes = tuple(dict.fromkeys(diff_schedules(baseline, schedule)))
        pd.DataFrame(
            ({"Course ID": c.course_id, "Field": c.field,
              "Before": c.before, "After": c.after} for c in changes),
            columns=("Course ID", "Field", "Before", "After"),
        ).to_csv(changes_path, index=False)
        applied_overrides_path.write_bytes(applied_overrides)
        applied_changes_path.write_bytes(applied_changes)
        if final:
            overrides_path.write_bytes(applied_overrides)
        else:
            overrides_path.write_text(
                render_override_template(schedule, term=term, source_version=version),
                encoding="utf-8",
            )
        report_path.write_text(report, encoding="utf-8")

        immutable = [
            schedule_path, instructor_path, room_path, report_path,
            attempts_path, changes_path, baseline_path,
            applied_overrides_path, applied_changes_path,
        ]
        if final:
            immutable.append(overrides_path)
        manifest["files"] = {path.name: sha256(path) for path in immutable}
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

        backup = None
        if destination.exists():
            backup = destination.parent / f".{version}-backup-{uuid.uuid4().hex}"
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

    return PublishedPaths(
        output_dir=destination,
        schedule_path=destination / f"{term}_{version}.csv",
        instructor_path=destination / f"{term}_{version}_instructor.xlsx",
        room_path=destination / f"{term}_{version}_room.xlsx",
        report_path=destination / "report.md",
        attempts_path=destination / "attempts.csv",
        changes_path=destination / "changes.csv",
        baseline_path=destination / "baseline.csv",
        manifest_path=destination / "manifest.json",
        overrides_path=destination / "overrides.toml",
        applied_overrides_path=destination / "applied_overrides.toml",
        applied_changes_path=destination / "applied_changes.toml",
    )
