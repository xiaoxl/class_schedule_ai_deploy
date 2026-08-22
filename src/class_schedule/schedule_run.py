"""Run a complete term solve and write a versioned, auditable result bundle."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .schedule_model import (
    HardViolation,
    Schedule,
    SoftFinding,
    check_conflicts,
    check_soft_preferences,
)
from .overrides import OverrideFile, apply_overrides, load_overrides
from .solver import (
    InfeasibleSchedule,
    SolveResult,
    SolveTimeout,
    SolverConfig,
    diff_schedules,
    solve_detailed,
)


@dataclass(frozen=True)
class Attempt:
    number: int
    result: SolveResult | None
    soft_penalty: float | None
    soft_findings: tuple[SoftFinding, ...] = ()
    hard_violations: tuple[HardViolation, ...] = ()
    worst_overload: float | None = None
    error: str | None = None

    @property
    def ranking(self) -> tuple[float, float, float]:
        if self.result is None:
            return (float("inf"), float("inf"), float("inf"))
        return (
            self.worst_overload or 0.0,
            self.result.objective,
            self.soft_penalty or 0.0,
        )


@dataclass(frozen=True)
class RunBundle:
    term: str
    version: str
    output_dir: Path
    schedule_path: Path
    report_path: Path
    attempts_path: Path
    changes_path: Path
    manifest_path: Path
    overrides_path: Path
    best_attempt: Attempt
    attempts: tuple[Attempt, ...]


def teaching_loads(schedule: Schedule) -> dict[str, float]:
    totals: dict[str, float] = {}
    for item in schedule.classes:
        for instructor in {s.instructor for s in item.sections if s.instructor}:
            totals[instructor] = totals.get(instructor, 0.0) + item.credit_hours
    return totals


def worst_overload(schedule: Schedule, config: SolverConfig) -> float:
    loads = teaching_loads(schedule)
    return max(
        (max(0.0, loads.get(name, 0.0) - person.max_load)
         for name, person in config.persons.items()),
        default=0.0,
    )


def next_version(term_dir: Path) -> str:
    versions = []
    if term_dir.exists():
        for path in term_dir.iterdir():
            match = re.fullmatch(r"ver(\d+)", path.name)
            if path.is_dir() and match:
                versions.append(int(match.group(1)))
    return f"ver{max(versions, default=0) + 1}"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evaluate_attempt(number: int, result: SolveResult, config: SolverConfig) -> Attempt:
    hard = tuple(check_conflicts(result.schedule))
    soft_penalty, soft = check_soft_preferences(
        result.schedule, config.preferences, config.persons, config.global_rules
    )
    return Attempt(
        number=number,
        result=result,
        soft_penalty=soft_penalty,
        soft_findings=tuple(soft),
        hard_violations=hard,
        worst_overload=worst_overload(result.schedule, config),
    )


def _attempt_rows(attempts: tuple[Attempt, ...]) -> list[dict[str, object]]:
    rows = []
    for attempt in attempts:
        result = attempt.result
        rows.append({
            "Attempt": attempt.number,
            "Status": result.status.value if result else "failed",
            "Objective": result.objective if result else None,
            "BestBound": result.best_bound if result else None,
            "SolveSeconds": result.solve_seconds if result else None,
            "CandidateCount": result.candidate_count if result else None,
            "SoftPenalty": attempt.soft_penalty,
            "SoftFindings": len(attempt.soft_findings),
            "HardViolations": len(attempt.hard_violations),
            "WorstOverload": attempt.worst_overload,
            "Error": attempt.error,
        })
    return rows


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:g}"


def _report(
    term: str,
    version: str,
    input_path: Path,
    before: Schedule,
    config: SolverConfig,
    attempts: tuple[Attempt, ...],
    best: Attempt,
    per_attempt_seconds: float,
) -> str:
    assert best.result is not None
    after = best.result.schedule
    before_hard = check_conflicts(before)
    before_soft_total, before_soft = check_soft_preferences(
        before, config.preferences, config.persons, config.global_rules
    )
    before_loads, after_loads = teaching_loads(before), teaching_loads(after)
    changes = list(dict.fromkeys(diff_schedules(before, after)))
    unresolved = sorted(
        {s.instructor for item in after.classes for s in item.sections
         if s.instructor.lower().startswith("staff")}
    )

    lines = [
        f"# {term} {version} solve report",
        "",
        f"Input: `{input_path.as_posix()}` ({len(before)} atomic classes, "
        f"{len(before.to_records())} rows)",
        "",
        f"Configuration version: `{config.version or 'unversioned'}`",
        "",
        f"Ran {len(attempts)} independent attempt(s), each with a "
        f"{per_attempt_seconds:g}s CP-SAT budget. Selected attempt {best.number} "
        "by lowest worst instructor overload, then lowest solver objective, "
        "then lowest reported soft penalty.",
        "",
        "## Selected result",
        "",
        f"- Solver status: {best.result.status.value}",
        f"- Solver objective: {_fmt(best.result.objective)}",
        f"- Best objective bound: {_fmt(best.result.best_bound)}",
        f"- Solve time: {_fmt(best.result.solve_seconds)} seconds",
        f"- Candidate assignments: {best.result.candidate_count}",
        f"- Hard violations: {len(best.hard_violations)}",
        f"- Soft penalty: {_fmt(best.soft_penalty)} ({len(best.soft_findings)} findings)",
        f"- Worst instructor overload: {_fmt(best.worst_overload)} credit hours",
        f"- Remaining placeholder identities: {', '.join(unresolved) if unresolved else 'none'}",
        "",
        "## Attempt comparison",
        "",
        "| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for attempt in attempts:
        result = attempt.result
        lines.append(
            f"| {attempt.number} | {result.status.value if result else 'failed'} | "
            f"{_fmt(result.objective if result else None)} | "
            f"{_fmt(result.best_bound if result else None)} | "
            f"{_fmt(result.solve_seconds if result else None)} | "
            f"{_fmt(attempt.soft_penalty)} | {_fmt(attempt.worst_overload)} | "
            f"{len(attempt.hard_violations)} |"
        )

    lines.extend([
        "",
        "## Before and after",
        "",
        "| Metric | Before | After |",
        "|---|---:|---:|",
        f"| Hard violations | {len(before_hard)} | {len(best.hard_violations)} |",
        f"| Soft penalty | {_fmt(before_soft_total)} | {_fmt(best.soft_penalty)} |",
        f"| Soft findings | {len(before_soft)} | {len(best.soft_findings)} |",
        f"| Worst overload | {_fmt(worst_overload(before, config))} | "
        f"{_fmt(best.worst_overload)} |",
        "",
        "## Teaching loads",
        "",
        "| Instructor | Target | Before | After | Delta |",
        "|---|---:|---:|---:|---:|",
    ])
    names = sorted(set(before_loads) | set(after_loads) | set(config.persons))
    for name in names:
        target = config.persons[name].max_load if name in config.persons else None
        left, right = before_loads.get(name, 0.0), after_loads.get(name, 0.0)
        lines.append(
            f"| {name} | {_fmt(target)} | {_fmt(left)} | {_fmt(right)} | "
            f"{right - left:+g} |"
        )

    lines.extend(["", "## Changes from input", ""])
    if changes:
        for change in changes:
            lines.append(
                f"- **{change.course_id}** {change.field}: "
                f"`{change.before}` -> `{change.after}`"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Remaining hard violations", ""])
    if best.hard_violations:
        lines.extend(f"- [{item.rule}] {item.message}" for item in best.hard_violations)
    else:
        lines.append("- none")

    lines.extend(["", "## Remaining soft findings", ""])
    if best.soft_findings:
        lines.extend(
            f"- [{item.rule}] ({item.penalty:g}) {item.message}"
            for item in best.soft_findings
        )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def run_term(
    term: str,
    *,
    input_path: str | Path | None = None,
    output_root: str | Path = "out",
    config_dir: str | Path = "config",
    version: str | None = None,
    attempts: int = 5,
    time_limit_seconds: float = 45.0,
    overrides_path: str | Path | None = None,
    parent: str | None = None,
) -> RunBundle:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be positive")

    output_root = Path(output_root)
    term_dir = output_root / term
    input_path = Path(input_path) if input_path else term_dir / "starting.csv"
    version = version or next_version(term_dir)
    if not re.fullmatch(r"ver\d+", version):
        raise ValueError("version must have the form 'verN', for example 'ver3'")
    destination = term_dir / version
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing result: {destination}")

    config = SolverConfig.load(config_dir, term=term)
    dataframe = pd.read_csv(input_path, dtype=str) if input_path.suffix.lower() == ".csv" else pd.read_excel(input_path, dtype=str)
    source_schedule = Schedule.from_dataframe(dataframe.dropna(how="all"), persons=config.persons)
    overrides = load_overrides(overrides_path) if overrides_path else OverrideFile()
    starting = apply_overrides(source_schedule, overrides)

    attempt_results: list[Attempt] = []
    for number in range(1, attempts + 1):
        try:
            result = solve_detailed(
                starting, config, time_limit_seconds=time_limit_seconds,
                locks=overrides.locks,
            )
            attempt_results.append(_evaluate_attempt(number, result, config))
        except SolveTimeout as error:
            attempt_results.append(Attempt(number, None, None, error=str(error)))
        except InfeasibleSchedule:
            raise

    successful = [attempt for attempt in attempt_results if attempt.result is not None]
    if not successful:
        raise SolveTimeout("Every solve attempt expired before finding a feasible schedule")
    best = min(successful, key=lambda attempt: attempt.ranking)
    attempts_tuple = tuple(attempt_results)
    assert best.result is not None

    term_dir.mkdir(parents=True, exist_ok=True)
    staging = term_dir / f".{version}-staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        base = f"{term}_{version}"
        schedule_path = staging / f"{base}.csv"
        report_path = staging / "report.md"
        attempts_path = staging / "attempts.csv"
        changes_path = staging / "changes.csv"
        manifest_path = staging / "manifest.json"
        saved_overrides_path = staging / "overrides.toml"
        best.result.schedule.to_dataframe().to_csv(schedule_path, index=False)
        pd.DataFrame(_attempt_rows(attempts_tuple)).to_csv(attempts_path, index=False)
        changes = list(dict.fromkeys(diff_schedules(source_schedule, best.result.schedule)))
        pd.DataFrame(
            ({"Course ID": item.course_id, "Field": item.field,
              "Before": item.before, "After": item.after} for item in changes),
            columns=("Course ID", "Field", "Before", "After"),
        ).to_csv(changes_path, index=False)
        if overrides_path:
            saved_overrides_path.write_bytes(Path(overrides_path).read_bytes())
        else:
            saved_overrides_path.write_text(
                "# No manual edits or locks were applied to this version.\n",
                encoding="utf-8",
            )
        report_path.write_text(
            _report(
                term, version, input_path, source_schedule, config, attempts_tuple,
                best, time_limit_seconds,
            ),
            encoding="utf-8",
        )
        artifact_names = (schedule_path.name, report_path.name, attempts_path.name,
                          changes_path.name, saved_overrides_path.name)
        manifest = {
            "schema_version": 1,
            "term": term,
            "version": version,
            "parent": parent,
            "created_at": datetime.now(UTC).isoformat(),
            "input": {"path": str(input_path), "sha256": _sha256(input_path)},
            "configuration": {
                "version": config.version,
                "files": [
                    {"path": name, "sha256": _sha256(Path(name))}
                    for name in config.source_paths
                ],
            },
            "overrides_sha256": _sha256(saved_overrides_path),
            "selected_attempt": best.number,
            "solver": {
                "status": best.result.status.value,
                "objective": best.result.objective,
                "best_bound": best.result.best_bound,
                "random_seed": best.result.random_seed,
                "time_limit_seconds": time_limit_seconds,
                "attempts": attempts,
            },
            "validation": {
                "hard_violations": len(best.hard_violations),
                "soft_penalty": best.soft_penalty,
                "worst_overload": best.worst_overload,
            },
            "files": {
                name: _sha256(staging / name) for name in artifact_names
            },
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        staging.replace(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    return RunBundle(
        term=term,
        version=version,
        output_dir=destination,
        schedule_path=destination / f"{term}_{version}.csv",
        report_path=destination / "report.md",
        attempts_path=destination / "attempts.csv",
        changes_path=destination / "changes.csv",
        manifest_path=destination / "manifest.json",
        overrides_path=destination / "overrides.toml",
        best_attempt=best,
        attempts=attempts_tuple,
    )


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Solve a term schedule and write out/TERM/verN CSV/Markdown results."
    )
    parser.add_argument("term", help="term identifier, for example 27S")
    parser.add_argument("--input", help="starting CSV/XLSX (default: out/TERM/starting.csv)")
    parser.add_argument("--output-root", default="out")
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--version", help="explicit version such as ver3; defaults to next available")
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--seconds", type=float, default=45.0, help="CP-SAT budget per attempt")
    parser.add_argument("--overrides", help="manual edits/locks TOML")
    parser.add_argument("--parent", help="parent version, for example ver3")
    args = parser.parse_args()

    bundle = run_term(
        args.term,
        input_path=args.input,
        output_root=args.output_root,
        config_dir=args.config_dir,
        version=args.version,
        attempts=args.attempts,
        time_limit_seconds=args.seconds,
        overrides_path=args.overrides,
        parent=args.parent,
    )
    best = bundle.best_attempt
    print(f"Wrote {bundle.output_dir}")
    print(f"Schedule: {bundle.schedule_path}")
    print(f"Report: {bundle.report_path}")
    print(
        f"Selected attempt {best.number}: soft={best.soft_penalty:g}, "
        f"worst_overload={best.worst_overload:g}"
    )


if __name__ == "__main__":
    _main()
