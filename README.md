# Class Schedule

An auditable class-scheduling system that cleans CSV/XLSX input, builds atomic classes, applies term changes and instructor preferences, solves with OR-Tools CP-SAT, and publishes immutable versions.

## Start the web interface

```powershell
cd "D:\Codes\Projects\Projects 26\class_schedule_ai_deploy"
uv run uvicorn class_schedule.webapp:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Import a starting CSV/XLSX schedule, edit it in Instructor, Room, or Course view, enter the term, and select **Save New Version**. Output is published to `out/<term>/verN/`.

The Configuration selector discovers complete packages directly under `config/`. The included package is `config/27S/`; copy that directory to create another independent package. The CLI equivalent is `--package <package-name>`.

See [the documentation home](docs/index.md) for the complete UI workflow.

## Command-line workflow

```powershell
uv run class-schedule --config config --package 27S initialize 27S inputs/27S/source.xlsx
uv run class-schedule --config config --package 27S initial 27S work/27S/draft/draft.csv inputs/27S/changes.toml
uv run class-schedule --config config --package 27S solve 27S
uv run class-schedule --config config --package 27S final 27S ver10
```

`initialize` cleans the source and creates pre-change instructor and room views. `initial` applies the complete term changes. Each `solve` independently starts from the same initial schedule and creates a new immutable `verN`. `final` applies manual overrides to a selected version and refreshes a publishable final directory.

Typical version contents include:

```text
out/27S/ver10/
  schedule.csv
  schedule.xlsx
  schedule_instructor.xlsx
  schedule_room.xlsx
  changes.csv
  baseline.csv
  applied_changes.toml
  overrides.toml
  applied_overrides.toml
  report.md
  attempts.csv
  manifest.json
```

## Documentation

- [Architecture, startup, and workflow](docs/index.md)
- [Data cleaning](docs/data-cleaning.md)
- [Configuration](docs/configuration.md)
- [Scheduling rules](docs/scheduling-rules.md)
- [Manual adjustments and versioning](docs/manual-adjustments.md)
- [Demand analysis](docs/demand-analysis.md)
- [Deployment](DEPLOY.md)

## Tests

```powershell
uv run python -m unittest discover -s tests -v
```

The CLI and web interface share the same schedule model, solver, validation, version publisher, and Excel export implementation.
