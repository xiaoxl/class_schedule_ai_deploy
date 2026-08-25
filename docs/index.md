# Class Schedule System

This project cleans CSV/XLSX schedule data, groups rows into atomic classes, applies term changes and preferences, solves with OR-Tools CP-SAT, and publishes auditable versions under `out/<term>/verN/`.

## Start the web interface

Open PowerShell in the project directory:

```powershell
cd "D:\Codes\Projects\Projects 26\class_schedule_ai_deploy"
uv run uvicorn class_schedule.webapp:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Press `Ctrl+C` to stop the server.

## Use the web interface

1. Import a starting schedule in CSV or XLSX format.
2. Switch between Instructor, Room, and Course views.
3. Drag a class to change its meeting time. Moving between weekday columns can change supported MWF/TR patterns.
4. Right-click a class to assign an instructor or room. Choose **New** to create another New Instructor identity.
5. Review workloads and findings. Finding links open the relevant Instructor or Room view.
6. Enter a term such as `27S`, resolve hard conflicts, and select **Save New Version**.

Browser saves use the same version publisher as solver output and are written to `out/27S/verN/`.

## Command-line workflow

```powershell
uv run class-schedule --config config initialize 27S inputs/27S/source.xlsx
uv run class-schedule --config config initial 27S
uv run class-schedule --config config solve 27S
uv run class-schedule --config config final 27S ver10
```

`initialize` cleans the source and creates pre-change views. `initial` applies term changes. Every `solve` starts from the same initial schedule and creates an immutable version. `final` applies manual overrides to a selected version.

## Documentation

- [Data cleaning](data-cleaning.md)
- [Configuration](configuration.md)
- [Scheduling rules](scheduling-rules.md)
- [Manual adjustments and versioning](manual-adjustments.md)
- [Demand analysis](demand-analysis.md)

## Tests

```powershell
uv run python -m unittest discover -s tests -v
```
