# 27S ver9 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `f50283e0a5f4`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 3 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -555
- Best objective bound: -1780
- Solve time: 45.0173 seconds
- Candidate assignments: 5998
- Hard violations: 0
- Soft penalty: 170 (6 findings)
- Worst instructor overload: 3 credit hours
- Remaining placeholder identities: Staff

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -520 | -1760 | 45.0141 | 35 | 3 | 0 |
| 2 | feasible | -390 | -1505 | 45.0097 | 305 | 6 | 0 |
| 3 | feasible | -555 | -1780 | 45.0173 | 170 | 3 | 0 |
| 4 | feasible | -775 | -1770 | 45.1156 | 120 | 6 | 0 |
| 5 | feasible | -375 | -1705 | 45.0097 | 210 | 6 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 3 | 0 |
| Soft penalty | 520 | 170 |
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
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 23 | 15 | -8 |
| Staff 2 | n/a | 6 | 0 | -6 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 12 | +2 |
| Yousuf, Marium | 15 | 15 | 17 | +2 |

## Simplified changes from initial

- **MATH 1113-F01** instructor: `Yousuf, Marium` -> `Taylor, Teresa L.`
- **MATH 1113-F01** time: `MWF 10:00am` -> `MWF 2:00pm`
- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 2914-003** room: `Corley 101` -> `Corley 102`
- **MATH 2924-001** instructor: `Yousuf, Marium` -> `Xiao, Xinli`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Xiao, Xinli`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 2:00pm`
- **MATH 2924-003** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 2934-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-002** instructor: `Staff` -> `Yousuf, Marium`
- **MATH 2934-002** room: `Corley 101` -> `Corley 269`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 268` -> `Rothwell 212`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 268` -> `Rothwell 212`
- **MATH 0903-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 1113-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 0803-004** instructor: `Staff 2` -> `Staff`
- **MATH 0803-004** room: `Corley 267` -> `Corley 101`
- **MATH 1003-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-004** room: `Corley 267` -> `Corley 101`
- **MATH 1113-006** instructor: `Taylor, Teresa L.` -> `Yousuf, Marium`
- **MATH 2243-001** instructor: `Overduin, Matthew D.` -> `Cox, Allie M.`
- **MATH 2703-001** time: `MWF 10:00am` -> `MWF 2:00pm`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Yousuf, Marium`
- **MATH 2703-002** time: `TR 11:00am` -> `TR 8:00am`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3123-001** room: `Corley 102` -> `Ross Pendergraft Library 331`
- **MATH 3243-001** instructor: `Xiao, Xinli` -> `Overduin, Matthew D.`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 2:00pm`
- **MATH 4003-001** instructor: `Xiao, Xinli` -> `Overduin, Matthew D.`
- **STAT 2163-001** room: `Rothwell 221` -> `Corley 269`
- **STAT 2163-004** instructor: `Staff` -> `Jordan, Scott M.`
- **STAT 2163-004** room: `` -> `Ross Pendergraft Library 332`

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (100) Jordan, Scott M.: 15 credit hours exceeds max_load 12
- [custom_rule] (50) MATH 1914-001: matches a custom dislike rule (weight 50)
- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 0903-002: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
