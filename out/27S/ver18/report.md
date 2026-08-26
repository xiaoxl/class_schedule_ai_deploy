# 27S ver18 solve report

Validated solver input: `work/27S/initial-dynamic-pools/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial-dynamic-pools/initial.csv` (57 atomic classes, 79 rows)

Reconciliation snapshot: `work/27S/initial-dynamic-pools/reconciliation.toml`

Configuration version: `527f958b7377`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget and 8 search worker(s). Selected attempt 3 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -835
- Best objective bound: -1219
- Solve time: 47.1704 seconds
- Candidate assignments: 26823
- CP-SAT search workers: 8
- Hard violations: 0
- Soft penalty: 110 (6 findings)
- Worst instructor overload: 0 credit hours
- Remaining placeholder identities: new_instructor, new_professor

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -950 | -1220 | 47.263 | 105 | 1 | 0 |
| 2 | feasible | -670 | -1219 | 47.8686 | 300 | 1 | 0 |
| 3 | feasible | -835 | -1219 | 47.1704 | 110 | 0 | 0 |
| 4 | feasible | -540 | -1200 | 47.8832 | 100 | 0 | 0 |
| 5 | feasible | 315 | -1214 | 48.8984 | 1185 | 4 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 18 | 0 |
| Soft penalty | 850 | 110 |
| Soft findings | 10 | 6 |
| Worst overload | 0 | 0 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 15 | +1 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 14 | 13 | -1 |
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 0 | 17 | +17 |
| new_instructor | n/a | 22 | 9 | -13 |
| new_instructor 2 | n/a | 3 | 0 | -3 |
| new_instructor 3 | n/a | 6 | 0 | -6 |
| new_professor | n/a | 15 | 7 | -8 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 2:00pm`
- **MATH 1914-001** time: `T 9:30am` -> `R 2:30pm`
- **MATH 2914-003** instructor: `new_instructor` -> `Yousuf, Marium`
- **MATH 2914-003** room: `Corley 101` -> `Corley 267`
- **MATH 2914-003** time: `R 2:30pm` -> `T 2:30pm`
- **MATH 2924-001** room: `Corley 102` -> `Corley 267`
- **MATH 2924-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 9:00am`
- **MATH 2924-002** time: `T 1:00pm` -> `T 9:30am`
- **MATH 2934-001** instructor: `new_professor` -> `Yousuf, Marium`
- **MATH 2934-001** room: `Rothwell 207` -> `Corley 268`
- **MATH 2934-002** instructor: `new_professor` -> `Overduin, Matthew D.`
- **MATH 4123-001** instructor: `new_professor` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 101` -> `Rothwell 306`
- **MATH 4123-H01** instructor: `new_professor` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 101` -> `Rothwell 306`
- **MATH 0803-004** instructor: `new_instructor 3` -> `new_instructor`
- **MATH 0803-004** room: `Corley 101` -> `Ross Pendergraft Library 220`
- **MATH 1003-004** instructor: `new_instructor 3` -> `new_instructor`
- **MATH 1003-004** room: `Corley 101` -> `Ross Pendergraft Library 220`
- **MATH 0903-001** instructor: `new_instructor` -> `Growns, Landon C.`
- **MATH 1113-001** instructor: `new_instructor` -> `Growns, Landon C.`
- **MATH 0903-TC1** instructor: `new_instructor` -> `Bain, Leslie M.`
- **MATH 1113-TC1** instructor: `new_instructor` -> `Bain, Leslie M.`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Ballard, Kasey L.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 8:00am`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Yousuf, Marium`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Cox, Allie M.`
- **MATH 2033-001** time: `MWF 10:00am` -> `MWF 1:00pm`
- **MATH 2223-003** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 2223-003** room: `Corley 103` -> `Ross Pendergraft Library 332`
- **MATH 2243-002** time: `TR 9:30am` -> `TR 2:30pm`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 11:00am`
- **MATH 4003-001** time: `MWF 9:00am` -> `MWF 1:00pm`
- **STAT 2163-TC1** instructor: `Bain, Leslie M.` -> `Yousuf, Marium`
- **MATH 1003-007** instructor: `new_instructor` -> `King, Jamie L.`
- **MATH 1003-007** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 1003-007** room: `Corley 101` -> `Rothwell 221`
- **STAT 2163-004** instructor: `new_instructor 2` -> `new_professor`

## Remaining hard violations

- none

## Remaining soft findings

- [custom_rule] (30) MATH 2924-002: matches a custom dislike rule (weight 30)
- [custom_rule] (30) MATH 2924-002: matches a custom dislike rule (weight 30)
- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (20) MATH 0903-002: matches a custom dislike rule (weight 20)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
- [custom_rule] (20) MATH 1113-002: matches a custom dislike rule (weight 20)
