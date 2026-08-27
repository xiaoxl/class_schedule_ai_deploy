# Scheduling Rules

## Atomic classes

The solver schedules atomic classes and counts each atomic class once.

- `NormalClass`: one ordinary row.
- `FourCreditClass`: an MWF row paired with Tuesday or Thursday, same instructor, start times no more than 90 minutes apart.
- `HybridClass`: a physical meeting plus a derived online companion, same instructor. Only the physical row appears on the grid.
- `CrossListingClass`: two rows recognized as one cross-listed offering (a shared Cross-List marker, a known course pair, or an honors/regular section pair). Whichever of instructor/room/time the source data already had matching for a given pair is kept in sync going forward; whichever it didn't is free to diverge independently -- there is no requirement that all three match, and the two rows are never checked against each other for conflicts.
- `CoreqClass`: a whitelisted or configured pair of two different courses, same instructor; the two meetings must be either both online, back-to-back in the same room, or on disjoint weekdays starting within 30 minutes of each other.

### Nonfatal atomic-class issues

Construction never rejects a row-level adjustment on any of the four kinds above -- see `docs/codes.md`'s "Never-Block Scheduling" section for the full design. Each kind defines one `is_valid_schedule(left, right)` covering everything in its bullet above; failing it still constructs the class, recording the problem as `schedule_issues` and reporting it through `evaluate_schedule()` as a hard violation (`four_credit_invalid` / `hybrid_invalid` / `coreq_invalid` / `cross_listing_invalid`) rather than raising. The solver still requires the full rule via `pairwise_predicate`, unconditionally for all four kinds -- so a pairing broken in a way the solver can actually fix (time, room) gets repaired, while one broken in a way it can't (e.g. a hybrid pairing whose physical/online shape no longer holds) correctly reports the solve attempt infeasible instead of silently shipping something invalid.

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
