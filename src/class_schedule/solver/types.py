"""Shared immutable types and public solver exceptions."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import StrEnum

from ..schedule_model import Schedule


class NoFeasibleSchedule(RuntimeError):
    """No assignment exists, or none was found within the search budget."""


class InfeasibleSchedule(NoFeasibleSchedule):
    """The candidate model was proven infeasible."""


class SolveTimeout(NoFeasibleSchedule):
    """The search budget expired before a feasible assignment was found."""


class SolveStatus(StrEnum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"


@dataclass(frozen=True)
class SolveResult:
    schedule: Schedule
    status: SolveStatus
    objective: float
    best_bound: float
    solve_seconds: float
    candidate_count: int
    config_version: str
    random_seed: int = 0
    search_workers: int = 1


@dataclass(frozen=True)
class MeetingPattern:
    days: str
    duration_minutes: int
    starts: tuple[datetime.time, ...]
    roles: frozenset[str] = frozenset()
    courses: frozenset[str] = frozenset()
    atomic_courses: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RoomRecord:
    building: str
    room: str


@dataclass(frozen=True)
class SectionCandidate:
    instructor: str
    time_slot: str
    duration: int | None
    days: str | None
    start: datetime.time | None
    end: datetime.time | None
    room: str
    building: str
    cost: float


@dataclass(frozen=True)
class SectionChange:
    course_id: str
    field: str
    before: str
    after: str
