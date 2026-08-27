"""Web app: load a configuration workspace schedule and optionally solve it.

Built on ``schedule_model.Schedule`` / ``class_model``. Every workspace is
evaluated against the resolved persons and preferences configuration
-- see ``schedule_model.check_soft_preferences`` (everything, including
max_load) / hard validation (room/instructor double-booking plus configured
hard constraint rules). ``POST /api/solve`` runs the OR-Tools
solver (``solver.solve_detailed``) on top of that, using
the resolved timeslot/location configuration for the legal time/room search
space. The Web API keeps no server-side editing session; browser publication
and CLI solves both use the shared version publisher.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import shutil
import tempfile
import threading
import tomllib
import uuid
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import psutil
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.staticfiles import StaticFiles

from . import solver as solver_module
from .config_inference import infer_configuration_from_template
from .schedule_io import read_schedule
from .schedule_run import _verified_initial, next_version
from .version_publisher import publish_version, sha256
from .template_workspace import (
    TEMPLATE_SUFFIXES,
    find_template,
    install_template,
    rebuild_work_views,
    template_summary,
)
from .schedule_model import (
    GroupingError,
    HardViolation,
    Schedule,
    SoftFinding,
    evaluate_schedule,
    summarize_instructor_loads,
)

PACKAGE_WEB = Path(__file__).with_name("web")
CONFIG_DIR = Path(os.environ.get(
    "CLASS_SCHEDULE_CONFIG_ROOT",
    Path(__file__).resolve().parents[2] / "config",
))
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_CONFIG_BYTES = 2 * 1024 * 1024
LOG_PATH = Path("output/logs/webapp.log")
CONFIG_FILES = {
    "catalogs.toml": Path("basicinfo/catalogs.toml"),
    "locations.toml": Path("basicinfo/locations.toml"),
    "timeslot.toml": Path("basicinfo/timeslot.toml"),
    "persons.toml": Path("basicinfo/persons.toml"),
    "courses.toml": Path("courses.toml"),
    "preferences.toml": Path("preferences.toml"),
    "constraints.toml": Path("constraints.toml"),
}
PACKAGE_COMMENT = re.compile(
    r"^\s*#\s*Configuration package:\s*(\S(?:.*\S)?)\s*$",
    re.MULTILINE,
)
PACKAGE_ID = re.compile(
    r"^(?:[A-Za-z0-9][A-Za-z0-9_-]*|推断\([1-9]\d*\))$"
)
_CONFIG_WRITE_LOCK = threading.Lock()
CONFIG_TRASH = Path("work/config-trash")
WORK_ROOT = Path("work")

# A soft finding's penalty at or above this is rendered orange in the UI
# (an under_load of at least one credit, a strict instructor's first credit
# past tolerance (100), a permissive one past OVERLOAD_FAR_THRESHOLD, and a
# strongly weighted "dislike" PreferenceRule, land here); below it is
# yellow (back_to_back and mildly weighted preferences, a permissive
# instructor's ordinary overload (10), and a mildly weighted
# PreferenceRule). Every penalty in this system shares one 0-100 scale --
# see the configured workload policy in constraints.toml.
SOFT_SEVERITY_THRESHOLD = 20.0

# This bounds CP-SAT search time per Web request; model construction happens
# before the timed search.
SOLVE_TIME_LIMIT_SECONDS = 60.0

logger = logging.getLogger("class_schedule.webapp")

# Record memory around the model-building endpoint so resource regressions
# remain visible in normal service logs.
_PROCESS = psutil.Process()


def _rss_mb() -> float:
    return _PROCESS.memory_info().rss / (1024 * 1024)


# Configuration errors are deployment errors, not a reason to silently run
# without qualifications/preferences. Fail startup with a precise schema error.
def _default_package() -> str:
    packages = solver_module.list_config_packages(CONFIG_DIR)
    if not packages:
        raise RuntimeError(f"No complete configuration packages found under {CONFIG_DIR}")
    return packages[0].id


DEFAULT_PACKAGE = os.environ.get("CLASS_SCHEDULE_CONFIG_PACKAGE") or _default_package()
SOLVER_CONFIG = solver_module.SolverConfig.load(CONFIG_DIR, package=DEFAULT_PACKAGE)


def _load_web_config(
    package: str = DEFAULT_PACKAGE,
) -> solver_module.SolverConfig:
    try:
        return solver_module.SolverConfig.load(CONFIG_DIR, package=package)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(400, str(error)) from error


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

    @app.get("/api/configurations")
    async def configuration_packages():
        return {
            "configurations": [
                _configuration_summary(path.name)
                for path in sorted(CONFIG_DIR.iterdir(), key=lambda item: item.name.lower())
                if path.is_dir() and PACKAGE_ID.fullmatch(path.name)
            ]
        }

    @app.get("/api/configuration-files")
    async def configuration_files(package: str = DEFAULT_PACKAGE):
        return _configuration_file_payload(package)

    @app.put("/api/configuration-files/{filename}")
    async def update_configuration_file(filename: str, payload: dict):
        package = str(payload.get("package", DEFAULT_PACKAGE)).strip()
        content = payload.get("content")
        if not isinstance(content, str):
            raise HTTPException(400, "Configuration content must be text")
        encoded = content.encode("utf-8")
        commented_package = _package_name_from_comments({filename: encoded})
        if commented_package != package:
            raise HTTPException(
                400, f"Header names package {commented_package}, not selected package {package}",
            )
        return _upsert_configuration_package({filename: encoded})

    @app.post("/api/configuration-packages")
    async def create_configuration_package(
        config_files: list[UploadFile] = File(...),
        current_package: str = Form(DEFAULT_PACKAGE),
    ):
        current_package = current_package.strip()
        if not PACKAGE_ID.fullmatch(current_package):
            raise HTTPException(
                400, f"Invalid configuration package name: {current_package!r}",
            )
        replacements: dict[str, bytes] = {}
        uploaded_template: tuple[str, bytes] | None = None
        for upload in config_files:
            filename = Path(upload.filename or "").name
            if Path(filename).suffix.lower() in TEMPLATE_SUFFIXES:
                if uploaded_template is not None:
                    raise HTTPException(400, "Upload at most one CSV/XLSX template")
                content = await upload.read()
                if not content:
                    raise HTTPException(400, "Schedule template is empty")
                if len(content) > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Schedule template exceeds 50 MB")
                uploaded_template = (filename, content)
                continue
            if filename not in CONFIG_FILES:
                continue
            if filename in replacements:
                raise HTTPException(400, f"Folder contains more than one {filename}")
            replacements[filename] = await upload.read()
        if not replacements and uploaded_template is None:
            raise HTTPException(400, "Upload configuration TOMLs or one CSV/XLSX template")
        routed_package = (
            _package_name_from_comments(replacements) if replacements else None
        )
        changes: dict[str, dict] = {}
        if routed_package:
            changes[routed_package] = {
                "replacements": replacements, "rebuild": True,
            }
        if uploaded_template is not None:
            current = changes.setdefault(current_package, {})
            current["template"] = uploaded_template
            incoming = current.setdefault("replacements", {})
            package_root = CONFIG_DIR / current_package
            needed = [
                filename for filename, relative in CONFIG_FILES.items()
                if filename not in incoming
                and not (package_root / relative).is_file()
            ]
            inferred_names = []
            if needed:
                inferred = _infer_uploaded_template(
                    *uploaded_template, package=current_package,
                )
                missing = _missing_inferred_files(
                    current_package, inferred.files, incoming,
                )
                incoming.update(missing)
                inferred_names = list(missing)
            current["inferred_files"] = inferred_names
            current["rebuild"] = True
        _apply_configuration_transaction(changes)
        package_to_show = current_package if uploaded_template else routed_package
        payload = _configuration_file_payload(package_to_show)
        payload["uploaded_configuration_package"] = routed_package
        payload["inferred_files"] = (
            changes.get(current_package, {}).get("inferred_files", [])
            if uploaded_template else []
        )
        return payload

    @app.get("/api/configuration-packages/{package}/template")
    async def get_configuration_template(package: str):
        root = _package_root(package)
        path = find_template(root)
        if path is None:
            raise HTTPException(404, "This configuration has no schedule template")
        media = "text/csv" if path.suffix.lower() == ".csv" else (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        return Response(
            content=path.read_bytes(), media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
        )

    @app.delete("/api/configuration-packages/{package}/template")
    async def delete_configuration_template(package: str):
        return _delete_package_template(package)

    @app.post("/api/configuration-packages/{package}/rebuild-work-views")
    async def rebuild_configuration_work_views(package: str):
        return _rebuild_package_work_views(package)

    @app.post("/api/configuration-packages/{package}/infer-from-template")
    async def infer_configuration_files(package: str):
        root = _package_root(package)
        template = find_template(root)
        if template is None:
            raise HTTPException(404, "Upload a schedule template before inferring configuration")
        try:
            inferred_package = _next_inferred_package_name()
            inferred = infer_configuration_from_template(
                template, package=inferred_package,
            )
            _apply_configuration_transaction({inferred_package: {
                "replacements": inferred.files,
                "rebuild": True,
            }})
        except HTTPException:
            raise
        except (OSError, ValueError) as error:
            raise HTTPException(422, f"Could not infer configuration: {error}") from error
        payload = _configuration_file_payload(inferred_package)
        payload["source_package"] = package
        payload["inference"] = {
            "courses": inferred.course_count,
            "sections": inferred.section_count,
            "relationships": inferred.relationship_count,
            "rooms": inferred.room_count,
            "time_patterns": inferred.time_pattern_count,
            "persons": inferred.person_count,
        }
        return payload

    @app.post("/api/configuration-packages/{package}/templates/{filename}")
    async def generate_configuration_template(package: str, filename: str):
        return _generate_configuration_template(package, filename)

    @app.delete("/api/configuration-packages/{package}/files/{filename}")
    async def delete_configuration_file(package: str, filename: str):
        return _delete_configuration_file(package, filename)

    @app.delete("/api/configuration-packages/{package}")
    async def delete_configuration_package(package: str):
        _delete_configuration_package(package)
        return {"deleted": package}

    @app.get("/api/schedule")
    async def configuration_schedule(package: str = DEFAULT_PACKAGE):
        config = _load_web_config(package)
        source, schedule = _load_workspace_schedule(package, config)
        logger.info("Loaded %s into %d classes", source, len(schedule))
        return _schedule_payload(schedule, config, source=source)

    @app.post("/api/solve")
    async def solve_schedule(payload: dict):
        schedule, config = _schedule_from_payload(payload)
        source = f"{config.package_id} current workspace"
        regenerate = bool(payload.get("regenerate", False))
        rss_before = _rss_mb()
        try:
            solve_result = solver_module.solve_detailed(
                schedule, config, time_limit_seconds=SOLVE_TIME_LIMIT_SECONDS,
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
                source, error, rss_before, _rss_mb(),
            )
            raise HTTPException(504, str(error)) from error
        except solver_module.NoFeasibleSchedule as error:
            # 422, not 400: the request itself was well-formed -- there's
            # just no conflict-free assignment to offer for this input
            # (see InfeasibleSchedule). app.js keys off this
            # status to keep "Solve Schedule" disabled until a new file
            # is chosen, instead of inviting a retry that can't succeed.
            logger.warning(
                "Could not solve %r: %s (RSS %.1f -> %.1f MB)",
                source, error, rss_before, _rss_mb(),
            )
            raise HTTPException(422, str(error)) from error
        changes = solver_module.diff_schedules(schedule, solved)
        violations = _analysis_payload(solved, config)
        logger.info(
            "Solved %r cleanly (%d classes, %d field change(s), RSS %.1f -> %.1f MB)",
            source, len(solved), len(changes), rss_before, _rss_mb(),
        )
        return {
            "count": len(solved),
            "source_name": source,
            "config_version": config.version,
            "package_id": config.package_id,
            "assignment_options": _assignment_options(config),
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
        }

    @app.post("/api/analyze")
    async def analyze_current_schedule(payload: dict):
        schedule, config = _schedule_from_payload(payload)
        return _analysis_payload(schedule, config)

    @app.post("/api/export/{view}")
    async def export_current_schedule(view: str, payload: dict):
        schedule, config = _schedule_from_payload(payload)
        methods = {
            "schedule": "to_raw_excel",
            "instructor": "to_instructor_excel",
            "location": "to_room_excel",
        }
        method = methods.get(view)
        if method is None:
            raise HTTPException(404, f"Unknown export view: {view}")
        content = _excel_bytes(schedule, method)
        filename = f"{config.package_id}_current_{view}.xlsx"
        return Response(
            content=content,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/api/save")
    async def save_schedule_version(payload: dict):
        """Publish browser edits through the same atomic verN publisher as solve."""
        term = str(payload.get("term", "")).strip()
        if not PACKAGE_ID.fullmatch(term):
            raise HTTPException(
                400, "A valid configuration/output name is required, for example 27S",
            )
        records = payload.get("records")
        baseline_records = payload.get("baseline_records")
        if not isinstance(records, list) or not isinstance(baseline_records, list):
            raise HTTPException(400, "Current and baseline schedule records are required")
        package = str(payload.get("package", DEFAULT_PACKAGE)).strip()
        if term != package:
            raise HTTPException(
                400, "The output term must match the selected configuration package"
            )
        config = _load_web_config(package)
        try:
            relationships = tuple(config.courses.relationships) if config.courses else ()
            catalogs = tuple(config.catalogs.courses) if config.catalogs else ()
            schedule = Schedule.from_records(
                records, persons=config.persons, relationships=relationships,
                catalogs=catalogs,
            )
            baseline = Schedule.from_records(
                baseline_records, persons=config.persons, relationships=relationships,
                catalogs=catalogs,
            )
        except (GroupingError, ValueError) as error:
            raise HTTPException(400, str(error)) from error
        evaluation = evaluate_schedule(
            schedule, config.preferences, config.persons, config.global_rules,
            config.meeting_patterns, config.constraint_rules,
            config.workload_policy, config.back_to_back_policy,
        )
        # Hard violations never block publication (see docs/codes.md) -- they
        # are recorded in the report/manifest and returned below instead, so
        # a version can always be saved and inspected, never refused.
        output_root = Path("out")
        version = next_version(output_root / term)
        destination = output_root / term / version
        baseline_bytes = baseline.to_dataframe().to_csv(index=False).encode("utf-8")
        no_overrides = b"# Browser manual schedule publication; no override file applied.\n"
        reconciliation = b"# Browser publication used the imported schedule as its baseline.\n"
        created_at = datetime.now(UTC).isoformat()
        report = (
            f"# {term} {version} manual schedule report\n\n"
            f"Published from the schedule workbench at {created_at}.\n\n"
            f"- Atomic classes: {len(schedule)}\n"
            f"- Rows: {len(schedule.to_records())}\n"
            f"- Hard violations: {len(evaluation.hard_violations)}\n"
            f"- Soft penalty: {evaluation.soft_penalty:g}\n"
            f"- Soft findings: {len(evaluation.soft_findings)}\n"
        )
        manifest = {
            "schema_version": 4,
            "term": term,
            "version": version,
            "parent": None,
            "created_at": created_at,
            "input": {
                "path": f"work/{package}/initial/initial.csv",
                "sha256": hashlib.sha256(baseline_bytes).hexdigest(),
            },
            "initial_baseline": {
                "path": f"work/{package}/initial/initial.csv",
                "sha256": hashlib.sha256(baseline_bytes).hexdigest(),
                "snapshot": "baseline.csv", "role": "initial",
            },
            "configuration": {
                "package_id": config.package_id,
                "version": config.version,
                "files": [{"path": name, "sha256": sha256(Path(name))} for name in config.source_paths],
            },
            "reconciliation": {
                "source": "configuration-workspace",
                "sha256": hashlib.sha256(reconciliation).hexdigest(),
                "snapshot": "reconciliation.toml",
            },
            "applied_overrides_sha256": hashlib.sha256(no_overrides).hexdigest(),
            "override_workspace": {"path": "overrides.toml", "mutable": True, "source_version": version},
            "selected_attempt": 1,
            "solver": {
                "status": "manual", "objective": None, "best_bound": None,
                "random_seed": None, "time_limit_seconds": 0,
                "search_workers": 0, "attempts": 1,
                "attempts_requested": 1, "attempts_run": 1,
            },
            "validation": {
                "hard_violations": len(evaluation.hard_violations),
                "soft_penalty": evaluation.soft_penalty,
                "worst_overload": None,
            },
        }
        paths = publish_version(
            term=term, version=version, destination=destination,
            schedule=schedule, baseline=baseline, baseline_bytes=baseline_bytes,
            attempts_rows=[{
                "Attempt": 1, "Status": "manual", "Objective": None,
                "BestBound": None, "SolveSeconds": 0, "CandidateCount": None,
                "SearchWorkers": 0, "SoftPenalty": evaluation.soft_penalty,
                "SoftFindings": len(evaluation.soft_findings),
                "HardViolations": len(evaluation.hard_violations),
                "WorstOverload": None, "Error": None,
            }],
            report=report, manifest=manifest, applied_overrides=no_overrides,
            reconciliation=reconciliation,
        )
        logger.info(
            "Published browser schedule as %s/%s (%d hard violation(s))",
            term, version, len(evaluation.hard_violations),
        )
        return {
            "term": term, "version": version,
            "output_dir": str(paths.output_dir),
            "schedule_path": str(paths.schedule_path),
            "hard_violations": [_serialize_hard(v) for v in evaluation.hard_violations],
        }

    app.mount("/", _NoCacheStaticFiles(directory=PACKAGE_WEB, html=True), name="web")
    return app


def _package_root(package: str) -> Path:
    clean_package = package.strip()
    if not PACKAGE_ID.fullmatch(clean_package):
        raise HTTPException(400, f"Invalid configuration package name: {clean_package!r}")
    root = CONFIG_DIR / clean_package
    if not root.is_dir():
        raise HTTPException(404, f"Unknown configuration package: {clean_package}")
    return root


def _next_inferred_package_name() -> str:
    """Return the first unused system-generated ``推断(N)`` package name."""
    used = {
        int(match.group(1))
        for path in CONFIG_DIR.iterdir()
        if path.is_dir() and (match := re.fullmatch(r"推断\(([1-9]\d*)\)", path.name))
    }
    rank = 1
    while rank in used:
        rank += 1
    return f"推断({rank})"


def _infer_uploaded_template(
    filename: str,
    content: bytes,
    *,
    package: str,
):
    """Materialize one upload briefly and return its seven inferred TOMLs."""
    suffix = Path(filename).suffix.lower()
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / f"template{suffix}"
        source.write_bytes(content)
        return infer_configuration_from_template(source, package=package)


def _missing_inferred_files(
    package: str,
    inferred_files: dict[str, bytes],
    incoming: dict[str, bytes],
) -> dict[str, bytes]:
    """Select only TOMLs absent from both disk and the current upload."""
    package_root = CONFIG_DIR / package
    return {
        filename: content
        for filename, content in inferred_files.items()
        if filename not in incoming
        and not (package_root / CONFIG_FILES[filename]).is_file()
    }


def _configuration_target(package: str, filename: str) -> tuple[Path, Path]:
    clean_package = package.strip()
    if filename not in CONFIG_FILES or Path(filename).name != filename:
        raise HTTPException(400, f"Unknown configuration filename: {filename}")
    package_root = _package_root(clean_package)
    relative = CONFIG_FILES[filename]
    target = (package_root / relative).resolve()
    root = package_root.resolve()
    if root not in target.parents:
        raise HTTPException(400, "Invalid configuration path")
    return target, relative


def _configuration_file_payload(package: str) -> dict:
    summary = _configuration_summary(package)
    files = []
    for filename, relative in CONFIG_FILES.items():
        target, _ = _configuration_target(package, filename)
        files.append({
            "name": filename,
            "path": relative.as_posix(),
            "present": target.is_file(),
            "updated_at": (
                datetime.fromtimestamp(target.stat().st_mtime, UTC).isoformat()
                if target.is_file() else None
            ),
            "content": target.read_text(encoding="utf-8") if target.is_file() else "",
            "template_available": filename in {"courses.toml", "preferences.toml", "constraints.toml"},
        })
    return {
        **summary, "package_id": package, "files": files,
        "template": template_summary(_package_root(package), WORK_ROOT),
    }


def _working_view_ready(package: str) -> bool:
    """Return whether a package owns a complete, provenance-verified work view."""
    try:
        _verified_initial(WORK_ROOT / package / "initial" / "initial.csv")
    except (FileNotFoundError, OSError, ValueError):
        return False
    return True


def _configuration_summary(package: str) -> dict:
    root = CONFIG_DIR / package
    if not root.is_dir():
        raise HTTPException(404, f"Unknown configuration package: {package}")
    missing = [
        filename for filename, relative in CONFIG_FILES.items()
        if not (root / relative).is_file()
    ]
    errors: list[str] = []
    for filename, relative in CONFIG_FILES.items():
        path = root / relative
        if not path.is_file():
            continue
        try:
            tomllib.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
            errors.append(f"{filename}: {error}")
    version = ""
    if not missing and not errors:
        try:
            version = solver_module.SolverConfig.load(CONFIG_DIR, package=package).version
        except (FileNotFoundError, ValueError) as error:
            errors.append(str(error))
    status = "invalid" if errors else "draft" if missing else "ready"
    return {
        "id": package,
        "display_name": package,
        "status": status,
        "missing": missing,
        "errors": errors,
        "config_version": version,
        "working_view_ready": status == "ready" and _working_view_ready(package),
    }


def _replace_configuration_file(package: str, filename: str, content: bytes) -> dict:
    return _replace_configuration_files(package, {filename: content})


def _apply_configuration_transaction(changes: dict[str, dict]) -> None:
    """Validate and rebuild staged packages before committing any upload."""
    if not changes:
        return
    for package in changes:
        if not PACKAGE_ID.fullmatch(package):
            raise HTTPException(400, f"Invalid configuration package name: {package!r}")

    CONFIG_DIR.parent.mkdir(parents=True, exist_ok=True)
    with _CONFIG_WRITE_LOCK, tempfile.TemporaryDirectory(
        dir=CONFIG_DIR.parent, prefix=".configuration-transaction-",
    ) as folder:
        transaction = Path(folder)
        staged_config = transaction / "config"
        staged_work = transaction / "work"
        staged_config.mkdir()
        staged_work.mkdir()

        try:
            for package, change in changes.items():
                source = CONFIG_DIR / package
                staged_package = staged_config / package
                if source.is_dir():
                    shutil.copytree(source, staged_package)
                else:
                    if (
                        change.get("template") is not None
                        and not change.get("replacements")
                    ):
                        raise HTTPException(
                            404, f"Unknown configuration package: {package}",
                        )
                    staged_package.mkdir(parents=True)

                for filename, content in change.get("replacements", {}).items():
                    if filename not in CONFIG_FILES:
                        continue
                    target = staged_package / CONFIG_FILES[filename]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)

                template = change.get("template")
                if template is not None:
                    for old_table in staged_package.rglob("*"):
                        if (
                            old_table.is_file()
                            and old_table.suffix.lower() in TEMPLATE_SUFFIXES
                        ):
                            old_table.unlink()
                    install_template(staged_package, *template)

                complete = all(
                    (staged_package / relative).is_file()
                    for relative in CONFIG_FILES.values()
                )
                if complete:
                    solver_module.SolverConfig.load(staged_config, package=package)
                if change.get("rebuild"):
                    rebuild_work_views(
                        staged_package,
                        config_root=staged_config,
                        work_root=staged_work,
                    )
        except HTTPException:
            raise
        except (OSError, UnicodeError, ValueError) as error:
            logger.warning("Configuration transaction validation failed: %s", error)
            raise HTTPException(
                422, f"Upload rejected; working views could not be rebuilt: {error}",
            ) from error

        swaps: list[tuple[Path, Path | None]] = []
        incoming_paths: list[Path] = []
        try:
            for package in changes:
                staged_package = staged_config / package
                destination = CONFIG_DIR / package
                incoming = CONFIG_DIR / f".{package}.incoming-{uuid.uuid4().hex}"
                shutil.copytree(staged_package, incoming)
                incoming_paths.append(incoming)
                backup = None
                if destination.exists():
                    backup = CONFIG_DIR / f".{package}.backup-{uuid.uuid4().hex}"
                    destination.replace(backup)
                swaps.append((destination, backup))
                incoming.replace(destination)
                incoming_paths.remove(incoming)

                staged_initial = staged_work / package / "initial"
                if staged_initial.is_dir():
                    destination_initial = WORK_ROOT / package / "initial"
                    destination_initial.parent.mkdir(parents=True, exist_ok=True)
                    work_incoming = destination_initial.parent / (
                        f".initial.incoming-{uuid.uuid4().hex}"
                    )
                    shutil.copytree(staged_initial, work_incoming)
                    incoming_paths.append(work_incoming)
                    work_backup = None
                    if destination_initial.exists():
                        work_backup = destination_initial.parent / (
                            f".initial.backup-{uuid.uuid4().hex}"
                        )
                        destination_initial.replace(work_backup)
                    swaps.append((destination_initial, work_backup))
                    work_incoming.replace(destination_initial)
                    incoming_paths.remove(work_incoming)
        except OSError as error:
            for incoming in incoming_paths:
                if incoming.exists():
                    shutil.rmtree(incoming)
            for destination, backup in reversed(swaps):
                if destination.exists():
                    shutil.rmtree(destination)
                if backup is not None and backup.exists():
                    backup.replace(destination)
            raise HTTPException(500, f"Could not commit configuration: {error}") from error
        else:
            for _, backup in swaps:
                if backup is not None and backup.exists():
                    shutil.rmtree(backup)


def _replace_configuration_files(
    package: str, replacements: dict[str, bytes],
) -> dict:
    targets: dict[str, tuple[Path, Path]] = {}
    for filename, content in replacements.items():
        target, relative = _configuration_target(package, filename)
        if not content:
            raise HTTPException(400, f"{filename} is empty")
        if len(content) > MAX_CONFIG_BYTES:
            raise HTTPException(413, f"{filename} exceeds 2 MB")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise HTTPException(400, f"{filename} must use UTF-8") from error
        targets[filename] = (target, relative)

    _apply_configuration_transaction({package: {
        "replacements": replacements,
        "rebuild": True,
    }})

    logger.info(
        "Updated configuration %s: %s", package,
        ", ".join(targets[name][1].as_posix() for name in replacements),
    )
    return _configuration_file_payload(package)


def _package_name_from_comments(replacements: dict[str, bytes]) -> str:
    names: set[str] = set()
    for filename, content in replacements.items():
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise HTTPException(400, f"{filename} must use UTF-8") from error
        header = "\n".join(text.splitlines()[:8])
        match = PACKAGE_COMMENT.search(header)
        if match:
            names.add(match.group(1))
        try:
            tomllib.loads(text)
        except tomllib.TOMLDecodeError as error:
            raise HTTPException(400, f"{filename} has invalid TOML: {error}") from error
    if not names:
        raise HTTPException(
            400, "Add '# Configuration package: NAME' near the start of the files",
        )
    if len(names) != 1:
        raise HTTPException(400, "Configuration package comments do not agree")
    name = names.pop()
    if not PACKAGE_ID.fullmatch(name):
        raise HTTPException(400, f"Invalid configuration package name: {name!r}")
    return name


def _upsert_configuration_package(
    replacements: dict[str, bytes], *, rebuild: bool = True,
) -> dict:
    if not replacements:
        raise HTTPException(400, "No recognized configuration files were provided")
    package = _package_name_from_comments(replacements)
    for filename, content in replacements.items():
        if not content:
            raise HTTPException(400, f"{filename} is empty")
        if len(content) > MAX_CONFIG_BYTES:
            raise HTTPException(413, f"{filename} exceeds 2 MB")
    _apply_configuration_transaction({package: {
        "replacements": replacements,
        "rebuild": rebuild,
    }})
    logger.info("Updated configuration package %s", package)
    return _configuration_file_payload(package)


def _configuration_template(package: str, filename: str) -> bytes:
    if filename not in {"courses.toml", "preferences.toml", "constraints.toml"}:
        raise HTTPException(400, f"No minimal template is available for {filename}")
    title = {
        "courses.toml": "# Add [[courses]] offerings and [[relationships]] here.\n",
        "preferences.toml": "staff_count_weight = 10\nstaff_credit_weight = 5\n",
        "constraints.toml": "# Default workload and dynamic-position policies apply.\n",
    }[filename]
    return (
        f"# Configuration package: {package}\n"
        "# Generated minimal template\n\n"
        f"{title}"
    ).encode("utf-8")


def _generate_configuration_template(package: str, filename: str) -> dict:
    target, _ = _configuration_target(package, filename)
    if target.exists():
        raise HTTPException(409, f"{filename} already exists")
    return _upsert_configuration_package({filename: _configuration_template(package, filename)})


def _trash_destination(package: str, filename: str | None = None) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"-{filename}" if filename else ""
    return CONFIG_TRASH / f"{package}-{stamp}-{uuid.uuid4().hex[:8]}{suffix}"


def _delete_configuration_file(package: str, filename: str) -> dict:
    target, relative = _configuration_target(package, filename)
    if not target.is_file():
        raise HTTPException(404, f"{filename} does not exist in {package}")
    trash = _trash_destination(package, filename)
    trash.parent.mkdir(parents=True, exist_ok=True)
    trash.mkdir()
    shutil.move(str(target), str(trash / filename))
    logger.info("Moved configuration file %s/%s to %s", package, relative, trash)
    return _configuration_file_payload(package)


def _delete_configuration_package(package: str) -> None:
    if not PACKAGE_ID.fullmatch(package):
        raise HTTPException(400, f"Invalid configuration package name: {package!r}")
    source = CONFIG_DIR / package
    if not source.is_dir():
        raise HTTPException(404, f"Unknown configuration package: {package}")
    trash = _trash_destination(package)
    trash.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(trash))
    logger.info("Moved configuration package %s to %s", package, trash)


def _rebuild_package_work_views(package: str) -> dict:
    root = _package_root(package)
    try:
        return rebuild_work_views(root, config_root=CONFIG_DIR, work_root=WORK_ROOT)
    except (OSError, ValueError) as error:
        logger.warning("Could not rebuild work views for %s: %s", package, error)
        raise HTTPException(422, f"Could not rebuild work views: {error}") from error


def _delete_package_template(package: str) -> dict:
    root = _package_root(package)
    template = find_template(root)
    if template is None:
        raise HTTPException(404, "This configuration has no schedule template")
    trash = _trash_destination(package, template.name)
    trash.parent.mkdir(parents=True, exist_ok=True)
    trash.mkdir()
    shutil.move(str(template), str(trash / template.name))
    template.parent.rmdir()
    logger.info("Moved schedule template %s/%s to %s", package, template.name, trash)
    return _configuration_file_payload(package)


def _excel_bytes(schedule: Schedule, method_name: str) -> bytes:
    """Build one shared Schedule Excel view without persistent server state."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "export.xlsx"
        getattr(schedule, method_name)(path)
        return path.read_bytes()


def _schedule_from_payload(
    payload: dict,
) -> tuple[Schedule, solver_module.SolverConfig]:
    package = str(payload.get("package", DEFAULT_PACKAGE)).strip()
    records = payload.get("records")
    if not isinstance(records, list):
        raise HTTPException(400, "Current schedule records are required")
    config = _load_web_config(package)
    try:
        schedule = Schedule.from_records(
            records,
            persons=config.persons,
            relationships=tuple(config.courses.relationships) if config.courses else (),
            catalogs=tuple(config.catalogs.courses) if config.catalogs else (),
        )
    except (GroupingError, ValueError) as error:
        raise HTTPException(400, str(error)) from error
    return schedule, config


def _load_workspace_schedule(
    package: str, config: solver_module.SolverConfig,
) -> tuple[str, Schedule]:
    """Load the verified initial working view owned by a Ready package."""
    initial = WORK_ROOT / package / "initial" / "initial.csv"
    try:
        _verified_initial(initial)
        schedule = read_schedule(
            initial,
            persons=config.persons,
            relationships=tuple(config.courses.relationships) if config.courses else (),
            catalogs=tuple(config.catalogs.courses) if config.catalogs else (),
        )
    except (FileNotFoundError, GroupingError, ValueError) as error:
        raise HTTPException(
            409,
            f"Configuration {package!r} has no valid working schedule; "
            f"rebuild its working views: {error}",
        ) from error
    return initial.name, schedule


def _schedule_payload(
    schedule: Schedule,
    config: solver_module.SolverConfig,
    *,
    source: str,
) -> dict:
    return {
        "count": len(schedule),
        "source_name": source,
        "config_version": config.version,
        "package_id": config.package_id,
        "assignment_options": _assignment_options(config),
        "classes": _serialize_schedule(schedule),
        "violations": _analysis_payload(schedule, config),
    }


def _assignment_options(config: solver_module.SolverConfig) -> dict:
    """Configured resources offered by the browser's assignment menu."""
    return {
        "instructors": sorted(config.persons),
        "contract_loads": {
            name: person.max_load for name, person in sorted(config.persons.items())
        },
        "new_instructor_contract_load": config.new_instructor_policy.contract_load,
        "new_professor_contract_load": config.new_professor_policy.contract_load,
        "workload_policy": {
            "overload_tolerance": config.workload_policy.overload_tolerance,
            "hard_load_cap_tolerance": config.workload_policy.hard_load_cap_tolerance,
        },
        "rooms": [
            {"building": room.building, "room": room.room}
            for room in config.rooms
        ],
        "meeting_patterns": [
            {
                "days": pattern.days,
                "duration": pattern.duration_minutes,
                "roles": sorted(pattern.roles),
            }
            for pattern in config.meeting_patterns
        ],
    }


class _NoCacheStaticFiles(StaticFiles):
    """Static files with no browser caching.

    The frontend and API are deployed together, so caching an older
    ``app.js`` can make it incompatible with the current response shape.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store"
        return response


def _serialize_schedule(schedule: Schedule) -> list[dict]:
    return [
        {
            "kind": type(item).__name__,
            "course_ids": list(item.course_ids),
            "credit_hours": item.credit_hours,
            "sections": [_serialize_record(r) for r in item.to_records()],
            # CrossListingClass only -- see docs/codes.md. Lets the web UI
            # decide whether editing instructor/room/time on one row should
            # propagate to the other, instead of guessing from whatever the
            # two rows' current values happen to be.
            "synced_fields": (
                sorted(item.synced_fields)
                if hasattr(item, "synced_fields") else None
            ),
        }
        for item in schedule
    ]


def _analysis_payload(
    schedule: Schedule, config: solver_module.SolverConfig,
) -> dict:
    """Serialize the same deterministic evaluation used by CLI publication."""
    evaluation = evaluate_schedule(
        schedule, config.preferences, config.persons, config.global_rules,
        config.meeting_patterns,
        config.constraint_rules,
        config.workload_policy, config.back_to_back_policy,
    )
    loads = [
        {
            "name": row.name, "hours": row.hours, "target": row.target,
            "delta": row.delta, "state": row.state, "position": row.position,
        }
        for row in summarize_instructor_loads(
            evaluation.loads, config.persons,
            new_instructor_target=config.new_instructor_policy.contract_load,
            new_professor_target=config.new_professor_policy.contract_load,
            overload_tolerance=config.workload_policy.overload_tolerance,
        )
    ]
    records = schedule.to_records()
    locations = {
        (str(row.get("Building") or ""), str(row.get("Room") or ""))
        for row in records if row.get("Room")
    }
    return {
        "atomic_classes": evaluation.atomic_classes,
        "row_count": evaluation.row_count,
        "instructor_count": len({row["name"] for row in loads if row["hours"]}),
        "location_count": len(locations),
        "instructor_loads": loads,
        "hard": [_serialize_hard(v) for v in evaluation.hard_violations],
        "soft_total": evaluation.soft_penalty,
        "soft": [_serialize_soft(f) for f in evaluation.soft_findings],
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
