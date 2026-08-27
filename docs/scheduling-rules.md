# Scheduling Rules

## Atomic classes

The solver schedules atomic classes and counts each atomic class once.

- `NormalClass`: one ordinary row.
- `FourCreditClass`: an MWF row paired with Tuesday or Thursday, same instructor. Construction only requires that pairing; a start-time gap over 90 minutes still constructs, flagged as a `four_credit_time_gap` violation instead of blocking the schedule.
- `HybridClass`: a physical meeting plus a derived online companion. Only the physical row appears on the grid.
- `CrossListingClass`: two rows recognized as one cross-listed offering (a shared Cross-List marker, a known course pair, or an honors/regular section pair). Whichever of instructor/room/time the source data already had matching for a given pair is kept in sync going forward; whichever it didn't is free to diverge independently -- there is no requirement that all three match, and the two rows are never checked against each other for conflicts.
- `CoreqClass`: a configured pair whose course identities and instructor must match; the two meetings must be either both online, back-to-back in the same room, or on disjoint weekdays starting within 30 minutes of each other. Falling short of that adjacency (but not the instructor/pairing requirement) still constructs, flagged as a `coreq_adjacency_gap` violation instead of blocking the schedule.

### Nonfatal atomic-class issues

`FourCreditClass` and `CoreqClass` distinguish a hard structural requirement (same instructor, valid day pairing or course pairing) from a softer scheduling-distance rule (start-time gap, room/adjacency match). Failing only the softer rule still constructs the class -- the problem is recorded on the instance and reported by `evaluate_schedule()` as a hard violation (`four_credit_time_gap` / `coreq_adjacency_gap`), not raised as a construction error. `HybridClass` similarly constructs even when a declared pairing (e.g. from a `courses.toml` relationship) no longer looks like a valid physical/online pair, reporting `hybrid_shape` instead -- but unlike the other two, the solver is never asked to enforce validity on an already-broken hybrid pairing, since a section's online/physical shape isn't something candidate selection can adjust; forcing that would make solving infeasible rather than just imperfect.

## Hard constraints

- Every section selects one legal candidate.
- Atomic classes cannot overlap for the same instructor or room.
- Multi-row classes retain their structural relationship.
- Locked fields cannot change.
- Explicit constraints and solver load caps must hold.

## New Instructor

Two scalable pools grow and shrink with the schedule:

- `new_instructor`, `new_instructor 2`, and so on teach through the configured maximum course number.
- `new_professor`, `new_professor 2`, and so on teach from the configured minimum course number upward.

Contract load, course-number eligibility, and back-to-back policy come from the corresponding `[new_instructor]` and `[new_professor]` sections in `constraints.toml`; no production policy number is hard-coded in the solver.

## Soft objectives and validation

The objective considers instructor/time/room changes, preferences, back-to-back rules, contract load, and New Instructor use. `schedule_model.evaluate_schedule()` is shared by CLI validation, solver attempts, reports, and the web API. Teaching load always comes from atomic classes through `teaching_loads()`.

A successful solver status is not sufficient by itself. Hard violations never block saving or exporting (see "Nonfatal atomic-class issues" below), but review them along with workload and soft findings before treating a version as done.
