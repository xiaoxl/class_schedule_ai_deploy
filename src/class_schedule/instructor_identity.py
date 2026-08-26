"""Canonical identities for both dynamic position pools."""

from __future__ import annotations

import re

NEW_INSTRUCTOR = "new_instructor"
NEW_PROFESSOR = "new_professor"
_DYNAMIC_NAME = re.compile(
    r"^(?:staff|new[_ ]instructor)(?:\s+(\d+))?$", re.IGNORECASE
)
_DYNAMIC_PROFESSOR_NAME = re.compile(
    r"^new[_ ]professor(?:\s+(\d+))?$", re.IGNORECASE
)


def canonical_instructor(value: str) -> str:
    """Map legacy Staff names and spelling variants to new_instructor N."""
    text = str(value or "").strip()
    match = _DYNAMIC_NAME.fullmatch(text)
    if match:
        suffix = match.group(1)
        return NEW_INSTRUCTOR if suffix is None else f"{NEW_INSTRUCTOR} {int(suffix)}"
    match = _DYNAMIC_PROFESSOR_NAME.fullmatch(text)
    if match:
        suffix = match.group(1)
        return NEW_PROFESSOR if suffix is None else f"{NEW_PROFESSOR} {int(suffix)}"
    return text


def is_new_instructor(value: str) -> bool:
    return canonical_instructor(value).split(" ", 1)[0] == NEW_INSTRUCTOR


def new_instructor_rank(value: str) -> int:
    canonical = canonical_instructor(value)
    return 1 if canonical == NEW_INSTRUCTOR else int(canonical.rsplit(" ", 1)[1])


def new_instructor_name(rank: int) -> str:
    if rank < 1:
        raise ValueError("New Instructor rank must be positive")
    return NEW_INSTRUCTOR if rank == 1 else f"{NEW_INSTRUCTOR} {rank}"


def is_new_professor(value: str) -> bool:
    return canonical_instructor(value).split(" ", 1)[0] == NEW_PROFESSOR


def new_professor_rank(value: str) -> int:
    canonical = canonical_instructor(value)
    return 1 if canonical == NEW_PROFESSOR else int(canonical.rsplit(" ", 1)[1])


def new_professor_name(rank: int) -> str:
    if rank < 1:
        raise ValueError("New Professor rank must be positive")
    return NEW_PROFESSOR if rank == 1 else f"{NEW_PROFESSOR} {rank}"
