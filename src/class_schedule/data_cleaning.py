"""Normalize raw schedule exports into an auditable scheduling input."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd

from . import record_utils
from .class_model import Section
from .schedule_io import read_table
from .schedule_model import (
    GroupingError,
    PersonRecord,
    Schedule,
    resolve_person_name,
)


NORMALIZED_COLUMNS = (
    "Subject", "Number", "Section", "Type", "Title", "Credits",
    "Instructor", "Delivery Mode", "Scheduling Status", "Time Slot",
    "Duration", "Days", "Start", "End", "Building", "Room",
    "Cross-List", "CRN", "Seats Available", "Source Row",
)


@dataclass(frozen=True)
class CleanResult:
    normalized: pd.DataFrame
    rejected: pd.DataFrame
    warnings: tuple[str, ...]
    source_rows: int
    ignored_concurrent_rows: int


@dataclass(frozen=True)
class InitializeResult:
    """Cleaning result, canonical draft, and pre-change source views."""

    cleaning: CleanResult
    draft_path: Path | None
    instructor_path: Path | None
    room_path: Path | None


def _plain(value: object) -> object:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def _first(row: dict[str, object], *names: str) -> str:
    return record_utils.text(record_utils.value(row, *names))


def _mode_and_status(raw_slot: str, section: Section) -> tuple[str, str]:
    slot = raw_slot.strip().upper()
    if slot == "ONLINE":
        return "online", "scheduled"
    if slot == "TBA":
        return "arranged", "tba"
    if not slot:
        return "arranged", "unscheduled"
    return section.delivery_mode.value, "scheduled"


def clean_dataframe(
    dataframe: pd.DataFrame,
    *,
    persons: dict[str, PersonRecord] | None = None,
) -> CleanResult:
    """Return fixed-schema rows, rejected rows, and table-level warnings.

    Row numbers are one-based spreadsheet row numbers: the header is row 1,
    therefore the first data record is Source Row 2.
    """
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    ignored = 0

    for offset, source in enumerate(
        dataframe.dropna(how="all").to_dict(orient="records"), start=2
    ):
        row = record_utils.normalize_columns(source)
        try:
            subject = _first(row, "Subject").upper()
            instructor = _first(row, "Instructor")
            if persons and instructor:
                resolved = resolve_person_name(instructor, persons, subject=subject)
                if resolved is not None:
                    row["Instructor"] = resolved
            section = Section.from_record(row)
            if section.section.upper().startswith(("P", "ET", "A")):
                ignored += 1
            raw_slot = _first(row, "Time Slot")
            if not raw_slot:
                raw_slot = record_utils.format_slot(
                    record_utils.value(row, "Days"), record_utils.value(row, "Start")
                )
            mode, status = _mode_and_status(raw_slot, section)
            normalized = section.to_record()
            normalized.update({
                "Delivery Mode": mode,
                "Scheduling Status": status,
                "CRN": _first(row, "CRN"),
                "Seats Available": _first(
                    row, "Seats Available", "Seats_Avail", "Seats Avail"
                ),
                "Source Row": offset,
            })
            accepted.append({name: _plain(normalized.get(name, "")) for name in NORMALIZED_COLUMNS})
        except (TypeError, ValueError) as error:
            failure = {str(key).strip(): _plain(value) for key, value in source.items()}
            failure["Source Row"] = offset
            failure["Error"] = str(error)
            rejected.append(failure)

    warnings: list[str] = []
    if accepted:
        try:
            Schedule.from_records(accepted, persons=persons)
        except GroupingError as error:
            warnings.append(f"Atomic grouping failed: {error}")
    return CleanResult(
        normalized=pd.DataFrame(accepted, columns=NORMALIZED_COLUMNS),
        rejected=pd.DataFrame(rejected),
        warnings=tuple(warnings),
        source_rows=len(accepted) + len(rejected),
        ignored_concurrent_rows=ignored,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_file(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    persons: dict[str, PersonRecord] | None = None,
) -> CleanResult:
    """Clean one source file and atomically publish the cleaning bundle."""
    input_path, output_dir = Path(input_path), Path(output_dir)
    result = clean_dataframe(
        read_table(input_path), persons=persons,
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite cleaning result: {output_dir}")
    staging = output_dir.parent / f".{output_dir.name}-staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        result.normalized.to_csv(staging / "sections.csv", index=False)
        result.rejected.to_csv(staging / "rejected_rows.csv", index=False)
        report = [
            "# Data cleaning validation", "",
            f"- Source: `{input_path.as_posix()}`",
            f"- Source rows: {result.source_rows}",
            f"- Accepted rows: {len(result.normalized)}",
            f"- Rejected rows: {len(result.rejected)}",
            f"- Concurrent rows retained in CSV but ignored by scheduling: {result.ignored_concurrent_rows}",
            f"- Atomic grouping warnings: {len(result.warnings)}", "",
            "## Warnings", "",
        ]
        report.extend(f"- {item}" for item in result.warnings)
        if not result.warnings:
            report.append("- none")
        (staging / "validation.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "source": str(input_path),
            "source_sha256": _sha256(input_path),
            "source_rows": result.source_rows,
            "accepted_rows": len(result.normalized),
            "rejected_rows": len(result.rejected),
            "normalized_columns": list(NORMALIZED_COLUMNS),
        }
        (staging / "source_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        staging.replace(output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return result


def _pre_change_view_paths(input_path: Path) -> tuple[Path, Path]:
    return (
        input_path.with_name(f"{input_path.stem}_instructor.xlsx"),
        input_path.with_name(f"{input_path.stem}_room.xlsx"),
    )


def _publish_pre_change_views(
    schedule: Schedule, input_path: Path,
) -> tuple[Path, Path]:
    """Atomically replace both pre-change workbooks beside ``input_path``."""
    instructor_path, room_path = _pre_change_view_paths(input_path)
    token = uuid.uuid4().hex
    staged = {
        instructor_path: instructor_path.with_name(
            f".{instructor_path.stem}-staging-{token}.xlsx"
        ),
        room_path: room_path.with_name(
            f".{room_path.stem}-staging-{token}.xlsx"
        ),
    }
    backups: dict[Path, Path] = {}
    originally_present = {path for path in staged if path.exists()}
    try:
        schedule.to_instructor_excel(staged[instructor_path])
        schedule.to_room_excel(staged[room_path])
        for destination in staged:
            if destination.exists():
                backup = destination.with_name(
                    f".{destination.name}-backup-{token}"
                )
                destination.replace(backup)
                backups[destination] = backup
        for destination, temporary in staged.items():
            temporary.replace(destination)
    except Exception:
        for destination in staged:
            if destination in backups:
                destination.unlink(missing_ok=True)
                backups[destination].replace(destination)
            elif destination not in originally_present:
                destination.unlink(missing_ok=True)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        for backup in backups.values():
            backup.unlink(missing_ok=True)
    return instructor_path, room_path


def publish_draft(schedule: Schedule, output_path: str | Path) -> Path:
    """Publish the canonical, grouped, pre-change schedule as ``draft.csv``."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite draft: {output_path}")
    staging = output_path.with_name(
        f".{output_path.stem}-staging-{uuid.uuid4().hex}{output_path.suffix}"
    )
    try:
        schedule.to_dataframe().to_csv(staging, index=False)
        staging.replace(output_path)
    finally:
        staging.unlink(missing_ok=True)
    return output_path


def initialize_input(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    persons: dict[str, PersonRecord] | None = None,
    draft_path: str | Path | None = None,
) -> InitializeResult:
    """Clean a source export and publish its canonical draft and source views.

    The workbooks are built from the normalized, atomically grouped source
    schedule. No term changes, new-hire placement, overrides, preferences, or
    solver transformations are accepted by this API.
    """
    input_path = Path(input_path)
    draft_destination = Path(
        draft_path or Path(output_dir).parent / "draft" / "draft.csv"
    )
    if draft_destination.exists():
        raise FileExistsError(f"Refusing to overwrite draft: {draft_destination}")
    cleaning = clean_file(input_path, output_dir, persons=persons)
    if len(cleaning.rejected) or cleaning.warnings:
        return InitializeResult(cleaning, None, None, None)
    schedule = Schedule.from_dataframe(cleaning.normalized, persons=persons)
    published_draft = publish_draft(
        schedule, draft_destination
    )
    instructor_path, room_path = _publish_pre_change_views(schedule, input_path)
    return InitializeResult(
        cleaning, published_draft, instructor_path, room_path
    )
