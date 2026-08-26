# Class Schedule

An auditable class-scheduling system that reconciles CSV/XLSX templates to a declared course package, builds atomic classes, applies instructor preferences, solves with OR-Tools CP-SAT, and publishes immutable versions.

## Start the web interface

```powershell
cd "D:\Codes\Projects\Projects 26\class_schedule_ai_deploy"
uv run uvicorn class_schedule.webapp:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Select a package, import a starting CSV/XLSX schedule, edit it in Instructor, Room, or Course view, and select **Save New Version**. The package name is also the output namespace, for example `out/27S/verN/`.

The Configuration selector discovers complete packages directly under `config/`. The included package is `config/27S/`; copy that directory to create another independent package. CLI commands take that directory name as their single configuration argument.

See [the documentation home](docs/index.md) for the complete UI workflow.

## Command-line workflow

```powershell
uv run class-schedule import-template 27S inputs/27S/source.xlsx
uv run class-schedule solve 27S
uv run class-schedule final 27S ver10
```

`import-template` validates and normalizes the source, installs it as the package's sole CSV/XLSX template, reconciles it to `courses.toml`, and transactionally rebuilds the working views and `reconciliation.toml` audit. `initial 27S` performs the same rebuild when a template was placed into the configuration directory outside the importer. Missing or multiple table files are rejected. Each `solve` starts from the same initial schedule and creates a new immutable `verN`.

Typical version contents include:

```text
out/27S/ver10/
  schedule.csv
  schedule.xlsx
  schedule_instructor.xlsx
  schedule_room.xlsx
  changes.csv
  baseline.csv
  reconciliation.toml
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
