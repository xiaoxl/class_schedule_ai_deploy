"""Web app: upload a schedule file, see it grouped into atomic classes,
and optionally solve it.

Built on ``schedule_model.Schedule`` / ``class_model``, not the archived
``schedule``/``models`` stack (see ``.dep/class_schedule_old/``). Every upload is also
evaluated against ``config/persons.toml`` and ``config/preferences.toml``
-- see ``schedule_model.check_soft_preferences`` (everything, including
max_load) / ``check_conflicts`` (the only hard-violation source,
room/instructor double-booking). ``POST /api/solve`` runs the OR-Tools
solver (``solver.solve``) on top of that, using
``config/timeslot.toml``/``config/locations.toml`` for the legal
time/room search space. There is still no LLM scheduling agent; that
lived on top of the old stack and has no equivalent here.
"""

from __future__ import annotations

import base64
import io
import logging
import math
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pandas as pd
import psutil
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from . import solver as solver_module
from .schedule_model import (
    GroupingError,
    HardViolation,
    PersonRecord,
    PreferenceRecord,
    PreferenceRule,
    Schedule,
    SoftFinding,
    check_conflicts,
    check_soft_preferences,
)

PACKAGE_WEB = Path(__file__).with_name("web")
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
ALLOWED_SUFFIXES = {".csv", ".xlsx", ".xls"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
LOG_PATH = Path("output/logs/webapp.log")

# A soft finding's penalty at or above this is rendered orange in the UI
# (under_load, always weighted 90, a strict instructor's overload (flat
# 100), a permissive one past OVERLOAD_FAR_THRESHOLD (10+50=60), and a
# strongly weighted "dislike" PreferenceRule, land here); below it is
# yellow (back_to_back/disliked_*, weighted 5-10, a permissive
# instructor's ordinary overload (10), and a mildly weighted
# PreferenceRule). Every penalty in this system shares one 0-100 scale --
# see the comment above schedule_model.OVERLOAD_TOLERANCE.
SOFT_SEVERITY_THRESHOLD = 20.0

# The solver is a real optimization pass, not instant -- generous but
# bounded so a solve request can't hang the server indefinitely. This is
# CP-SAT's own search budget only (model-building happens first and
# isn't counted); a real ~85-section semester schedule takes ~60s total.
SOLVE_TIME_LIMIT_SECONDS = 60.0

logger = logging.getLogger("class_schedule.webapp")

# The solve endpoint is the one path that reproducibly drove production
# RSS into the multi-GB range before _add_scheduling_constraints moved to
# add_no_overlap (see solver/constraints.py) -- logging before/after RSS here, next
# to the request that actually caused that incident, is cheap (one OS
# call each way) and gives an ongoing record to compare against if it
# ever creeps back up, without needing a one-off benchmark script.
_PROCESS = psutil.Process()


def _rss_mb() -> float:
    return _PROCESS.memory_info().rss / (1024 * 1024)


# Configuration errors are deployment errors, not a reason to silently run
# without qualifications/preferences. Fail startup with a precise schema error.
SOLVER_CONFIG = solver_module.SolverConfig.load(CONFIG_DIR)
PERSONS: dict[str, PersonRecord] = SOLVER_CONFIG.persons
PREFERENCES: dict[str, PreferenceRecord] = SOLVER_CONFIG.preferences
GLOBAL_RULES: tuple[PreferenceRule, ...] = SOLVER_CONFIG.global_rules


def _configure_logging() -> None:
    """Log to both console and a rotating file under ``output/logs/``."""
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"
    )
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


_configure_logging()


def create_app() -> FastAPI:
    app = FastAPI(title="Class Schedule Viewer", version="0.3.0")

    @app.post("/api/schedule")
    async def parse_schedule(schedule_file: UploadFile = File(...)):
        filename, schedule = await _read_and_group(schedule_file)
        logger.info("Parsed %r into %d classes", filename, len(schedule))
        return {
            "count": len(schedule),
            "config_version": SOLVER_CONFIG.version,
            "classes": _serialize_schedule(schedule),
            "violations": _evaluate_schedule(schedule),
            "excel": {
                "raw": _excel_base64(schedule, "to_raw_excel"),
                "instructor": _excel_base64(schedule, "to_instructor_excel"),
                "room": _excel_base64(schedule, "to_room_excel"),
            },
        }

    @app.post("/api/solve")
    async def solve_schedule(
        schedule_file: UploadFile = File(...),
        regenerate: bool = Form(False),
    ):
        filename, schedule = await _read_and_group(schedule_file)
        rss_before = _rss_mb()
        try:
            solve_result = solver_module.solve_detailed(
                schedule, SOLVER_CONFIG, time_limit_seconds=SOLVE_TIME_LIMIT_SECONDS,
                # On a "regenerate" re-solve, `schedule` is already the
                # caller's own previous solve output (see app.js's
                # currentFile) -- forbidding it as `previous` guarantees a
                # genuinely different result instead of just a possibly
                # different one.
                previous=schedule if regenerate else None,
            )
            solved = solve_result.schedule
        except solver_module.SolveTimeout as error:
            logger.warning(
                "Solve timed out for %r: %s (RSS %.1f -> %.1f MB)",
                filename, error, rss_before, _rss_mb(),
            )
            raise HTTPException(504, str(error)) from error
        except solver_module.NoFeasibleSchedule as error:
            # 422, not 400: the request itself was well-formed -- there's
            # just no conflict-free assignment to offer for this input
            # (see solver.solve()'s docstring). app.js keys off this
            # status to keep "Solve Schedule" disabled until a new file
            # is chosen, instead of inviting a retry that can't succeed.
            logger.warning(
                "Could not solve %r: %s (RSS %.1f -> %.1f MB)",
                filename, error, rss_before, _rss_mb(),
            )
            raise HTTPException(422, str(error)) from error
        changes = solver_module.diff_schedules(schedule, solved)
        violations = _evaluate_schedule(solved)
        logger.info(
            "Solved %r cleanly (%d classes, %d field change(s), RSS %.1f -> %.1f MB)",
            filename, len(solved), len(changes), rss_before, _rss_mb(),
        )
        return {
            "count": len(solved),
            "config_version": SOLVER_CONFIG.version,
            "classes": _serialize_schedule(solved),
            "violations": violations,
            "changes": [_serialize_change(c) for c in changes],
            "solver": {
                "status": solve_result.status.value,
                "objective": solve_result.objective,
                "best_bound": solve_result.best_bound,
                "solve_seconds": solve_result.solve_seconds,
                "candidate_count": solve_result.candidate_count,
                "config_version": solve_result.config_version,
            },
            "excel": {
                "raw": _excel_base64(solved, "to_raw_excel"),
                "instructor": _excel_base64(solved, "to_instructor_excel"),
                "room": _excel_base64(solved, "to_room_excel"),
            },
        }

    app.mount("/", _NoCacheStaticFiles(directory=PACKAGE_WEB, html=True), name="web")
    return app


def _excel_base64(schedule: Schedule, method_name: str) -> str:
    """Build one of Schedule's Excel exports and return it as base64, so
    the frontend can offer it as a download without any server-side
    session state -- the whole app is otherwise stateless per request."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "export.xlsx"
        getattr(schedule, method_name)(path)
        return base64.b64encode(path.read_bytes()).decode("ascii")


async def _read_and_group(schedule_file: UploadFile) -> tuple[str, Schedule]:
    """Shared upload -> DataFrame -> Schedule pipeline for both
    ``/api/schedule`` and ``/api/solve`` -- same validation, same
    GroupingError handling either way."""
    filename = schedule_file.filename or "<unknown>"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        logger.warning("Rejected %r: unsupported file type", filename)
        raise HTTPException(400, "Upload a CSV, XLSX, or XLS schedule file")
    content = await schedule_file.read()
    if not content:
        logger.warning("Rejected %r: empty file", filename)
        raise HTTPException(400, "Uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        logger.warning(
            "Rejected %r: %d bytes exceeds the 50 MB limit",
            filename, len(content),
        )
        raise HTTPException(413, "Uploaded file exceeds 50 MB")

    try:
        dataframe = _read_dataframe(content, suffix)
    except Exception as error:
        logger.exception("Failed to read %r", filename)
        raise HTTPException(400, f"Could not read file: {error}") from error
    del content  # no longer needed once parsed; drop it before the solve path holds `schedule`

    try:
        schedule = Schedule.from_dataframe(dataframe, persons=PERSONS)
    except GroupingError as error:
        logger.warning(
            "Failed to group %r into classes: %s (%d record(s))",
            filename, error, len(error.records),
        )
        raise HTTPException(
            400,
            {
                "message": str(error),
                "records": [_serialize_record(r) for r in error.records],
            },
        ) from error
    except ValueError as error:
        logger.warning("Failed to group %r into classes: %s", filename, error)
        raise HTTPException(400, str(error)) from error
    del dataframe  # Schedule.from_dataframe() copies out into Class objects; doesn't need the DataFrame itself

    return filename, schedule


class _NoCacheStaticFiles(StaticFiles):
    """Static files with no browser caching.

    This UI is under active development -- a stale cached ``app.js`` has
    already caused confusion where a fix looked "not applied" simply
    because the browser kept serving the old script. Correctness here
    matters more than the bandwidth saved by caching a small local file.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store"
        return response


def _read_dataframe(content: bytes, suffix: str) -> pd.DataFrame:
    # dtype=str on both branches -- without it, pandas silently infers
    # numeric types for numeric-looking text columns (course "Number",
    # "Room", ...), stripping leading zeros ("0803" -> 803). This isn't
    # just theoretical: it's exactly what corrupted a solved schedule's
    # own raw Excel export when re-uploaded for another solve pass.
    buffer = io.BytesIO(content)
    dataframe = (
        pd.read_csv(buffer, dtype=str)
        if suffix == ".csv"
        else pd.read_excel(buffer, dtype=str)
    )
    return dataframe.dropna(how="all")


def _serialize_schedule(schedule: Schedule) -> list[dict]:
    return [
        {
            "kind": type(item).__name__,
            "course_ids": list(item.course_ids),
            "credit_hours": item.credit_hours,
            "sections": [_serialize_record(r) for r in item.to_records()],
        }
        for item in schedule
    ]


def _evaluate_schedule(schedule: Schedule) -> dict:
    """Run both checks and shape them for the frontend's violations
    summary: hard (red, room/instructor conflicts only -- see
    ``check_conflicts``), soft (orange/yellow by penalty threshold)."""
    hard = check_conflicts(schedule)
    soft_total, soft_findings = check_soft_preferences(
        schedule, PREFERENCES, PERSONS, GLOBAL_RULES
    )
    return {
        "hard": [_serialize_hard(v) for v in hard],
        "soft_total": soft_total,
        "soft": [_serialize_soft(f) for f in soft_findings],
    }


def _serialize_hard(violation: HardViolation) -> dict:
    return {
        "rule": violation.rule,
        "subject": violation.subject,
        "message": violation.message,
    }


def _serialize_soft(finding: SoftFinding) -> dict:
    return {
        "rule": finding.rule,
        "subject": finding.instructor,
        "message": finding.message,
        "penalty": finding.penalty,
        "severity": (
            "orange" if finding.penalty >= SOFT_SEVERITY_THRESHOLD else "yellow"
        ),
    }


def _serialize_change(change: solver_module.SectionChange) -> dict:
    return {
        "course_id": change.course_id,
        "field": change.field,
        "before": change.before,
        "after": change.after,
    }


def _serialize_record(record: dict) -> dict:
    result = {}
    for key, value in record.items():
        if value is None or (isinstance(value, float) and math.isnan(value)):
            # A blank CSV/Excel cell becomes a raw NaN float in a
            # GroupingError's un-normalized row dicts (Section
            # construction -- which would otherwise turn it into "" via
            # record_utils.text() -- never got the chance to run before
            # raising). FastAPI's JSONResponse uses allow_nan=False, so a
            # literal NaN reaching here crashes the *error response
            # itself* into an unhandled 500 -- exactly the kind of bug
            # that looks like "the server is broken" instead of "this row
            # has a blank cell".
            result[key] = None
        elif hasattr(value, "strftime"):
            result[key] = value.strftime("%H:%M")
        else:
            result[key] = value
    return result


app = create_app()
