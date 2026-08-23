"""Unified command-line entry point for the schedule production pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .data_cleaning import clean_file
from .schedule_io import read_schedule
from .schedule_model import evaluate_schedule
from .schedule_run import create_override_template, publish_final, run_term
from .solver import SolverConfig, diff_schedules
from .solver.config import resolve_config_paths
from .starting_template import build_starting_templates, print_starting_result


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


def _draft(args: argparse.Namespace) -> int:
    output = Path(args.output or Path("work") / args.term / "draft")
    output.mkdir(parents=True, exist_ok=True)
    persons_path = resolve_config_paths(args.config, args.term)["persons.toml"]
    results = build_starting_templates(
        args.input, args.changes, persons_path, output_dir=output, seed=args.seed,
    )
    for label, result in results.items():
        print_starting_result(label, result)
    print(f"Wrote {output / 'starting.csv'} and {output / 'starting_noadding.csv'}")
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
        parent=args.parent, baseline_path=args.baseline,
    ))


def _final(args: argparse.Namespace) -> int:
    try:
        bundle = publish_final(
            args.term, args.from_version,
            output_root=args.output_root, config_dir=args.config,
            attempts=args.attempts, time_limit_seconds=args.seconds,
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
    evaluation = evaluate_schedule(
        schedule, config.preferences, config.persons, config.global_rules
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

    clean = commands.add_parser("clean", help="normalize a raw CSV/XLSX export")
    clean.add_argument("term")
    clean.add_argument("input")
    clean.add_argument("--output")
    clean.set_defaults(handler=_clean)

    draft = commands.add_parser("draft", help="roll a cleaned schedule into a term draft")
    draft.add_argument("term")
    draft.add_argument("input")
    draft.add_argument("changes")
    draft.add_argument("--output")
    draft.add_argument("--seed", type=int)
    draft.set_defaults(handler=_draft)

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
    solve.add_argument("--overrides")
    solve.add_argument("--parent")
    solve.add_argument(
        "--baseline",
        help="cumulative changes baseline (default: out/TERM/starting.csv)",
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
