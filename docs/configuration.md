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
belong to only one declared relationship.

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
overload_tolerance = 2
hard_load_cap_tolerance = 6
far_overload_threshold = 4

[workload.penalties]
underload_per_credit = 30
permissive_overload_per_credit = 10
strict_overload_per_credit = 100
far_overload_extra = 50

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

`catalogs.toml` is the package credit authority. A missing catalog course,
invalid input credit, or input/catalog disagreement is an error. A catalog
entry may omit `credits`, in which case the last course-number digit is its
resolved credit value everywhere, including the solver and reports.

All course selectors are cross-validated. Instructor qualifications must reference catalog courses; preference and constraint sections must be offered; timeslot selectors must reference real courses. Package loading also verifies that every declared relationship has applicable meeting-pattern roles before the solver runs.

`courses.toml` is the sole desired-offering source. The starting file contributes reusable instructor, time, and room assignments only. `initial` generates `reconciliation.toml`; there is no hand-written cancellation/addition file.

The package name is also the normal work/output namespace. CLI commands reject a different positional term, and the Web output field is read-only and follows the selected package.
