"""Solve a term and atomically publish an auditable verN or final bundle."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .instructor_identity import is_new_instructor, is_new_professor
from .schedule_model import (
    HardViolation,
    Schedule,
    SoftFinding,
    evaluate_schedule,
    summarize_instructor_loads,
    teaching_loads,
)
from .schedule_io import read_schedule
from .overrides import (
    OverrideFile,
    apply_overrides,
    load_overrides,
    render_override_template,
    validate_override_context,
)
from .solver import (
    DEFAULT_SEARCH_WORKERS,
    InfeasibleSchedule,
    SolveResult,
    SolveStatus,
    SolveTimeout,
    SolverConfig,
    diff_schedules,
    solve_detailed,
)
from .version_publisher import publish_version


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
    def ranking(self) -> tuple[float, float, float, float]:
        """Fewer hard violations always outranks a "cleaner" objective --
        see docs/codes.md: publication is never blocked on hard violations,
        but among several attempts we still prefer the least-broken one."""
        if self.result is None:
            return (float("inf"), float("inf"), float("inf"), float("inf"))
        return (
            len(self.hard_violations),
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
    instructor_path: Path
    room_path: Path
    report_path: Path
    attempts_path: Path
    changes_path: Path
    baseline_path: Path
    manifest_path: Path
    overrides_path: Path
    applied_overrides_path: Path
    reconciliation_path: Path
    best_attempt: Attempt
    attempts: tuple[Attempt, ...]


def worst_overload(schedule: Schedule, config: SolverConfig) -> float:
    loads = teaching_loads(schedule)
    return max(
        (max(
            0.0,
            loads.get(name, 0.0) - person.max_load
            - config.workload_policy.overload_tolerance,
        )
         for name, person in config.persons.items()),
        default=0.0,
    )


def simplified_changes(before: Schedule, after: Schedule):
    """Return the direct field diff, eliminating all intermediate changes."""
    return tuple(dict.fromkeys(diff_schedules(before, after)))


def latest_version(term_dir: Path) -> str | None:
    versions = []
    if term_dir.exists():
        for path in term_dir.iterdir():
            match = re.fullmatch(r"ver(\d+)", path.name)
            if path.is_dir() and match:
                versions.append(int(match.group(1)))
    return f"ver{max(versions)}" if versions else None


def next_version(term_dir: Path) -> str:
    latest = latest_version(term_dir)
    return f"ver{int(latest[3:]) + 1}" if latest else "ver1"


def infer_parent_version(input_path: Path, term_dir: Path) -> str | None:
    """Infer ``verN`` when the input file lives inside that version directory."""
    try:
        relative = input_path.resolve().relative_to(term_dir.resolve())
    except ValueError:
        return None
    if not relative.parts:
        return None
    return relative.parts[0] if re.fullmatch(r"ver\d+", relative.parts[0]) else None


def version_schedule_path(
    term: str,
    version: str,
    *,
    output_root: str | Path = "out",
) -> Path:
    """Return the canonical CSV for an existing published version."""
    if re.fullmatch(r"ver\d+", version) is None:
        raise ValueError("source version must have the form 'verN'")
    path = Path(output_root) / term / version / f"{term}_{version}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Published schedule does not exist: {path}")
    return path


def _bound_version_package(version_dir: Path, requested: str | None) -> str | None:
    """Use a published version's package and reject an explicit mismatch."""
    manifest_path = version_dir / "manifest.json"
    if not manifest_path.is_file():
        return requested
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    recorded = manifest.get("configuration", {}).get("package_id")
    if recorded and requested and recorded != requested:
        raise ValueError(
            f"Configuration package {requested!r} does not match the source "
            f"version package {recorded!r}"
        )
    return requested or recorded


def create_override_template(
    term: str,
    from_version: str,
    *,
    output_path: str | Path | None = None,
    output_root: str | Path = "out",
    config_dir: str | Path = "config",
    package: str | None = None,
) -> Path:
    """Generate a no-op, version-bound manual-revision TOML template."""
    source_path = version_schedule_path(term, from_version, output_root=output_root)
    package = _bound_version_package(source_path.parent, package)
    config = SolverConfig.load(config_dir, package=package or "27S")
    schedule = read_schedule(
        source_path, persons=config.persons,
        relationships=tuple(config.courses.relationships) if config.courses else (),
        catalogs=tuple(config.catalogs.courses) if config.catalogs else (),
    )
    destination = Path(
        output_path
        or source_path.parent / "overrides.toml"
    )
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite override template: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        render_override_template(schedule, term=term, source_version=from_version),
        encoding="utf-8",
    )
    return destination


def install_version_override_template(
    term: str,
    version: str,
    *,
    output_root: str | Path = "out",
    config_dir: str | Path = "config",
    package: str | None = None,
) -> Path:
    """Install the mutable override workspace and preserve prior audit input."""
    source_path = version_schedule_path(term, version, output_root=output_root)
    package = _bound_version_package(source_path.parent, package)
    version_dir = source_path.parent
    workspace = version_dir / "overrides.toml"
    applied = version_dir / "applied_overrides.toml"
    if not applied.exists():
        if workspace.exists():
            applied.write_bytes(workspace.read_bytes())
        else:
            applied.write_text(
                "# No applied override file was recorded for this imported version.\n",
                encoding="utf-8",
            )
    config = SolverConfig.load(config_dir, package=package or "27S")
    schedule = read_schedule(
        source_path, persons=config.persons,
        relationships=tuple(config.courses.relationships) if config.courses else (),
        catalogs=tuple(config.catalogs.courses) if config.catalogs else (),
    )
    workspace.write_text(
        render_override_template(schedule, term=term, source_version=version),
        encoding="utf-8",
    )
    manifest_path = version_dir / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest.setdefault("files", {})
        baseline_info = manifest.get(
            "initial_baseline", manifest.get("change_baseline", {})
        )
        recorded_baseline = Path(str(baseline_info.get("path", "")))
        baseline_snapshot = version_dir / "baseline.csv"
        if recorded_baseline.is_file():
            expected_hash = baseline_info.get("sha256")
            if expected_hash and _sha256(recorded_baseline) != expected_hash:
                raise ValueError(
                    f"Recorded baseline has changed since {version} was published: "
                    f"{recorded_baseline}"
                )
            read_schedule(
                recorded_baseline, persons=config.persons,
                relationships=tuple(config.courses.relationships) if config.courses else (),
                catalogs=tuple(config.catalogs.courses) if config.catalogs else (),
            ).to_dataframe().to_csv(baseline_snapshot, index=False)
            baseline_info["snapshot"] = baseline_snapshot.name
            files[baseline_snapshot.name] = _sha256(baseline_snapshot)
        files.pop("overrides.toml", None)
        files[applied.name] = _sha256(applied)
        manifest["schema_version"] = max(4, int(manifest.get("schema_version", 1)))
        manifest.pop("overrides_sha256", None)
        manifest["applied_overrides_sha256"] = _sha256(applied)
        manifest["override_workspace"] = {
            "path": workspace.name,
            "mutable": True,
            "source_version": version,
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    return workspace


def publish_final(
    term: str,
    from_version: str,
    *,
    output_root: str | Path = "out",
    config_dir: str | Path = "config",
    package: str | None = None,
    attempts: int = 5,
    time_limit_seconds: float = 45.0,
    search_workers: int = DEFAULT_SEARCH_WORKERS,
) -> RunBundle:
    """Apply a version's embedded overrides and atomically refresh ``final``."""
    source_path = version_schedule_path(term, from_version, output_root=output_root)
    package = _bound_version_package(source_path.parent, package)
    overrides_path = source_path.parent / "overrides.toml"
    if not overrides_path.is_file():
        raise FileNotFoundError(
            f"Embedded override file does not exist: {overrides_path}"
        )
    overrides = load_overrides(overrides_path)
    if not overrides.edits and not overrides.locks:
        raise ValueError(
            f"No manual edits or locks are enabled in {overrides_path}"
        )
    baseline_path = source_path.parent / "baseline.csv"
    if not baseline_path.is_file():
        raise FileNotFoundError(
            f"Source version has no baseline snapshot: {baseline_path}"
        )
    return run_term(
        term,
        input_path=source_path,
        output_root=output_root,
        config_dir=config_dir,
        package=package,
        version="final",
        attempts=attempts,
        time_limit_seconds=time_limit_seconds,
        search_workers=search_workers,
        overrides_path=overrides_path,
        parent=from_version,
        baseline_path=baseline_path,
        replace_destination=True,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"Required provenance manifest does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _verified_initial(initial_path: Path) -> tuple[Path, dict[str, object]]:
    """Verify an initial artifact and its generated reconciliation audit."""
    manifest = _load_json(initial_path.parent / "manifest.json")
    if manifest.get("role") != "initial":
        raise ValueError(f"Not an initial artifact manifest: {initial_path.parent}")
    initial_info = manifest.get("initial", {})
    if not isinstance(initial_info, dict):
        raise ValueError("Initial manifest has no initial artifact record")
    if initial_info.get("path") != initial_path.name:
        raise ValueError("Initial manifest points to a different schedule file")
    if initial_info.get("sha256") != _sha256(initial_path):
        raise ValueError(f"Initial schedule changed after publication: {initial_path}")
    audit_info = manifest.get("reconciliation", {})
    audit = initial_path.parent / str(audit_info.get("snapshot", "reconciliation.toml"))
    if not audit.is_file() or audit_info.get("sha256") != _sha256(audit):
        legacy = manifest.get("changes", {})
        audit = Path(str(legacy.get("path", "")))
        if not audit.is_file() or legacy.get("sha256") != _sha256(audit):
            raise ValueError("Initial reconciliation audit is missing or changed")
    return audit, manifest


def _verified_parent_baseline(
    term: str, parent: str, term_dir: Path,
) -> tuple[Path, Path]:
    """Return the immutable initial baseline and reconciliation snapshot."""
    parent_dir = term_dir / parent
    manifest = _load_json(parent_dir / "manifest.json")
    baseline_info = manifest.get("initial_baseline", {})
    if not isinstance(baseline_info, dict) or baseline_info.get("role") != "initial":
        raise ValueError(
            f"{term} {parent} is a legacy/non-initial version chain; "
            "start the next normal version from work/TERM/initial/initial.csv"
        )
    snapshot = parent_dir / str(baseline_info.get("snapshot", "baseline.csv"))
    if not snapshot.is_file():
        raise FileNotFoundError(f"Parent version has no initial baseline snapshot: {snapshot}")
    files = manifest.get("files", {})
    if not isinstance(files, dict) or files.get(snapshot.name) != _sha256(snapshot):
        raise ValueError(f"Parent initial baseline snapshot failed hash verification: {snapshot}")
    reconciliation = parent_dir / "reconciliation.toml"
    if not reconciliation.is_file():
        legacy = parent_dir / "applied_changes.toml"
        if legacy.is_file():
            reconciliation = legacy
        else:
            raise FileNotFoundError(
                f"Parent version has no reconciliation snapshot: {reconciliation}"
            )
    return snapshot, reconciliation


def _evaluate_attempt(number: int, result: SolveResult, config: SolverConfig) -> Attempt:
    evaluation = evaluate_schedule(
        result.schedule, config.preferences, config.persons, config.global_rules,
        config.meeting_patterns, config.constraint_rules,
        config.workload_policy, config.back_to_back_policy,
        config.new_instructor_policy, config.new_professor_policy,
    )
    return Attempt(
        number=number,
        result=result,
        soft_penalty=evaluation.soft_penalty,
        soft_findings=evaluation.soft_findings,
        hard_violations=evaluation.hard_violations,
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
            "SearchWorkers": result.search_workers if result else None,
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
    solver_input: Schedule,
    baseline_path: Path,
    baseline: Schedule,
    reconciliation_path: Path | None,
    config: SolverConfig,
    attempts: tuple[Attempt, ...],
    best: Attempt,
    per_attempt_seconds: float,
) -> str:
    assert best.result is not None
    after = best.result.schedule
    baseline_evaluation = evaluate_schedule(
        baseline, config.preferences, config.persons, config.global_rules,
        config.meeting_patterns, config.constraint_rules,
        config.workload_policy, config.back_to_back_policy,
        config.new_instructor_policy, config.new_professor_policy,
    )
    before_loads = baseline_evaluation.loads
    after_loads = teaching_loads(after)
    load_rows = summarize_instructor_loads(
        after_loads, config.persons,
        new_instructor_target=config.new_instructor_policy.contract_load,
        new_professor_target=config.new_professor_policy.contract_load,
        overload_tolerance=config.workload_policy.overload_tolerance,
    )
    targets = {row.name: row.target for row in load_rows}
    changes = simplified_changes(baseline, after)
    unresolved = sorted(
        {s.instructor for item in after.classes for s in item.sections
         if is_new_instructor(s.instructor) or is_new_professor(s.instructor)}
    )

    lines = [
        f"# {term} {version} solve report",
        "",
        f"Validated solver input: `{input_path.as_posix()}` "
        f"({len(solver_input)} atomic classes, "
        f"{len(solver_input.to_records())} rows)",
        "",
        f"Initial baseline: `{baseline_path.as_posix()}` ({len(baseline)} atomic classes, "
        f"{len(baseline.to_records())} rows)",
        "",
        (
            f"Reconciliation snapshot: `{reconciliation_path.as_posix()}`"
            if reconciliation_path is not None
            else "Reconciliation snapshot: unavailable for historical backfill"
        ),
        "",
        f"Configuration version: `{config.version or 'unversioned'}`",
        "",
        f"Ran {len(attempts)} independent attempt(s), each with a "
        f"{per_attempt_seconds:g}s CP-SAT budget and "
        f"{best.result.search_workers} search worker(s). "
        f"Selected attempt {best.number} "
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
        f"- CP-SAT search workers: {best.result.search_workers}",
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
        f"| Hard violations | {len(baseline_evaluation.hard_violations)} | "
        f"{len(best.hard_violations)} |",
        f"| Soft penalty | {_fmt(baseline_evaluation.soft_penalty)} | "
        f"{_fmt(best.soft_penalty)} |",
        f"| Soft findings | {len(baseline_evaluation.soft_findings)} | "
        f"{len(best.soft_findings)} |",
        f"| Worst overload | {_fmt(worst_overload(baseline, config))} | "
        f"{_fmt(best.worst_overload)} |",
        "",
        "## Teaching loads",
        "",
        "| Instructor | Target | Before | After | Delta |",
        "|---|---:|---:|---:|---:|",
    ])
    names = sorted(set(before_loads) | set(after_loads) | set(config.persons))
    for name in names:
        target = targets.get(name)
        left, right = before_loads.get(name, 0.0), after_loads.get(name, 0.0)
        lines.append(
            f"| {name} | {_fmt(target)} | {_fmt(left)} | {_fmt(right)} | "
            f"{right - left:+g} |"
        )

    lines.extend(["", "## Simplified changes from initial", ""])
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
    package: str | None = None,
    version: str | None = None,
    attempts: int = 5,
    time_limit_seconds: float = 45.0,
    search_workers: int = DEFAULT_SEARCH_WORKERS,
    overrides_path: str | Path | None = None,
    initial_path: str | Path | None = None,
    parent: str | None = None,
    baseline_path: str | Path | None = None,
    historical_backfill: bool = False,
    replace_destination: bool = False,
) -> RunBundle:
    if package is not None and term.upper() != package.upper():
        raise ValueError(
            f"Output namespace {term!r} must match configuration package {package!r}"
        )
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be positive")
    if search_workers < 1:
        raise ValueError("search_workers must be at least 1")

    output_root = Path(output_root)
    term_dir = output_root / term
    canonical_initial = Path(
        initial_path or Path("work") / term / "initial" / "initial.csv"
    )
    input_path = Path(input_path) if input_path else canonical_initial
    version = version or next_version(term_dir)
    parent = parent or infer_parent_version(input_path, term_dir)
    is_final = version == "final"
    if not re.fullmatch(r"ver\d+", version) and not is_final:
        raise ValueError("version must have the form 'verN', for example 'ver3'")
    if replace_destination and not is_final:
        raise ValueError("Only the final publication channel may be replaced")
    destination = term_dir / version
    if destination.exists() and not replace_destination:
        raise FileExistsError(f"Refusing to overwrite existing result: {destination}")

    if historical_backfill:
        baseline_path = Path(baseline_path) if baseline_path else input_path
        reconciliation_path = None
    elif is_final:
        if parent is None:
            raise ValueError("final requires an explicit source verN")
        expected_input = version_schedule_path(term, parent, output_root=output_root)
        if input_path.resolve() != expected_input.resolve():
            raise ValueError(f"Parent {parent} does not match final input {input_path}")
        inherited_baseline, inherited_reconciliation = _verified_parent_baseline(
            term, parent, term_dir
        )
        if baseline_path is not None and Path(baseline_path).resolve() != inherited_baseline.resolve():
            raise ValueError("final baseline must be inherited from its source ver")
        baseline_path = inherited_baseline
        reconciliation_path = inherited_reconciliation
    else:
        if parent is not None:
            raise ValueError(
                "Every automatic ver must start from initial; a previous ver cannot "
                "be used as solve input"
            )
        if baseline_path is not None:
            raise ValueError(
                "Automatic ver baseline is always initial; --baseline is only for "
                "--historical-backfill"
            )
        if input_path.resolve() != canonical_initial.resolve():
            raise ValueError(
                "Every automatic ver must use the initial schedule as input; "
                "use --historical-backfill only for explicit legacy reconstruction"
            )
        reconciliation_path, initial_manifest = _verified_initial(canonical_initial)
        initial_package = initial_manifest.get("configuration", {}).get("package_id")
        requested_package = package or initial_package or "27S"
        if initial_package and initial_package != requested_package:
            raise ValueError(
                f"Configuration package {requested_package!r} does not match the "
                f"initial schedule package {initial_package!r}"
            )
        package = requested_package
        baseline_path = canonical_initial
    assert baseline_path is not None
    if not Path(baseline_path).is_file():
        raise FileNotFoundError(f"Initial baseline does not exist: {baseline_path}")
    baseline_path = Path(baseline_path)
    if (
        not historical_backfill and not is_final
        and baseline_path.resolve() != input_path.resolve()
    ):
        raise ValueError("Automatic ver input and baseline must both be initial.csv")

    config = SolverConfig.load(config_dir, package=package or "27S")
    relationships = tuple(config.courses.relationships) if config.courses else ()
    catalogs = tuple(config.catalogs.courses) if config.catalogs else ()
    source_schedule = read_schedule(
        input_path, persons=config.persons, relationships=relationships,
        catalogs=catalogs,
    )
    baseline_schedule = (
        source_schedule if baseline_path.resolve() == input_path.resolve()
        else read_schedule(
            baseline_path, persons=config.persons, relationships=relationships,
            catalogs=catalogs,
        )
    )
    overrides = load_overrides(overrides_path) if overrides_path else OverrideFile()
    validate_override_context(overrides, term=term, source_version=parent)
    adjusted_input = apply_overrides(source_schedule, overrides)

    attempt_results: list[Attempt] = []
    for number in range(1, attempts + 1):
        try:
            result = solve_detailed(
                adjusted_input, config, time_limit_seconds=time_limit_seconds,
                locks=overrides.locks,
                search_workers=search_workers,
            )
            attempt = _evaluate_attempt(number, result, config)
            attempt_results.append(attempt)
            if result.status is SolveStatus.OPTIMAL and not attempt.hard_violations:
                break
        except SolveTimeout as error:
            attempt_results.append(Attempt(number, None, None, error=str(error)))
        except InfeasibleSchedule as error:
            # Never a hard stop on its own (see docs/codes.md): this attempt's
            # candidate space had no feasible assignment, but another attempt
            # (different random seed) may still produce one. Only the total
            # absence of any usable result below gives up for real.
            attempt_results.append(Attempt(number, None, None, error=str(error)))

    candidates = [attempt for attempt in attempt_results if attempt.result is not None]
    if not candidates:
        # There is truly nothing to publish -- not "some attempts had
        # violations", but zero attempts produced a schedule at all. This is
        # the one case that still has to fail outright: a report can't
        # describe a schedule that was never built.
        errors = list(dict.fromkeys(a.error for a in attempt_results if a.error))
        if errors:
            raise InfeasibleSchedule(
                "Every solve attempt returned an invalid schedule: "
                + "; ".join(errors)
            )
        raise SolveTimeout("Every solve attempt expired before finding a feasible schedule")
    best = min(candidates, key=lambda attempt: attempt.ranking)
    attempts_tuple = tuple(attempt_results)
    assert best.result is not None

    applied_overrides = (
        Path(overrides_path).read_bytes() if overrides_path
        else b"# No manual edits or locks were applied to this version.\n"
    )
    reconciliation = (
        reconciliation_path.read_bytes() if reconciliation_path is not None
        else b"# Historical backfill has no package reconciliation audit.\n"
    )
    manifest = {
            "schema_version": 4,
            "term": term,
            "version": version,
            "parent": parent,
            "created_at": datetime.now(UTC).isoformat(),
            "input": {"path": str(input_path), "sha256": _sha256(input_path)},
            "initial_baseline": {
                "path": str(baseline_path),
                "sha256": _sha256(baseline_path),
                "snapshot": "baseline.csv",
                "role": "initial",
            },
            "configuration": {
                "package_id": config.package_id,
                "version": config.version,
                "files": [
                    {"path": name, "sha256": _sha256(Path(name))}
                    for name in config.source_paths
                ],
            },
            "reconciliation": {
                "source": "courses.toml",
                "sha256": hashlib.sha256(reconciliation).hexdigest(),
                "snapshot": "reconciliation.toml",
            },
            "applied_overrides_sha256": hashlib.sha256(applied_overrides).hexdigest(),
            "override_workspace": {
                "path": "overrides.toml",
                "mutable": not is_final,
                "source_version": parent if is_final else version,
            },
            "selected_attempt": best.number,
            "solver": {
                "status": best.result.status.value,
                "objective": best.result.objective,
                "best_bound": best.result.best_bound,
                "random_seed": best.result.random_seed,
                "time_limit_seconds": time_limit_seconds,
                "search_workers": best.result.search_workers,
                "attempts": len(attempts_tuple),
                "attempts_requested": attempts,
                "attempts_run": len(attempts_tuple),
            },
            "validation": {
                "hard_violations": len(best.hard_violations),
                "soft_penalty": best.soft_penalty,
                "worst_overload": best.worst_overload,
            },
        }
    published = publish_version(
        term=term, version=version, destination=destination,
        schedule=best.result.schedule, baseline=baseline_schedule,
        baseline_bytes=baseline_path.read_bytes(),
        attempts_rows=_attempt_rows(attempts_tuple),
        report=_report(
            term, version, input_path, source_schedule,
            baseline_path, baseline_schedule, reconciliation_path,
            config, attempts_tuple, best, time_limit_seconds,
        ),
        manifest=manifest,
        applied_overrides=applied_overrides,
        reconciliation=reconciliation,
        final=is_final,
        replace_destination=replace_destination,
    )

    return RunBundle(
        term=term,
        version=version,
        output_dir=published.output_dir,
        schedule_path=published.schedule_path,
        instructor_path=published.instructor_path,
        room_path=published.room_path,
        report_path=published.report_path,
        attempts_path=published.attempts_path,
        changes_path=published.changes_path,
        baseline_path=published.baseline_path,
        manifest_path=published.manifest_path,
        overrides_path=published.overrides_path,
        applied_overrides_path=published.applied_overrides_path,
        reconciliation_path=published.reconciliation_path,
        best_attempt=best,
        attempts=attempts_tuple,
    )
