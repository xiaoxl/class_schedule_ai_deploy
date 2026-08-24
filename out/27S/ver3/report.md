# 27S ver3 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `2f2f50210fec`

Ran 3 independent attempt(s), each with a 20s CP-SAT budget. Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -685
- Best objective bound: -2025
- Solve time: 20.0076 seconds
- Candidate assignments: 6094
- Hard violations: 0
- Soft penalty: 25 (5 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -685 | -2025 | 20.0076 | 25 | 2 | 0 |
| 2 | feasible | -490 | -2130 | 20.0094 | 365 | 6 | 0 |
| 3 | feasible | -830 | -1930 | 20.0046 | 210 | 3 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 2 | 0 |
| Soft penalty | 520 | 25 |
| Soft findings | 10 | 5 |
| Worst overload | 1 | 2 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 17 | +1 |
| Growns, Landon C. | 15 | 11 | 15 | +4 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 17 | +3 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Staff | n/a | 23 | 16 | -7 |
| Staff 2 | n/a | 6 | 0 | -6 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 12 | +2 |
| Yousuf, Marium | 15 | 15 | 16 | +1 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** time: `T 9:30am` -> `T 1:00pm`
- **MATH 1914-003** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 2914-001** instructor: `Jordan, Susan M.` -> `Overduin, Matthew D.`
- **MATH 2914-001** room: `Corley 101` -> `Corley 267`
- **MATH 2914-001** time: `R 9:30am` -> `R 8:00am`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Xiao, Xinli`
- **MATH 2914-003** time: `R 2:30pm` -> `R 11:00am`
- **MATH 2924-001** instructor: `Yousuf, Marium` -> `Xiao, Xinli`
- **MATH 2924-001** room: `Corley 102` -> `Corley 103`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Limperis, Thomas G.`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 1:00pm`
- **MATH 2924-003** room: `Rothwell 306` -> `Rothwell 207`
- **MATH 2934-001** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 2934-002** instructor: `Staff` -> `Yousuf, Marium`
- **MATH 2934-002** time: `MWF 11:00am` -> `MWF 9:00am`
- **MATH 2934-002** room: `Corley 101` -> `Corley 269`
- **MATH 4123-001** room: `Corley 268` -> `Corley 267`
- **MATH 4123-H01** room: `Corley 268` -> `Corley 267`
- **MATH 0903-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 1113-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 1110-003** instructor: `Growns, Landon C.` -> `Cox, Allie M.`
- **MATH 1113-003** instructor: `Growns, Landon C.` -> `Cox, Allie M.`
- **MATH 0803-004** instructor: `Staff 2` -> `King, Jamie L.`
- **MATH 0803-004** room: `Corley 267` -> `Corley 103`
- **MATH 1003-004** instructor: `Staff 2` -> `King, Jamie L.`
- **MATH 1003-004** room: `Corley 267` -> `Corley 103`
- **MATH 1003-005** instructor: `Winn, Janet L.` -> `Jordan, Susan M.`
- **MATH 1003-005** room: `Corley 104` -> `Corley 101`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Jordan, Susan M.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 11:00am`
- **MATH 1003-006** room: `Rothwell 221` -> `Corley 101`
- **MATH 1003-TC2** instructor: `King, Jamie L.` -> `Winn, Janet L.`
- **MATH 1113-006** instructor: `Taylor, Teresa L.` -> `Jordan, Susan M.`
- **MATH 1113-006** room: `Corley 104` -> `Corley 101`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Taylor, Teresa L.`
- **MATH 2223-001** room: `Corley 103` -> `Rothwell 207`
- **MATH 2223-003** room: `Corley 103` -> `Corley 104`
- **MATH 2243-001** instructor: `Overduin, Matthew D.` -> `Ballard, Kasey L.`
- **MATH 2243-001** time: `MWF 1:00pm` -> `MWF 8:00am`
- **MATH 2243-001** room: `Corley 104` -> `Rothwell 306`
- **MATH 2703-001** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 2703-001** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 2703-001** room: `Corley 101` -> `Corley 102`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Yousuf, Marium`
- **MATH 2703-002** time: `TR 11:00am` -> `TR 1:00pm`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 102`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3243-001** instructor: `Xiao, Xinli` -> `Limperis, Thomas G.`
- **MATH 3243-001** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 4003-001** instructor: `Xiao, Xinli` -> `Overduin, Matthew D.`
- **MATH 4003-001** time: `MWF 9:00am` -> `MWF 8:00am`
- **STAT 2163-001** time: `MWF 10:00am` -> `MWF 9:00am`
- **STAT 3153-001** room: `Rothwell 207` -> `Rothwell 312`
- **STAT 3153-002** room: `Corley 102` -> `Rothwell 221`
- **MATH 1003-007** instructor: `Staff` -> `Growns, Landon C.`
- **MATH 1003-007** time: `MWF 1:00pm` -> `MWF 8:00am`
- **MATH 1003-007** room: `` -> `Ross Pendergraft Library 331`

## Remaining hard violations

- none

## Remaining soft findings

- [disliked_time] (5) MATH 1914-001: falls in a disliked time (No 8am classes)
- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 0903-002: falls in a disliked time (No 8am classes)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (No 8am classes)
