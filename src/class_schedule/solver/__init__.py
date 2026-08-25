"""Public scheduling API backed by focused configuration and model modules."""

from .candidates import (
    INSTRUCTOR_CHANGE_COST,
    MAX_CANDIDATES_PAIRED_SECTION,
    MAX_CANDIDATES_SINGLE_SECTION,
    ROOM_CHANGE_COST,
    TIME_CHANGE_COST,
)
from .config import (
    SolverConfig,
    load_meeting_patterns,
    load_rooms,
)
from .constraints import HARD_LOAD_CAP_TOLERANCE
from .engine import DEFAULT_SEARCH_WORKERS, solve, solve_detailed
from .result import diff_schedules
from .types import (
    InfeasibleSchedule,
    MeetingPattern,
    NoFeasibleSchedule,
    RoomRecord,
    SectionCandidate,
    SectionChange,
    SolveResult,
    SolveStatus,
    SolveTimeout,
)

__all__ = [
    "HARD_LOAD_CAP_TOLERANCE",
    "DEFAULT_SEARCH_WORKERS",
    "INSTRUCTOR_CHANGE_COST",
    "InfeasibleSchedule",
    "MAX_CANDIDATES_PAIRED_SECTION",
    "MAX_CANDIDATES_SINGLE_SECTION",
    "MeetingPattern",
    "NoFeasibleSchedule",
    "ROOM_CHANGE_COST",
    "RoomRecord",
    "SectionCandidate",
    "SectionChange",
    "SolveResult",
    "SolveStatus",
    "SolveTimeout",
    "SolverConfig",
    "TIME_CHANGE_COST",
    "diff_schedules",
    "load_meeting_patterns",
    "load_rooms",
    "solve",
    "solve_detailed",
]
