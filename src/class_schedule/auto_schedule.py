"""Temporary, package-scoped history for non-repeating browser solves."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from . import solver
from .schedule_model import Schedule, evaluate_schedule, teaching_loads, workload_records

_lock = threading.Lock()


def run_auto_schedule(schedule, config, *, root: Path, seconds: float, compare_template=None) -> dict:
    if not _lock.acquire(blocking=False):
        raise RuntimeError("An Auto Schedule request is already running. Try again when it finishes.")
    try:
        inventory = sorted(
            section.course_id for item in schedule for section in item.sections
        )
        key = hashlib.sha256(json.dumps(
            [config.package_id, config.version, inventory], sort_keys=True,
        ).encode()).hexdigest()
        directory = root / key
        directory.mkdir(parents=True, exist_ok=True)
        history = []
        for path in sorted(directory.glob("*.json")):
            saved = json.loads(path.read_text(encoding="utf-8"))
            for name in ("input", "output"):
                if name in saved:
                    history.append(Schedule.from_records(
                        saved[name], persons=config.persons,
                        relationships=tuple(config.courses.relationships) if config.courses else (),
                        catalogs=tuple(config.catalogs.courses) if config.catalogs else (),
                    ))
        attempt_id = uuid.uuid4().hex
        path = directory / f"{attempt_id}.json"
        attempt = {
            "attempt_id": attempt_id, "package": config.package_id,
            "config_version": config.version,
            "started_at": datetime.now(UTC).isoformat(),
            "status": "running", "input": schedule.to_records(),
        }

        def save():
            pending = path.with_suffix(".pending")
            pending.write_text(json.dumps(attempt, indent=2, default=str), encoding="utf-8")
            pending.replace(path)

        save()  # Even a timeout or a stopped process leaves an input record.
        try:
            try:
                result = solver.solve_detailed(
                    schedule, config, time_limit_seconds=seconds,
                    excluded_schedules=tuple(history) + (schedule,),
                )
            except solver.InfeasibleSchedule:
                # A pruned candidate pool cannot prove that all alternatives are gone.
                attempt["exhaustive_candidates"] = True
                save()
                result = solver.solve_detailed(
                    schedule, config, time_limit_seconds=seconds,
                    excluded_schedules=tuple(history) + (schedule,),
                    exhaustive_candidates=True,
                )
            attempt.update(
                status="changed", output=result.schedule.to_records(),
                random_seed=result.random_seed, objective=result.objective,
            )
            if compare_template is not None:
                attempt["template_changes"] = compare_template(result.schedule)
            response = {"status": "changed", "result": result}
        except solver.InfeasibleSchedule:
            attempt["status"] = "exhausted"
            response = {"status": "exhausted", "result": None}
        except solver.SolveTimeout as error:
            attempt.update(status="timeout", message=str(error))
            response = {"status": "timeout", "result": None}
        except Exception as error:
            attempt.update(status="error", message=str(error))
            raise
        finally:
            attempt["finished_at"] = datetime.now(UTC).isoformat()
            save()
        return {
            **response, "attempt_id": attempt_id,
            "history_count": len(list(directory.glob('*.json'))),
            "template_changes": attempt.get("template_changes"),
        }
    finally:
        _lock.release()


def _rank_schedule(schedule, config, objective: float):
    """Order a solved schedule the way ``schedule_run`` orders publish
    attempts: fewest hard violations, then the smallest worst-instructor
    overload, then soft penalty, then the raw solver objective."""
    evaluation = evaluate_schedule(
        schedule, config.preferences, config.persons, config.global_rules,
        config.meeting_patterns, config.constraint_rules,
        config.workload_policy, config.back_to_back_policy,
        config.new_instructor_policy, config.new_professor_policy,
    )
    loads = teaching_loads(schedule)
    persons, _ = workload_records(
        loads, config.persons, config.preferences,
        config.new_instructor_policy, config.new_professor_policy,
    )
    tolerance = config.workload_policy.overload_tolerance
    worst_overload = max(
        (
            loads.get(name, 0.0) - person.max_load - tolerance
            for name, person in persons.items()
        ),
        default=0.0,
    )
    return (
        len(evaluation.hard_violations),
        max(0.0, worst_overload),
        evaluation.soft_penalty,
        objective,
    )


def run_best_schedule(
    schedule, config, *, root: Path, attempts: int, seconds: float,
    compare_template=None, progress_id: str | None = None,
) -> dict:
    """Independent multi-attempt optimize from the current schedule.

    Unlike :func:`run_auto_schedule`, this excludes nothing and is not
    hunting for a *different* schedule -- it runs several fresh-seeded
    CP-SAT solves so the search escapes the warm-start basin, then keeps
    whichever result ranks best under :func:`_rank_schedule`. Stops early
    on a proven-optimal, hard-violation-free attempt.

    ``progress_id`` (a client-supplied token) names the on-disk record so a
    poller can watch ``tries`` grow while this runs.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if not _lock.acquire(blocking=False):
        raise RuntimeError(
            "A solve is already running. Try again when it finishes."
        )
    try:
        inventory = sorted(
            section.course_id for item in schedule for section in item.sections
        )
        key = hashlib.sha256(json.dumps(
            [config.package_id, config.version, inventory, "best"], sort_keys=True,
        ).encode()).hexdigest()
        directory = root / key
        directory.mkdir(parents=True, exist_ok=True)
        attempt_id = uuid.uuid4().hex
        safe_progress = re.sub(r"[^A-Za-z0-9_-]", "", progress_id or "")[:64]
        path = directory / f"{safe_progress or attempt_id}.json"
        record = {
            "attempt_id": attempt_id, "progress_id": safe_progress or None,
            "package": config.package_id,
            "config_version": config.version, "mode": "best",
            "attempts_planned": attempts + 1,
            "started_at": datetime.now(UTC).isoformat(),
            "status": "running", "input": schedule.to_records(), "tries": [],
        }

        def save():
            pending = path.with_suffix(".pending")
            pending.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
            pending.replace(path)

        save()
        best_result = None
        best_rank = None
        errors: list[str] = []
        # One search worker per attempt on purpose: 8-way search proves the
        # raw-objective optimum every time (which piles load onto a few
        # instructors), so every seed converges to the same schedule and the
        # overload-first ranking below has nothing to choose between. A
        # single worker leaves each seeded attempt in a different feasible
        # basin, and we keep the least-overloaded of them.
        for number in range(1, attempts + 1):
            try:
                result = solver.solve_detailed(
                    schedule, config, time_limit_seconds=seconds,
                    search_workers=1,
                )
            except (solver.InfeasibleSchedule, solver.SolveTimeout) as error:
                errors.append(f"attempt {number}: {error}")
                continue
            rank = _rank_schedule(result.schedule, config, result.objective)
            record["tries"].append({
                "attempt": number, "exhaustive": False,
                "status": result.status.value,
                "objective": result.objective, "worst_overload": rank[1],
                "soft_penalty": rank[2], "random_seed": result.random_seed,
            })
            save()
            if best_rank is None or rank < best_rank:
                best_rank, best_result = rank, result
            # Nothing left to improve on the dimensions we rank by.
            if rank[0] == 0 and rank[1] == 0.0 and result.status is solver.SolveStatus.OPTIMAL:
                break

        record["finished_at"] = datetime.now(UTC).isoformat()
        if best_result is None:
            record["status"] = "error"
            record["message"] = "; ".join(errors)
            save()
            raise solver.SolveTimeout(
                "No feasible schedule in any attempt: " + "; ".join(errors)
            )
        template_changes = (
            compare_template(best_result.schedule)
            if compare_template is not None else None
        )
        record.update(
            status="changed", output=best_result.schedule.to_records(),
            objective=best_result.objective, random_seed=best_result.random_seed,
        )
        if template_changes is not None:
            record["template_changes"] = template_changes
        save()
        return {
            "status": "changed", "result": best_result,
            "attempt_id": attempt_id, "tries": record["tries"],
            "template_changes": template_changes,
        }
    finally:
        _lock.release()
