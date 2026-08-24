# 27S ver25 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `f1d7cf69b459`

Ran 3 independent attempt(s), each with a 20s CP-SAT budget. Selected attempt 2 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -650
- Best objective bound: -1545
- Solve time: 20.0124 seconds
- Candidate assignments: 5972
- Hard violations: 0
- Soft penalty: 120 (7 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff, Staff 2

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -690 | -1480 | 20.0098 | 305 | 6 | 0 |
| 2 | feasible | -650 | -1545 | 20.0124 | 120 | 2 | 0 |
| 3 | feasible | -920 | -1570 | 20.0088 | 200 | 5 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 2 | 0 |
| Soft penalty | 475 | 120 |
| Soft findings | 10 | 7 |
| Worst overload | 1 | 2 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 17 | +1 |
| Growns, Landon C. | 15 | 11 | 16 | +5 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 17 | +3 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 7 | -3 |
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Staff | n/a | 23 | 15 | -8 |
| Staff 2 | n/a | 6 | 7 | +1 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 13 | +3 |
| Yousuf, Marium | 15 | 15 | 15 | +0 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Growns, Landon C.`
- **MATH 1914-001** time: `T 9:30am` -> `T 8:00am`
- **MATH 1914-003** room: `Corley 268` -> `Ross Pendergraft Library 220`
- **MATH 2914-001** time: `R 9:30am` -> `R 8:00am`
- **MATH 2914-003** room: `Corley 101` -> `Corley 104`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 8:00am`
- **MATH 2934-001** instructor: `Staff` -> `Overduin, Matthew D.`
- **MATH 2934-001** time: `T 9:30am` -> `T 8:00am`
- **MATH 2934-001** room: `Rothwell 207` -> `Corley 103`
- **MATH 2934-002** instructor: `Staff` -> `Staff 2`
- **MATH 2934-002** room: `Corley 101` -> `Corley 269`
- **MATH 2934-002** room: `Corley 101` -> `Corley 268`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 0903-001** instructor: `Staff 3` -> `Staff`
- **MATH 1113-001** instructor: `Staff 3` -> `Staff`
- **MATH 0903-TC1** instructor: `Staff` -> `Growns, Landon C.`
- **MATH 1113-TC1** instructor: `Staff` -> `Growns, Landon C.`
- **MATH 1110-003** instructor: `Growns, Landon C.` -> `Cox, Allie M.`
- **MATH 1110-003** time: `MW 2:00pm` -> `MW 10:00am`
- **MATH 1113-003** instructor: `Growns, Landon C.` -> `Cox, Allie M.`
- **MATH 1113-003** time: `MWF 1:00pm` -> `MWF 9:00am`
- **MATH 0803-004** instructor: `Staff 2` -> `Staff`
- **MATH 0803-004** time: `MWF 11:00am` -> `MWF 9:00am`
- **MATH 1003-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-004** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 1003-005** instructor: `Winn, Janet L.` -> `King, Jamie L.`
- **MATH 1003-005** room: `Corley 104` -> `Rothwell 207`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Winn, Janet L.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 11:00am`
- **MATH 1113-006** instructor: `Taylor, Teresa L.` -> `Jordan, Susan M.`
- **MATH 1113-006** room: `Corley 104` -> `Corley 101`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Taylor, Teresa L.`
- **MATH 2043-001** room: `Corley 102` -> `Rothwell 213`
- **MATH 2223-003** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Jordan, Susan M.`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 101`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Ballard, Kasey L.`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 8:00am`
- **MATH 3243-002** room: `Rothwell 212` -> `Corley 268`
- **MATH 4971-001** room: `Corley 101` -> `Ross Pendergraft Library 220`
- **STAT 2163-001** time: `MWF 10:00am` -> `MWF 1:00pm`
- **STAT 2163-001** room: `Rothwell 221` -> `Corley 268`
- **MATH 1003-007** instructor: `Staff` -> `Staff 2`
- **MATH 1003-007** time: `MWF 1:00pm` -> `MWF 9:00am`
- **MATH 1003-007** room: `` -> `Corley 102`

## Remaining hard violations

- none

## Remaining soft findings

- [under_load] (90) Limperis, Thomas G.: 7 credit hours is under max_load 12
- [disliked_time] (5) MATH 2914-001: falls in a disliked time (No 8am classes)
- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 0903-002: falls in a disliked time (No 8am classes)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (No 8am classes)
- [disliked_time] (5) MATH 2223-003: falls in a disliked time (Prefers no early classes)
