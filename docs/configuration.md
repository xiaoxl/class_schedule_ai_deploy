# Configuration

Configuration is distributed as self-contained packages directly below `config/`. A package is identified only by its directory name. There is no `profile.toml`, default profile, inheritance, or term subdirectory.

## Package layout

Every valid package contains these seven required TOML files:

```text
config/
  27S/
    basicinfo/
      catalogs.toml
      locations.toml
      timeslot.toml
      persons.toml
    courses.toml
    preferences.toml
    constraints.toml
```

The four-line header in the included package is a human-readable comment only:

```toml
# Configuration package: 27S
# Term: Spring 2027
# Department: MAPS
# Program: Mathematics
```

The parser ignores these comments. The package ID and Web label always come from the directory name, so missing or stale comments never affect execution.

To create another package, copy the whole directory and edit the copy:

```text
config/27S/ -> config/27F/
```

Packages are isolated and never inherit files from one another. A directory missing any of the seven files is not shown in the Web selector and cannot be loaded by the CLI.

## Selecting a package

```powershell
uv run class-schedule solve 27S
```

The CLI configuration root is always `config/`; the positional configuration name selects the directory below that root. The Web interface discovers packages automatically. Changing Configuration reparses the imported file with the selected package.

Published manifests record the package ID, the hash of all seven files, and every resolved path. Final publication inherits its source version's package and rejects a mismatch.

For deployment with configuration outside the repository, mount the package root and set:

```text
CLASS_SCHEDULE_CONFIG_ROOT=/run/secrets/class-schedule-config
CLASS_SCHEDULE_CONFIG_PACKAGE=27S
```

`work/` (rebuilt working views, config-trash) and `output/` (published
versions, logs) are real generated state too -- not safe to lose on a
redeploy -- and move the same way:

```text
CLASS_SCHEDULE_WORK_ROOT=/var/data/work
CLASS_SCHEDULE_OUTPUT_ROOT=/var/data/output
```

All three default to repo-relative paths (`config/`, `work/`, `output/`) when
unset, which is fine for local development but not for a host with an
ephemeral filesystem (see `render.yaml`, which points all three at one
mounted Disk). `CONFIG_DIR` may not contain any complete package yet on a
fresh mount -- the Web app boots regardless and the Configuration workspace's
upload/infer-from-template flow creates the first one.

## File responsibilities

- `basicinfo/catalogs.toml` defines subject, number, title, and credits.
- `basicinfo/locations.toml` defines available buildings and rooms.
- `basicinfo/timeslot.toml` defines legal days, durations, starts, and atomic-row roles.
- `basicinfo/persons.toml` defines names, aliases, contract loads, and qualifications.
- `courses.toml` declares offered sections and their relationships.
- `preferences.toml` defines weighted instructor and global preferences.
- `constraints.toml` defines hard required or forbidden combinations.

Course numbers and section codes are strings, preserving values such as `0803` and `001`.

## Catalog and offerings

Catalog information is declared once per course:

```toml
[[courses]]
subject = "MATH"
number = "1113"
title = "College Algebra"
credits = 3
```

`credits` is optional. When omitted, the final numeric digit of `number` is
used; an explicit value always wins.

The package-level `courses.toml` lists offered sections:

```toml
[[courses]]
subject = "MATH"
number = "1113"
sections = ["001", "002", "003"]
```

Every offered course must exist in `catalogs.toml`. Relationships refer to complete `SUBJECT NUMBER SECTION` identities:

```toml
[[relationships]]
kind = "coreq"
members = ["MATH 1110 003", "MATH 1113 003"]
```

Relationship IDs are derived internally from `kind` plus sorted canonical
members and are not authored. `coreq` has exactly two members;
`cross_listing` has two or more. `four_credit` and `hybrid` describe multiple
meeting rows within one section and therefore have one member. A section may
belong to only one declared relationship. Declarations may reference sections
that are not offered this term. Only relationships whose members are all
offered participate in scheduling; an inactive relationship never adds its
missing members to the offering list.

Course-level declarations omit the section code and expand against the actual
`courses` offerings:

```toml
[[relationships]]
kind = "four_credit"
members = ["MATH 2924"]

[[relationships]]
kind = "cross_listing"
members = ["MATH 5173", "STAT 4173"]
unsynced = []

[[relationships]]
kind = "coreq"
members = ["MATH 0803", "MATH 1003"]
```

Single-course declarations expand once per offered section. Multi-course
relationships expand only for section codes present in **every** member course.
Missing partners are silently skipped, never reported as an error or added to
the offerings. The same all-members-present rule applies to explicit section
relationships. Members within one declaration must all use the same level.
An active explicit section declaration takes precedence over a course-level
default involving that section. Expanded relationships preserve `unsynced`.

Coreq and CrossListing are never guessed during ordinary loading; their
default/legacy recognition exists only in template inference. Four-credit and
same-section `Fxx`/`Mxx` Hybrid recognition remains intrinsic.

A `cross_listing` relationship declares fields allowed to diverge with
`unsynced`, drawn from `"instructor"`, `"room"`, and `"time"`:

```toml
[[relationships]]
kind = "cross_listing"
members = ["MATH 5173 TC1", "STAT 4173 TC1"]
unsynced = ["time"]
```

This is persisted policy, not a live guess. Omitted `unsynced` and
`unsynced = []` both mean all three fields remain synchronized. Inference
writes the exact mismatching fields it observes. Legacy `synced_fields` input
is temporarily accepted for migration but is never generated.

## People, preferences, and constraints

New Instructor identities are dynamic and need no person record. Their contract, numeric course limit, and back-to-back policy are defined in `constraints.toml`.

Preference rules use course, section, section prefix, room, and time selectors. Positive weights reward matches and negative weights penalize them. Named rules apply to one instructor; unnamed rules are global.

Constraints are hard rules using the same selectors without a weight. Unknown fields and invalid cross-file references are rejected so mistakes cannot silently alter solver behavior.

The same file owns numeric scheduling policy:

```toml
[workload]
ok = [0, 1]
light = [2]
hard_load_cap_tolerance = 6
new_hire_penalty_scale = 0.5

[workload.penalties]
light_penalty = 5
heavy_unit_over = 20
heavy_unit_over_strict = 100
heavy_unit_under = 20

[back_to_back]
penalty = 10

[new_instructor]
allowed_counts = [0, 1, 2]
contract_load = 15
max_course_number_exclusive = 2300
allow_back_to_back = true

[new_professor]
allowed_counts = [0, 1, 2]
contract_load = 12
min_course_number_inclusive = 1914
allow_back_to_back = true
```

`max_load` is a target. Let `d = teaching_load - max_load` in whole credit
hours. Every integer `d` falls in exactly one tier:

- `d` in `ok` — no cost, not reported. `ok` must contain `0`.
- `d` in `light` — a single flat `light_penalty`, charged once, never
  surfaced as a review finding.
- anything else — *heavy*: reported, and costs `heavy_unit_over * |d|` when
  over contract (`heavy_unit_over_strict` for an instructor whose preference
  does not `allow_overload`), or `heavy_unit_under * |d|` when under it.

A load above `max_load + hard_load_cap_tolerance` is hard-infeasible;
`hard_load_cap_tolerance` must be at least the largest `|d|` listed in
`ok`/`light`. `ok`/`light` default to `[0]`/`[]` and every penalty defaults
low, so an unset policy prices any deviation as a mild heavy overload/underload.

`new_hire_penalty_scale` (default `1.0`) multiplies every workload penalty
above — light and heavy, over and under — for a New Instructor / New
Professor identity. Set it below `1.0` to make the solver put unavoidable
under/overload on a new hire before a named instructor. It does not affect
the hard cap or the identity-count policy.

Activation is determined by course assignments in code, not by a configuration
switch. New Instructor and New Professor identities use `contract_load` as the
same workload target once assigned any course: the ok/light/heavy tiers and
the hard cap all apply. Unused candidate identities have no workload cost.
Identity-count and per-credit assignment costs remain separate from workload
penalties.

`catalogs.toml` is the package credit authority. A missing catalog course,
invalid input credit, or input/catalog disagreement is an error. A catalog
entry may omit `credits`, in which case the last course-number digit is its
resolved credit value everywhere, including the solver and reports.

All course selectors are cross-validated. Instructor qualifications must reference catalog courses; preference, constraint, and timeslot selectors may target courses or sections not offered this term, but their course references must exist in the catalog. Package loading also verifies that every active relationship has applicable meeting-pattern roles before the solver runs.

`courses.toml` is the sole desired-offering source. The starting file contributes reusable instructor, time, and room assignments only. `initial` generates `reconciliation.toml`; there is no hand-written cancellation/addition file. Any change to the seven configuration files or the schedule template triggers reconciliation and an atomic rebuild of the CSV, instructor view, room view, and difference audit. Web saves and uploads rebuild immediately. While the server runs, a background scan detects disk edits every two seconds; loading a workspace also checks freshness. Unchanged sources do not cause repeated rebuilds. The difference panel and working schedule use the same rebuilt snapshot. Open browser workspaces refresh automatically when there are no unsaved edits. Invalid or incomplete configuration is reported and leaves the last successful files intact, but those files are not exposed as a current Ready view.

The package name is also the normal work/output namespace. CLI commands reject a different positional term, and the Web output field is read-only and follows the selected package.

### F01 preference matching

Unless a preference explicitly selects F01 through `section` or a matching
`section_prefix`, score F01 only on its physical meeting. Its derived ONLINE
companion does not repeat general course, instructor, or global preference
rewards or penalties. Explicit section selectors retain their existing matching
behavior. This is a code rule shared by the solver and evaluation, not a
configuration switch; the stored hybrid rows and hard constraints are unchanged.

## Lab and lecture/lab relationships

`kind = "lecture_lab"` links a lecture to its lab. It takes one member (a
single offering whose lecture and 50/170-minute labs share a course
number) or two members (a lecture course then its catalog-sibling lab
course, e.g. `["CHEM 3264 1", "CHEM 3260 1"]`). `lab_time_editable = false`
is the default; the lecture's room and time are editable, the lab's rooms
stay fixed even when its time is unlocked. Calendar roles are
`lecture_lab_lecture` (shared-number lecture only) and `lecture_lab_lab`.
A standalone split-room lab (`LabClass`) is recognized structurally and
needs no relationship. See [Lab and lecture/lab classes](lecture-lab.md)
for the complete rules.
