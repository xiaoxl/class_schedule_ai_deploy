# Class Schedule System

This project reconciles CSV/XLSX schedule templates to `courses.toml`, groups rows into atomic classes, applies preferences, solves with OR-Tools CP-SAT, and publishes auditable versions under `out/<package>/verN/`.

## Start the web interface

Open PowerShell in the project directory:

```powershell
cd "D:\Codes\Projects\Projects 26\class_schedule_ai_deploy"
uv run uvicorn class_schedule.webapp:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Press `Ctrl+C` to stop the server.

## Use the web interface

1. Select a Ready Configuration package. Its current working schedule loads automatically from the package workspace.
2. Switch between Instructor, Room, and Course views.
3. Drag a class to change its meeting time. Moving between weekday columns can change supported MWF/TR patterns.
4. Right-click a class to assign an instructor or room. Choose **New** to create another New Instructor identity.

## Configuration editor

Open the **Configuration** workspace tab to manage the selected package's seven
TOML files. Select a file to edit it in place, then choose **Validate & Save**.
You can also drop individual TOML files or a whole folder onto the upload area.
Only the seven exact configuration filenames are read; unrelated files are
ignored. Each upload is routed by its opening `# Configuration package: NAME`
comment and restored to its required package location (for example,
`locations.toml` is written under `basicinfo/`). Files uploaded later replace
files with the same name in that package; all headers in one drop must agree.

Packages may be assembled incrementally. A package missing files is **Draft**,
a complete package with invalid syntax or cross-file references is **Invalid**,
and only a **Ready** package can load or solve a schedule. Missing term files
(`courses.toml`, `preferences.toml`, and `constraints.toml`) can be created from
minimal templates. Individual files and entire packages can be deleted from the
editor; deleted content is moved to `work/config-trash/` rather than erased.

Each package may also keep one optional schedule template under
`config/<package>/template/`. Its CSV/XLSX filename is unrestricted. A template
drop always replaces the template in the currently managed package; TOMLs in
the same drop still route by their package comments. Updating a template or
`courses.toml` atomically rebuilds `work/<package>/initial/`. Without
`courses.toml`, the template itself produces the working views while the
package remains Draft. Without a template, a complete configuration produces a
deterministic default using configured course order, qualifications, load
limits, dynamic-position eligibility, meeting patterns, and available rooms.
When a template is uploaded, any configuration TOMLs already present are
preserved and only missing files are filled from inference. The template
panel's **从模板推断** action instead creates a new complete package named
`推断(N)` and copies the template into it; all seven TOMLs in that new package
come from inference. It infers
catalog courses and offered sections, marked cross-listings, hybrid and
four-credit relationships, rooms, meeting times, instructors, and the courses
they have taught. It deliberately does not infer corequisites; inferred
instructors allow overload and back-to-back teaching, and hard rules are empty.
5. Review workloads and findings. Finding links open the relevant Instructor or Room view.
6. Review any hard conflicts, then select **Save New Version** -- saving is never blocked by them, but resolving what you can first keeps the published report clean. The output namespace is locked to the selected package.

Browser saves use the same version publisher as solver output and are written to `out/27S/verN/`.
The three download buttons export the browser's current schedule, Instructor
View, and Location View on demand. They work before or after solving and after
manual edits; downloading does not create a new version.

Complete packages live directly under `config/<package-name>/`. The included package is `27S`; copy the entire directory to create another package.

## Command-line workflow

```powershell
uv run class-schedule import-template 27S inputs/27S/source.xlsx
uv run class-schedule solve 27S
uv run class-schedule final 27S ver10
```

`import-template` cleans the source, replaces the selected package's sole template, and rebuilds its working views as one transaction. `initial 27S` performs that same rebuild only when the table was placed in the package outside the importer. The sole CSV/XLSX filename is arbitrary, while zero or multiple table files are errors. Reconciliation makes the template exactly match `courses.toml`: extra sections are removed, missing sections are generated with a qualifying dynamic position, and instructors absent from `persons.toml` are reassigned. The resulting differences are written to `reconciliation.toml`.

## Documentation

- [Data cleaning](data-cleaning.md)
- [Configuration](configuration.md)
- [Scheduling rules](scheduling-rules.md)
- [Manual adjustments and versioning](manual-adjustments.md)
- [Demand analysis](demand-analysis.md)
- [Delivery mode design](codes.md)

## Tests

```powershell
uv run python -m unittest discover -s tests -v
```
