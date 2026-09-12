# Manual Adjustments and Versioning

## Web adjustments

Start the interface from [the documentation home](index.md). Import a starting CSV/XLSX schedule, drag meetings, or use the right-click assignment menu. Changes remain temporary until **Save New Version** is selected.

Saving uses the same atomic publisher as solver output. As long as the schedule can be built at all, saving always succeeds -- hard conflicts never block it, they are simply recorded in the version's report and manifest for review. Output goes to `output/<package>/verN/` with schedule, baseline, generated reconciliation audit, cumulative schedule diff, reports, and manifest.

## Section numbers and Course View

In **Course View**, click the section number after the course number to edit it. Enter or leaving the field submits; Escape cancels. Section codes are strings throughout the model, API, CSV, and Excel export: `001` remains `001`, distinct from `1`.

A section edit updates all rows whose class requires matching section numbers: four-credit, hybrid, corequisite, lecture/lab, split lab, and the recognized same-section cross-listed course pairs. Other cross-listed members can be renumbered independently. Schedule edits reject a duplicate section for the same subject and course number, including collisions introduced through any linked member. Multiple meeting rows of one existing section are allowed. A rejected edit leaves the entire class unchanged.

Click **Course**, **Instructor**, or **Room** in the column header to sort; click the same header again to reverse direction. The default is Course ascending. Sorting moves whole atomic classes, keeping their rows together. The member with the lowest course number supplies the representative course, instructor, and room; subject and section break ties. Sorting never changes the underlying editing indices.

Python callers can use `item.change_section("007", record=0)` to return a new class, or `schedule.change_section("MATH 1113-001", "007")` to update the schedule with duplicate checking. For independent members, `record` identifies the row; required links are always followed.

Renamed rows carry an optional `Source Section` column so subsequent edits and exports can resolve the original configuration relationships. **Save New Version** publishes the changed identifiers; its new configuration package uses the current section numbers in `courses.toml` and keeps relationship settings. The original configuration remains unchanged.

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
