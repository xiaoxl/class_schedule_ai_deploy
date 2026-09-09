"""Temporary, package-scoped history for non-repeating browser solves."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from . import solver
from .schedule_model import Schedule

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
