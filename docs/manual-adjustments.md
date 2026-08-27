# Manual Adjustments and Versioning

## Web adjustments

Start the interface from [the documentation home](index.md). Import a starting CSV/XLSX schedule, drag meetings, or use the right-click assignment menu. Changes remain temporary until **Save New Version** is selected.

Saving uses the same atomic publisher as solver output. As long as the schedule can be built at all, saving always succeeds -- hard conflicts never block it, they are simply recorded in the version's report and manifest for review. Output goes to `out/<package>/verN/` with schedule, baseline, generated reconciliation audit, cumulative schedule diff, reports, and manifest.

## TOML overrides

For CLI final publication, edit the version-specific `overrides.toml` rather than a published CSV. Edits can change instructor, time slot, building, or room; locks prevent the solver from moving those fields again.

```toml
term = "27S"
source_version = "ver10"

[[edits]]
course_id = "MATH 1113-F01"
instructor = "Instructor, Example"
time_slot = "TR 09:30"
building = "Corley"
room = "269"

[[locks]]
course_id = "MATH 1113-F01"
fields = ["instructor", "time", "building", "room"]
```

Use `record = 0` or `record = 1` only for a row-specific edit in a two-row atomic class. Unassignment uses `new_instructor`; legacy `Staff` is input-compatible but never newly exported.

`initial` is the stable post-change baseline. Every `verN` is immutable and independently solved. `final` is a refreshable release derived from one version and its overrides.
