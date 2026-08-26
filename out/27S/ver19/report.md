# 27S ver19 solve report

Validated solver input: `work/27S/initial-dynamic-pools-2300/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial-dynamic-pools-2300/initial.csv` (57 atomic classes, 79 rows)

Reconciliation snapshot: `work/27S/initial-dynamic-pools-2300/reconciliation.toml`

Configuration version: `c09c98626acf`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget and 8 search worker(s). Selected attempt 3 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -885
- Best objective bound: -1221
- Solve time: 48.6296 seconds
- Candidate assignments: 25215
- CP-SAT search workers: 8
- Hard violations: 0
- Soft penalty: 180 (7 findings)
- Worst instructor overload: 1 credit hours
- Remaining placeholder identities: new_instructor, new_professor

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -840 | -1207 | 46.9079 | 285 | 2 | 0 |
| 2 | feasible | -740 | -1226 | 48.3109 | 75 | 1 | 0 |
| 3 | feasible | -885 | -1221 | 48.6296 | 180 | 1 | 0 |
| 4 | feasible | -640 | -1219 | 48.3218 | 95 | 1 | 0 |
| 5 | feasible | -725 | -1226 | 47.4122 | 85 | 1 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 18 | 0 |
| Soft penalty | 850 | 180 |
| Soft findings | 10 | 7 |
| Worst overload | 0 | 1 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 12 | -1 |
| Cox, Allie M. | 15 | 16 | 16 | +0 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 16 | +2 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 14 | 14 | +0 |
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 18 | +3 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 0 | 16 | +16 |
| new_instructor | n/a | 25 | 9 | -16 |
| new_instructor 2 | n/a | 3 | 0 | -3 |
| new_instructor 3 | n/a | 3 | 0 | -3 |
| new_professor | n/a | 15 | 3 | -12 |

## Simplified changes from initial

- **MATH 1113-F01** instructor: `new_instructor` -> `Yousuf, Marium`
- **MATH 1113-F01** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 1914-001** room: `Corley 101` -> `Corley 268`
- **MATH 1914-001** room: `Corley 101` -> `Ross Pendergraft Library 332`
- **MATH 1914-003** instructor: `Ballard, Kasey L.` -> `Jordan, Susan M.`
- **MATH 1914-003** room: `Corley 102` -> `Corley 101`
- **MATH 1914-003** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 1914-003** room: `Corley 268` -> `Corley 101`
- **MATH 2914-001** time: `R 9:30am` -> `T 9:30am`
- **MATH 2914-003** instructor: `new_instructor` -> `Jordan, Susan M.`
- **MATH 2924-001** instructor: `new_professor` -> `Xiao, Xinli`
- **MATH 2924-001** room: `Corley 102` -> `Corley 103`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 2:00pm`
- **MATH 2934-001** instructor: `new_professor` -> `Yousuf, Marium`
- **MATH 2934-001** room: `Rothwell 207` -> `Corley 104`
- **MATH 2934-002** instructor: `new_professor` -> `Overduin, Matthew D.`
- **MATH 2934-002** room: `Corley 101` -> `Corley 267`
- **MATH 4123-001** instructor: `new_professor` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 101` -> `Rothwell 312`
- **MATH 4123-H01** instructor: `new_professor` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 101` -> `Rothwell 312`
- **MATH 0803-004** instructor: `new_instructor` -> `King, Jamie L.`
- **MATH 0803-004** room: `Corley 101` -> `Corley 267`
- **MATH 1003-004** instructor: `new_instructor` -> `King, Jamie L.`
- **MATH 1003-004** room: `Corley 101` -> `Corley 267`
- **MATH 0903-001** instructor: `new_instructor` -> `Winn, Janet L.`
- **MATH 1113-001** instructor: `new_instructor` -> `Winn, Janet L.`
- **MATH 1113-001** room: `Corley 104` -> `Corley 269`
- **MATH 0903-002** time: `MWF 8:00am` -> `MWF 2:00pm`
- **MATH 1113-002** time: `TR 8:00am` -> `TR 2:30pm`
- **MATH 1110-003** time: `MW 2:00pm` -> `TR 1:00pm`
- **MATH 1003-005** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1003-005** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Growns, Landon C.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 2:00pm`
- **MATH 1003-TC2** instructor: `King, Jamie L.` -> `Ballard, Kasey L.`
- **MATH 1113-006** room: `Corley 104` -> `Ross Pendergraft Library 220`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Yousuf, Marium`
- **MATH 2243-002** room: `Ross Pendergraft Library 220` -> `Rothwell 221`
- **MATH 2703-001** instructor: `Jordan, Susan M.` -> `Ballard, Kasey L.`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `new_professor`
- **STAT 2163-TC2** instructor: `Bain, Leslie M.` -> `Yousuf, Marium`
- **MATH 1003-007** instructor: `new_instructor 3` -> `new_instructor`
- **STAT 2163-004** instructor: `new_instructor 2` -> `Bain, Leslie M.`
- **STAT 2163-004** room: `Corley 101` -> `Corley 104`

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (100) Winn, Janet L.: 18 credit hours exceeds max_load 15
- [custom_rule] (30) MATH 2924-001: matches a custom dislike rule (weight 30)
- [custom_rule] (30) MATH 2924-001: matches a custom dislike rule (weight 30)
- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 0803-004: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 0903-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
