# 27S ver2 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `3e0858a58417`

Ran 3 independent attempt(s), each with a 20s CP-SAT budget. Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -820
- Best objective bound: -1555
- Solve time: 20.0081 seconds
- Candidate assignments: 6094
- Hard violations: 0
- Soft penalty: 20 (4 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff, Staff 2

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -820 | -1555 | 20.0081 | 20 | 2 | 0 |
| 2 | feasible | -730 | -1555 | 20.0132 | 110 | 2 | 0 |
| 3 | feasible | -770 | -1540 | 20.0101 | 205 | 6 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 2 | 0 |
| Soft penalty | 520 | 20 |
| Soft findings | 10 | 4 |
| Worst overload | 1 | 2 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 15 | +4 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 17 | +3 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 23 | 12 | -11 |
| Staff 2 | n/a | 6 | 6 | +0 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 15 | 15 | +0 |

## Simplified changes from initial

- **MATH 1113-F01** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Growns, Landon C.`
- **MATH 1914-001** time: `T 9:30am` -> `R 8:00am`
- **MATH 2914-001** time: `R 9:30am` -> `T 2:30pm`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Limperis, Thomas G.`
- **MATH 2914-003** room: `Corley 101` -> `Corley 268`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 2:00pm`
- **MATH 2924-003** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 2924-003** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 2934-001** instructor: `Staff` -> `Yousuf, Marium`
- **MATH 2934-002** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-002** room: `Corley 101` -> `Corley 103`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 1:00pm`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 1:00pm`
- **MATH 1003-001** room: `Corley 103` -> `Corley 267`
- **MATH 0903-001** instructor: `Staff 3` -> `Staff`
- **MATH 1113-001** instructor: `Staff 3` -> `Staff`
- **MATH 1113-006** time: `TR 9:30am` -> `TR 8:00am`
- **MATH 1113-006** room: `Corley 104` -> `Corley 102`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Cox, Allie M.`
- **MATH 2223-001** time: `MWF 11:00am` -> `MWF 9:00am`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Jordan, Susan M.`
- **MATH 2703-002** time: `TR 11:00am` -> `TR 9:30am`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 101`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Overduin, Matthew D.`
- **MATH 4003-001** time: `MWF 9:00am` -> `MWF 11:00am`
- **STAT 3113-001** time: `MWF 11:00am` -> `MWF 8:00am`
- **MATH 1003-007** instructor: `Staff` -> `Jordan, Susan M.`
- **MATH 1003-007** time: `MWF 1:00pm` -> `MWF 2:00pm`
- **MATH 1003-007** room: `` -> `Corley 101`
- **STAT 2163-004** instructor: `Staff` -> `Bain, Leslie M.`
- **STAT 2163-004** room: `` -> `Corley 104`

## Remaining hard violations

- none

## Remaining soft findings

- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 0903-002: falls in a disliked time (No 8am classes)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (No 8am classes)
