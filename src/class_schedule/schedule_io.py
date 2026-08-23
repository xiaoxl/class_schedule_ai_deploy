"""File-system boundary for schedule CSV/XLSX tables.

``read_table`` centralizes format and text-preserving reads for cleaning and
table-level audits. ``read_schedule`` immediately groups that table into a
``Schedule`` for business logic, which must not re-read rows or repeat atomic
grouping rules.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pandas as pd

from .schedule_model import PersonRecord, Schedule


def read_table(path: str | Path) -> pd.DataFrame:
    """Read a supported table without coercing identifiers to numbers."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str)
    if suffix == ".xlsx":
        return pd.read_excel(path, dtype=str)
    raise ValueError(f"Unsupported input type: {path.suffix or '<none>'}")


def read_schedule(
    path: str | Path,
    *,
    persons: Mapping[str, PersonRecord] | None = None,
) -> Schedule:
    """Read, normalize, and group a CSV/XLSX file into atomic classes."""
    return Schedule.from_dataframe(
        read_table(path).dropna(how="all"),
        persons=persons,
    )
