"""Normalize an imported template before transactional installation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

import pandas as pd

from . import record_utils
from .class_model import Section
from .schedule_model import GroupingError, PersonRecord, Schedule, resolve_person_name

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
    """Return fixed-schema rows plus explicit row/grouping failures."""
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    ignored = 0
    for offset, source in enumerate(
        dataframe.dropna(how="all").to_dict(orient="records"), start=2,
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
            raw_slot = _first(row, "Time Slot") or record_utils.format_slot(
                record_utils.value(row, "Days"), record_utils.value(row, "Start"),
            )
            mode, status = _mode_and_status(raw_slot, section)
            normalized = section.to_record()
            normalized.update({
                "Delivery Mode": mode, "Scheduling Status": status,
                "CRN": _first(row, "CRN"),
                "Seats Available": _first(
                    row, "Seats Available", "Seats_Avail", "Seats Avail",
                ),
                "Source Row": offset,
            })
            accepted.append({
                name: _plain(normalized.get(name, "")) for name in NORMALIZED_COLUMNS
            })
        except (TypeError, ValueError) as error:
            failure = {str(key).strip(): _plain(value) for key, value in source.items()}
            failure.update({"Source Row": offset, "Error": str(error)})
            rejected.append(failure)

    warnings: list[str] = []
    if accepted:
        try:
            Schedule.from_records(accepted, persons=persons)
        except GroupingError as error:
            warnings.append(f"Atomic grouping failed: {error}")
    return CleanResult(
        normalized=pd.DataFrame(accepted, columns=NORMALIZED_COLUMNS),
        rejected=pd.DataFrame(rejected), warnings=tuple(warnings),
        source_rows=len(accepted) + len(rejected),
        ignored_concurrent_rows=ignored,
    )
