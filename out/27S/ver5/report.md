# 27S ver5 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `c44e63cf169c`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 3 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -550
- Best objective bound: -2015
- Solve time: 45.0082 seconds
- Candidate assignments: 5998
- Hard violations: 0
- Soft penalty: 210 (6 findings)
- Worst instructor overload: 3 credit hours
- Remaining placeholder identities: Staff

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -815 | -1880 | 45.0113 | 285 | 6 | 0 |
| 2 | feasible | -685 | -2050 | 45.0636 | 305 | 4 | 0 |
| 3 | feasible | -550 | -2015 | 45.0082 | 210 | 3 | 0 |
| 4 | feasible | -720 | -1850 | 45.0127 | 295 | 5 | 0 |
| 5 | feasible | -625 | -2010 | 45.0131 | 360 | 6 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 3 | 0 |
| Soft penalty | 520 | 210 |
| Soft findings | 10 | 6 |
| Worst overload | 1 | 3 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 15 | +3 |
| Jordan, Susan M. | 15 | 14 | 15 | +1 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Staff | n/a | 23 | 18 | -5 |
| Staff 2 | n/a | 6 | 0 | -6 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 16 | +1 |
| Xiao, Xinli | 12 | 10 | 7 | -3 |
| Yousuf, Marium | 15 | 15 | 17 | +2 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 2:00pm`
- **MATH 1914-003** instructor: `Ballard, Kasey L.` -> `Winn, Janet L.`
- **MATH 1914-003** room: `Corley 268` -> `Corley 103`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Ballard, Kasey L.`
- **MATH 2914-003** time: `MWF 2:00pm` -> `MWF 11:00am`
- **MATH 2914-003** time: `R 2:30pm` -> `R 11:00am`
- **MATH 2924-001** instructor: `Yousuf, Marium` -> `Limperis, Thomas G.`
- **MATH 2924-001** room: `Corley 102` -> `Rothwell 306`
- **MATH 2924-001** room: `Corley 102` -> `Rothwell 213`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 2:00pm`
- **MATH 2924-003** instructor: `Limperis, Thomas G.` -> `Overduin, Matthew D.`
- **MATH 2924-003** room: `Rothwell 306` -> `Corley 268`
- **MATH 2924-003** time: `R 9:30am` -> `R 8:00am`
- **MATH 2934-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-002** instructor: `Staff` -> `Yousuf, Marium`
- **MATH 2934-002** room: `Corley 101` -> `Corley 104`
- **MATH 2934-002** time: `R 11:00am` -> `T 2:30pm`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 268` -> `Rothwell 221`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 268` -> `Rothwell 221`
- **MATH 0803-001** instructor: `Winn, Janet L.` -> `King, Jamie L.`
- **MATH 1003-001** instructor: `Winn, Janet L.` -> `King, Jamie L.`
- **MATH 0903-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 1113-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 1113-001** room: `Corley 104` -> `Corley 269`
- **MATH 0803-004** instructor: `Staff 2` -> `Staff`
- **MATH 0803-004** time: `MWF 11:00am` -> `MWF 10:00am`
- **MATH 1003-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-004** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 1003-005** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 1003-005** room: `Corley 104` -> `Corley 268`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Winn, Janet L.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 11:00am`
- **MATH 2223-001** room: `Corley 103` -> `Rothwell 312`
- **MATH 2223-003** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 2223-003** room: `Corley 103` -> `Ross Pendergraft Library 220`
- **MATH 2243-001** instructor: `Overduin, Matthew D.` -> `Cox, Allie M.`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Yousuf, Marium`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3243-001** instructor: `Xiao, Xinli` -> `Overduin, Matthew D.`
- **MATH 3243-001** time: `MWF 10:00am` -> `MWF 1:00pm`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 11:00am`
- **STAT 2163-001** instructor: `King, Jamie L.` -> `Jordan, Scott M.`
- **MATH 1003-007** room: `` -> `Ross Pendergraft Library 220`
- **STAT 2163-004** room: `` -> `Corley 104`

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (100) Jordan, Scott M.: 15 credit hours exceeds max_load 12
- [under_load] (90) Xiao, Xinli: 7 credit hours is under max_load 12
- [custom_rule] (5) MATH 1914-003: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 0903-002: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
