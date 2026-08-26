# Scheduling Rules

## Atomic classes

The solver schedules atomic classes and counts each atomic class once.

- `NormalClass`: one ordinary row.
- `FourCreditClass`: an MWF row paired with Tuesday or Thursday. Valid start times differ by no more than 90 minutes.
- `HybridClass`: a physical meeting plus a derived online companion. Only the physical row appears on the grid.
- `CrossListingClass`: course identities sharing one meeting; the UI merges their course numbers.
- `CoreqClass`: a configured pair whose relationship must survive all adjustments.

Corequisites may both be online, be back-to-back with the same instructor and exact same nonblank room, or use disjoint weekday patterns with starts inside the allowed tolerance.

## Hard constraints

- Every section selects one legal candidate.
- Atomic classes cannot overlap for the same instructor or room.
- Multi-row classes retain their structural relationship.
- Locked fields cannot change.
- Explicit constraints and solver load caps must hold.

## New Instructor

The scalable pool uses `new_instructor`, `new_instructor 2`, and so on. Contract load, course-number eligibility, and back-to-back policy come from `[new_instructor]` in `constraints.toml`; no production policy number is hard-coded in the solver.

## Soft objectives and validation

The objective considers instructor/time/room changes, preferences, back-to-back rules, contract load, and New Instructor use. `schedule_model.evaluate_schedule()` is shared by CLI validation, solver attempts, reports, and the web API. Teaching load always comes from atomic classes through `teaching_loads()`.

A successful solver status is not sufficient by itself. Confirm zero hard violations and review workload and soft findings before saving.
