"""Unified command-line entry point for the schedule production pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .data_cleaning import clean_dataframe
from .schedule_io import read_schedule, read_table
from .schedule_model import evaluate_schedule
from .schedule_run import create_override_template, publish_final, run_term
from .solver import SolverConfig, diff_schedules
from .template_workspace import rebuild_work_views, require_unique_template

CONFIG_ROOT = Path("config")


def _read_schedule(path: str | Path, config: SolverConfig):
    return read_schedule(
        path, persons=config.persons,
        relationships=tuple(config.courses.relationships) if config.courses else (),
        catalogs=tuple(config.catalogs.courses) if config.catalogs else (),
    )


def _load_config(args: argparse.Namespace) -> SolverConfig:
    return SolverConfig.load(CONFIG_ROOT, package=args.config_name)


def _import_template(args: argparse.Namespace) -> int:
    config = _load_config(args)
    source = Path(args.input)
    result = clean_dataframe(
        read_table(source), persons=config.persons,
    )
    if len(result.rejected) or result.warnings:
        print(
            f"Rejected template: {len(result.rejected)} invalid rows; "
            f"{len(result.warnings)} grouping warnings",
            file=sys.stderr,
        )
        for warning in result.warnings:
            print(f"ERROR: {warning}", file=sys.stderr)
        if len(result.rejected):
            print(result.rejected.to_string(index=False), file=sys.stderr)
        return 1
    from .webapp import _apply_configuration_transaction
    filename = f"{source.stem}.csv"
    _apply_configuration_transaction({args.config_name: {
        "template": (filename, result.normalized.to_csv(index=False).encode("utf-8")),
        "rebuild": True,
    }})
    print(
        f"Imported {len(result.normalized)} rows as "
        f"config/{args.config_name}/template/{filename}"
    )
    return 0


def _initial(args: argparse.Namespace) -> int:
    package = args.config_name
    package_root = CONFIG_ROOT / package
    if not package_root.is_dir():
        raise FileNotFoundError(f"Unknown configuration package: {package}")
    require_unique_template(package_root)
    SolverConfig.load(CONFIG_ROOT, package=package)
    summary = rebuild_work_views(
        package_root, config_root=CONFIG_ROOT, work_root=Path("work"),
    )
    differences = (summary.get("work_views") or {}).get("differences", {})
    print(f"Removed: {len(differences.get('removed', []))}")
    print(f"Added: {len(differences.get('added', []))}")
    print(f"Reassigned to dynamic positions: {len(differences.get('reassigned', []))}")
    print(f"Rebuilt work/{package}/initial")
    return 0


def _print_bundle(bundle) -> int:
    print(f"Wrote {bundle.output_dir}")
    print(f"Hard violations: {len(bundle.best_attempt.hard_violations)}")
    return 1 if bundle.best_attempt.hard_violations else 0


def _solve(args: argparse.Namespace) -> int:
    return _print_bundle(run_term(
        args.config_name, input_path=args.input, output_root=args.output_root,
        config_dir=CONFIG_ROOT, version=args.version, attempts=args.attempts,
        time_limit_seconds=args.seconds, overrides_path=args.overrides,
        initial_path=args.initial,
        parent=args.parent, baseline_path=args.baseline,
        historical_backfill=args.historical_backfill,
        search_workers=args.workers,
        package=args.config_name,
    ))


def _final(args: argparse.Namespace) -> int:
    try:
        bundle = publish_final(
            args.config_name, args.from_version,
            output_root=args.output_root, config_dir=CONFIG_ROOT,
            attempts=args.attempts, time_limit_seconds=args.seconds,
            search_workers=args.workers,
            package=args.config_name,
        )
    except (FileNotFoundError, IndexError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return _print_bundle(bundle)


def _override_template(args: argparse.Namespace) -> int:
    destination = create_override_template(
        args.config_name, args.from_version, output_path=args.output,
        output_root=args.output_root, config_dir=CONFIG_ROOT,
        package=args.config_name,
    )
    print(f"Wrote {destination}")
    return 0


def _validate(args: argparse.Namespace) -> int:
    config = _load_config(args)
    schedule = _read_schedule(args.input, config)
    evaluation = evaluate_schedule(
        schedule, config.preferences, config.persons, config.global_rules,
        config.meeting_patterns, config.constraint_rules,
        config.workload_policy, config.back_to_back_policy,
    )
    print(
        f"Atomic classes: {evaluation.atomic_classes}; "
        f"rows: {evaluation.row_count}"
    )
    print(
        f"Hard violations: {len(evaluation.hard_violations)}; "
        f"soft penalty: {evaluation.soft_penalty:g}; "
        f"soft findings: {len(evaluation.soft_findings)}"
    )
    for item in evaluation.hard_violations:
        print(f"HARD [{item.rule}] {item.message}")
    return 1 if evaluation.hard_violations else 0


def _diff(args: argparse.Namespace) -> int:
    config = _load_config(args)
    before, after = _read_schedule(args.before, config), _read_schedule(args.after, config)
    changes = list(dict.fromkeys(diff_schedules(before, after)))
    if args.output:
        pd.DataFrame(
            ({"Course ID": c.course_id, "Field": c.field, "Before": c.before, "After": c.after} for c in changes),
            columns=("Course ID", "Field", "Before", "After"),
        ).to_csv(args.output, index=False)
    for change in changes:
        print(f"{change.course_id}: {change.field}: {change.before} -> {change.after}")
    print(f"Changes: {len(changes)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="class-schedule")
    commands = parser.add_subparsers(dest="command", required=True)

    import_template = commands.add_parser(
        "import-template",
        help="clean, validate, and transactionally install a package template",
    )
    import_template.add_argument("config_name", help="configuration package name")
    import_template.add_argument("input", help="source CSV/XLSX")
    import_template.set_defaults(handler=_import_template)

    initial = commands.add_parser(
        "initial", help="reconcile the config package's sole CSV/XLSX template"
    )
    initial.add_argument("config_name", help="configuration package name")
    initial.set_defaults(handler=_initial)

    solve = commands.add_parser("solve", help="solve and publish a versioned result bundle")
    solve.add_argument("config_name")
    solve.add_argument("--input")
    solve.add_argument("--output-root", default="out")
    solve.add_argument(
        "--version",
        help="explicit backfill version; normally omit to append the next verN",
    )
    solve.add_argument("--attempts", type=int, default=5)
    solve.add_argument("--seconds", type=float, default=45.0)
    solve.add_argument(
        "--workers", type=int, default=8,
        help="parallel CP-SAT search workers; use 1 for deterministic search",
    )
    solve.add_argument("--overrides")
    solve.add_argument(
        "--initial",
        help="initial schedule (default: work/TERM/initial/initial.csv)",
    )
    solve.add_argument(
        "--parent",
        help="legacy provenance only; automatic ver rejects parent input",
    )
    solve.add_argument(
        "--baseline",
        help="legacy baseline; accepted only with --historical-backfill",
    )
    solve.add_argument(
        "--historical-backfill", action="store_true",
        help="bypass normal initial provenance checks for legacy reconstruction",
    )
    solve.set_defaults(handler=_solve)

    final = commands.add_parser(
        "final",
        help="apply a verN's embedded overrides and refresh out/TERM/final",
    )
    final.add_argument("config_name")
    final.add_argument("from_version", help="published source version, for example ver10")
    final.add_argument("--output-root", default="out")
    final.add_argument("--attempts", type=int, default=5)
    final.add_argument("--seconds", type=float, default=45.0)
    final.add_argument(
        "--workers", type=int, default=8,
        help="parallel CP-SAT search workers; use 1 for deterministic search",
    )
    final.set_defaults(handler=_final)

    template = commands.add_parser(
        "override-template",
        help="generate a manual-revision TOML template from a published verN",
    )
    template.add_argument("config_name")
    template.add_argument("from_version", help="published source version, for example ver10")
    template.add_argument("--output")
    template.add_argument("--output-root", default="out")
    template.set_defaults(handler=_override_template)

    validate = commands.add_parser("validate", help="evaluate a schedule without changing it")
    validate.add_argument("config_name")
    validate.add_argument("input")
    validate.set_defaults(handler=_validate)

    diff = commands.add_parser("diff", help="compare two schedule files")
    diff.add_argument("config_name")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.add_argument("--output")
    diff.set_defaults(handler=_diff)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        code = args.handler(args)
    except (FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        code = 2
    raise SystemExit(code)


if __name__ == "__main__":
    main()
