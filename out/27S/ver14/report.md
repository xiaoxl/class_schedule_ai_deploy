# 27S ver14 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `f07e7b85dc43`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -775
- Best objective bound: -1241
- Solve time: 45.0121 seconds
- Candidate assignments: 6122
- Hard violations: 0
- Soft penalty: 60 (3 findings)
- Worst instructor overload: 0 credit hours
- Remaining placeholder identities: Staff

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -775 | -1241 | 45.0121 | 60 | 0 | 0 |
| 2 | feasible | -605 | -1465 | 45.0104 | 280 | 4 | 0 |
| 3 | feasible | -405 | -1470 | 45.0086 | 225 | 1 | 0 |
| 4 | feasible | -690 | -1420 | 45.0109 | 35 | 1 | 0 |
| 5 | feasible | -429 | -1465 | 45.0117 | 140 | 1 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 3 | 0 |
| Soft penalty | 460 | 60 |
| Soft findings | 10 | 3 |
| Worst overload | 0 | 0 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 16 | +0 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 17 | +3 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 23 | 16 | -7 |
| Staff 2 | n/a | 6 | 0 | -6 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 13 | +3 |
| Yousuf, Marium | 15 | 15 | 15 | +0 |

## Simplified changes from initial

- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 1914-001** room: `Corley 101` -> `Corley 268`
- **MATH 2914-003** room: `Corley 101` -> `Corley 267`
- **MATH 2924-001** time: `R 1:00pm` -> `T 1:00pm`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Limperis, Thomas G.`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 1:00pm`
- **MATH 2934-001** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 2934-002** instructor: `Staff` -> `Yousuf, Marium`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 268` -> `Rothwell 306`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 268` -> `Rothwell 306`
- **MATH 0903-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 1113-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 0903-002** time: `MWF 8:00am` -> `MWF 2:00pm`
- **MATH 1113-002** time: `TR 8:00am` -> `TR 2:30pm`
- **MATH 0803-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Jordan, Susan M.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 10:00am`
- **MATH 1003-006** room: `Rothwell 221` -> `Corley 101`
- **MATH 1113-006** time: `TR 9:30am` -> `TR 8:00am`
- **MATH 1113-006** room: `Corley 104` -> `Corley 102`
- **MATH 2703-001** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Overduin, Matthew D.`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 4003-001** time: `MWF 9:00am` -> `MWF 2:00pm`
- **MATH 1003-007** instructor: `Staff` -> `Jordan, Susan M.`
- **MATH 1003-007** time: `MWF 1:00pm` -> `MWF 2:00pm`
- **MATH 1003-007** room: `` -> `Corley 101`
- **STAT 2163-004** instructor: `Staff` -> `King, Jamie L.`
- **STAT 2163-004** room: `` -> `Corley 268`

## Remaining hard violations

- none

## Remaining soft findings

- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
- [custom_rule] (50) MATH 2703-001: matches a custom dislike rule (weight 50)
