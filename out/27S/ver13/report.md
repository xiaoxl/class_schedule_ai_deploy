# 27S ver13 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `8712664adce9`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 3 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -700
- Best objective bound: -1604
- Solve time: 45.0122 seconds
- Candidate assignments: 6122
- Hard violations: 0
- Soft penalty: 195 (7 findings)
- Worst instructor overload: 4 credit hours
- Remaining placeholder identities: none

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -625 | -1565 | 45.0123 | 345 | 4 | 0 |
| 2 | feasible | -515 | -1597 | 45.0107 | 235 | 4 | 0 |
| 3 | feasible | -700 | -1604 | 45.0122 | 195 | 4 | 0 |
| 4 | feasible | -640 | -1594 | 45.0085 | 295 | 4 | 0 |
| 5 | feasible | -625 | -1435 | 45.1389 | 290 | 4 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 3 | 0 |
| Soft penalty | 460 | 195 |
| Soft findings | 10 | 7 |
| Worst overload | 0 | 4 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 21 | +6 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 18 | +7 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 19 | +5 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Staff | n/a | 23 | 0 | -23 |
| Staff 2 | n/a | 6 | 0 | -6 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 18 | +3 |
| Winn, Janet L. | 15 | 15 | 17 | +2 |
| Xiao, Xinli | 12 | 10 | 13 | +3 |
| Yousuf, Marium | 15 | 15 | 17 | +2 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 11:00am`
- **MATH 2914-001** time: `MWF 9:00am` -> `MWF 10:00am`
- **MATH 2914-002** time: `MWF 1:00pm` -> `MWF 2:00pm`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Jordan, Susan M.`
- **MATH 2914-003** time: `MWF 2:00pm` -> `MWF 1:00pm`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Limperis, Thomas G.`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 2:00pm`
- **MATH 2934-001** instructor: `Staff` -> `Yousuf, Marium`
- **MATH 2934-001** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 2934-002** instructor: `Staff` -> `Overduin, Matthew D.`
- **MATH 2934-002** time: `MWF 11:00am` -> `MWF 9:00am`
- **MATH 2934-002** time: `R 11:00am` -> `T 8:00am`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 268` -> `Rothwell 206`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 268` -> `Rothwell 206`
- **MATH 1003-001** room: `Corley 103` -> `Corley 267`
- **MATH 0903-001** instructor: `Staff 3` -> `King, Jamie L.`
- **MATH 1113-001** instructor: `Staff 3` -> `King, Jamie L.`
- **MATH 0903-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1113-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 0903-TC1** instructor: `Staff` -> `Bain, Leslie M.`
- **MATH 1113-TC1** instructor: `Staff` -> `Bain, Leslie M.`
- **MATH 1110-003** instructor: `Growns, Landon C.` -> `Winn, Janet L.`
- **MATH 1113-003** instructor: `Growns, Landon C.` -> `Winn, Janet L.`
- **MATH 0803-004** instructor: `Staff 2` -> `Winn, Janet L.`
- **MATH 1003-004** instructor: `Staff 2` -> `Winn, Janet L.`
- **MATH 1003-005** instructor: `Winn, Janet L.` -> `King, Jamie L.`
- **MATH 1003-005** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 1003-005** room: `Corley 104` -> `Corley 103`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Growns, Landon C.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 11:00am`
- **MATH 1003-TC2** instructor: `King, Jamie L.` -> `Growns, Landon C.`
- **MATH 1113-006** time: `TR 9:30am` -> `TR 2:30pm`
- **MATH 1113-006** room: `Corley 104` -> `Corley 102`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Taylor, Teresa L.`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Cox, Allie M.`
- **MATH 2703-001** instructor: `Jordan, Susan M.` -> `Limperis, Thomas G.`
- **MATH 2703-001** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 2703-001** room: `Corley 101` -> `Rothwell 212`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Jordan, Susan M.`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 101`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 4003-001** time: `MWF 9:00am` -> `MWF 1:00pm`
- **MATH 4971-001** time: `T 11:00am` -> `W 12:00pm`
- **STAT 2163-001** instructor: `King, Jamie L.` -> `Bain, Leslie M.`
- **STAT 2163-002** time: `MWF 9:00am` -> `MWF 2:00pm`
- **MATH 1003-007** instructor: `Staff` -> `Ballard, Kasey L.`
- **MATH 1003-007** time: `MWF 1:00pm` -> `MWF 9:00am`
- **MATH 1003-007** room: `` -> `Corley 104`
- **STAT 2163-004** instructor: `Staff` -> `Yousuf, Marium`
- **STAT 2163-004** room: `` -> `Ross Pendergraft Library 334`

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (60) Bain, Leslie M.: 21 credit hours exceeds max_load 15
- [overload] (10) Growns, Landon C.: 18 credit hours exceeds max_load 15
- [overload] (100) Jordan, Susan M.: 19 credit hours exceeds max_load 15
- [overload] (10) Taylor, Teresa L.: 18 credit hours exceeds max_load 15
- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 0903-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-001: matches a custom dislike rule (weight 5)
