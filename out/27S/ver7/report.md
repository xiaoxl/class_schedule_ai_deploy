# 27S ver7 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `9ce9a12c7dc8`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 2 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -835
- Best objective bound: -1835
- Solve time: 45.012 seconds
- Candidate assignments: 5998
- Hard violations: 0
- Soft penalty: 100 (3 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -645 | -2030 | 45.0137 | 280 | 6 | 0 |
| 2 | feasible | -835 | -1835 | 45.012 | 100 | 2 | 0 |
| 3 | feasible | -875 | -1960 | 45.0077 | 235 | 6 | 0 |
| 4 | feasible | -690 | -2055 | 45.0161 | 430 | 6 | 0 |
| 5 | feasible | -530 | -2025 | 45.0106 | 475 | 6 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 3 | 0 |
| Soft penalty | 520 | 100 |
| Soft findings | 10 | 3 |
| Worst overload | 1 | 2 |

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
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Staff | n/a | 23 | 16 | -7 |
| Staff 2 | n/a | 6 | 0 | -6 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 10 | +0 |
| Yousuf, Marium | 15 | 15 | 17 | +2 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 11:00am`
- **MATH 2914-002** instructor: `Jordan, Susan M.` -> `Cox, Allie M.`
- **MATH 2914-002** room: `Corley 101` -> `Corley 268`
- **MATH 2914-003** time: `R 2:30pm` -> `R 11:00am`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Limperis, Thomas G.`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 2:00pm`
- **MATH 2924-003** instructor: `Limperis, Thomas G.` -> `Overduin, Matthew D.`
- **MATH 2924-003** time: `R 9:30am` -> `T 2:30pm`
- **MATH 2934-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-002** time: `MWF 11:00am` -> `MWF 8:00am`
- **MATH 2934-002** time: `R 11:00am` -> `T 8:00am`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 268` -> `Rothwell 312`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 268` -> `Rothwell 312`
- **MATH 0903-001** instructor: `Staff 3` -> `Winn, Janet L.`
- **MATH 1113-001** instructor: `Staff 3` -> `Winn, Janet L.`
- **MATH 0903-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1113-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 0803-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-TC2** instructor: `King, Jamie L.` -> `Ballard, Kasey L.`
- **MATH 1113-006** instructor: `Taylor, Teresa L.` -> `Jordan, Susan M.`
- **MATH 1113-006** time: `TR 9:30am` -> `TR 2:30pm`
- **MATH 1113-006** room: `Corley 104` -> `Corley 101`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Taylor, Teresa L.`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Yousuf, Marium`
- **MATH 2703-002** time: `TR 11:00am` -> `TR 9:30am`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 11:00am`
- **MATH 1003-007** instructor: `Staff` -> `Jordan, Susan M.`
- **MATH 1003-007** room: `` -> `Corley 101`
- **STAT 2163-004** instructor: `Staff` -> `King, Jamie L.`
- **STAT 2163-004** room: `` -> `Corley 267`

## Remaining hard violations

- none

## Remaining soft findings

- [under_load] (90) Xiao, Xinli: 10 credit hours is under max_load 12
- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 0903-001: matches a custom dislike rule (weight 5)
