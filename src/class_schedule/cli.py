"""Unified command-line entry point for the schedule production pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .data_cleaning import clean_file, initialize_input, publish_draft
from .initial_builder import build_initial_schedules, print_initial_result
from .schedule_io import read_schedule
from .schedule_model import evaluate_schedule
from .schedule_run import create_override_template, publish_final, run_term
from .solver import SolverConfig, diff_schedules
from .solver.config import resolve_config_paths
from .term_builder import apply_cancellations, load_changes


def _read_schedule(path: str | Path, config: SolverConfig):
    return read_schedule(path, persons=config.persons)


def _clean(args: argparse.Namespace) -> int:
    config = SolverConfig.load(args.config, term=args.term)
    output = Path(args.output or Path("work") / args.term / "normalized")
    result = clean_file(
        args.input, output, persons=config.persons,
    )
    print(f"Wrote {output}: {len(result.normalized)} accepted, {len(result.rejected)} rejected")
    return 1 if len(result.rejected) or result.warnings else 0


def _initialize(args: argparse.Namespace) -> int:
    config = SolverConfig.load(args.config, term=args.term)
    output = Path(args.output or Path("work") / args.term / "normalized")
    result = initialize_input(
        args.input, output, persons=config.persons, draft_path=args.draft_output,
    )
    cleaning = result.cleaning
    print(
        f"Wrote {output}: {len(cleaning.normalized)} accepted, "
        f"{len(cleaning.rejected)} rejected"
    )
    if (
        result.draft_path is None
        or result.instructor_path is None
        or result.room_path is None
    ):
        print("Skipped draft and pre-change Excel views because cleaning was not valid")
        return 1
    print(f"Wrote pre-change draft: {result.draft_path}")
    print(f"Wrote pre-change instructor view: {result.instructor_path}")
    print(f"Wrote pre-change room view: {result.room_path}")
    return 0


def _draft(args: argparse.Namespace) -> int:
    config = SolverConfig.load(args.config, term=args.term)
    schedule = _read_schedule(args.input, config)
    output = Path(args.output or Path("work") / args.term / "draft" / "draft.csv")
    publish_draft(schedule, output)
    print(f"Wrote pre-change draft: {output}")
    return 0


def _initial(args: argparse.Namespace) -> int:
    output = Path(args.output or Path("work") / args.term / "initial")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite initial result: {output}")
    config = SolverConfig.load(args.config, term=args.term)
    persons_path = resolve_config_paths(args.config, args.term)["persons.toml"]
    results = build_initial_schedules(
        args.input, args.changes, persons_path, output_dir=output, seed=args.seed,
        meeting_patterns=config.meeting_patterns,
    )
    for label, result in results.items():
        print_initial_result(label, result)
    print(f"Wrote {output / 'initial.csv'} and {output / 'initial_noadding.csv'}")
    return 0


def _print_bundle(bundle) -> int:
    print(f"Wrote {bundle.output_dir}")
    print(f"Hard violations: {len(bundle.best_attempt.hard_violations)}")
    return 1 if bundle.best_attempt.hard_violations else 0


def _solve(args: argparse.Namespace) -> int:
    return _print_bundle(run_term(
        args.term, input_path=args.input, output_root=args.output_root,
        config_dir=args.config, version=args.version, attempts=args.attempts,
        time_limit_seconds=args.seconds, overrides_path=args.overrides,
        changes_path=args.changes, initial_path=args.initial,
        parent=args.parent, baseline_path=args.baseline,
        historical_backfill=args.historical_backfill,
        search_workers=args.workers,
    ))


def _final(args: argparse.Namespace) -> int:
    try:
        bundle = publish_final(
            args.term, args.from_version,
            output_root=args.output_root, config_dir=args.config,
            attempts=args.attempts, time_limit_seconds=args.seconds,
            search_workers=args.workers,
        )
    except (FileNotFoundError, IndexError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return _print_bundle(bundle)


def _override_template(args: argparse.Namespace) -> int:
    destination = create_override_template(
        args.term, args.from_version, output_path=args.output,
        output_root=args.output_root, config_dir=args.config,
    )
    print(f"Wrote {destination}")
    return 0


def _validate(args: argparse.Namespace) -> int:
    config = SolverConfig.load(args.config, term=args.term)
    schedule = _read_schedule(args.input, config)
    changes_path = (
        Path(args.changes) if args.changes
        else Path("inputs") / args.term / "changes.toml"
    )
    cancelled_course_ids: tuple[str, ...] = ()
    if changes_path.is_file():
        _, cancelled_course_ids, _ = apply_cancellations(
            schedule, load_changes(changes_path).cancel
        )
    elif args.changes:
        raise FileNotFoundError(f"Term changes file does not exist: {changes_path}")
    evaluation = evaluate_schedule(
        schedule, config.preferences, config.persons, config.global_rules,
        config.meeting_patterns, config.constraint_rules,
    )
    print(
        f"Atomic classes: {evaluation.atomic_classes}; "
        f"rows: {evaluation.row_count}"
    )
    print(
        f"Hard violations: {len(evaluation.hard_violations) + len(cancelled_course_ids)}; "
        f"soft penalty: {evaluation.soft_penalty:g}; "
        f"soft findings: {len(evaluation.soft_findings)}"
    )
    for item in evaluation.hard_violations:
        print(f"HARD [{item.rule}] {item.message}")
    for course_id in cancelled_course_ids:
        print(
            f"HARD [cancelled_course] {course_id}: remains present despite "
            f"{changes_path}"
        )
    return 1 if evaluation.hard_violations or cancelled_course_ids else 0


def _diff(args: argparse.Namespace) -> int:
    config = SolverConfig.load(args.config, term=args.term)
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
    parser.add_argument("--config", default="config", help="configuration root")
    commands = parser.add_subparsers(dest="command", required=True)

    initialize = commands.add_parser(
        "initialize",
        help="clean raw data and publish draft plus pre-change Excel views",
    )
    initialize.add_argument("term")
    initialize.add_argument("input")
    initialize.add_argument("--output")
    initialize.add_argument(
        "--draft-output",
        help="canonical pre-change draft (default: work/TERM/draft/draft.csv)",
    )
    initialize.set_defaults(handler=_initialize)

    clean = commands.add_parser("clean", help="normalize a raw CSV/XLSX export")
    clean.add_argument("term")
    clean.add_argument("input")
    clean.add_argument("--output")
    clean.set_defaults(handler=_clean)

    draft = commands.add_parser("draft", help="publish a cleaned Schedule as the pre-change draft")
    draft.add_argument("term")
    draft.add_argument("input")
    draft.add_argument("--output")
    draft.set_defaults(handler=_draft)

    initial = commands.add_parser("initial", help="apply term changes to the draft")
    initial.add_argument("term")
    initial.add_argument("input")
    initial.add_argument("changes")
    initial.add_argument("--output")
    initial.add_argument("--seed", type=int)
    initial.set_defaults(handler=_initial)

    solve = commands.add_parser("solve", help="solve and publish a versioned result bundle")
    solve.add_argument("term")
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
        "--changes",
        help="must match the changes snapshot used to build initial",
    )
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
    final.add_argument("term")
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
    template.add_argument("term")
    template.add_argument("from_version", help="published source version, for example ver10")
    template.add_argument("--output")
    template.add_argument("--output-root", default="out")
    template.set_defaults(handler=_override_template)

    validate = commands.add_parser("validate", help="evaluate a schedule without changing it")
    validate.add_argument("term")
    validate.add_argument("input")
    validate.add_argument(
        "--changes",
        help="term changes file (default: inputs/TERM/changes.toml when present)",
    )
    validate.set_defaults(handler=_validate)

    diff = commands.add_parser("diff", help="compare two schedule files")
    diff.add_argument("term")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.add_argument("--output")
    diff.set_defaults(handler=_diff)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(args.handler(args))


if __name__ == "__main__":
    main()
