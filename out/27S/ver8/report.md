# 27S ver8 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `f50283e0a5f4`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 4 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -435
- Best objective bound: -1820
- Solve time: 45.1366 seconds
- Candidate assignments: 5998
- Hard violations: 0
- Soft penalty: 100 (3 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff, Staff 2, Staff 3

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -490 | -1795 | 45.0115 | 200 | 6 | 0 |
| 2 | feasible | -690 | -1775 | 45.0909 | 225 | 6 | 0 |
| 3 | feasible | -670 | -1775 | 45.0161 | 240 | 6 | 0 |
| 4 | feasible | -435 | -1820 | 45.1366 | 100 | 2 | 0 |
| 5 | feasible | -565 | -1565 | 45.2734 | 120 | 3 | 0 |

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
| Growns, Landon C. | 15 | 11 | 15 | +4 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 17 | +3 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 23 | 4 | -19 |
| Staff 2 | n/a | 6 | 12 | +6 |
| Staff 3 | n/a | 6 | 9 | +3 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 15 | 7 | -8 |

## Simplified changes from initial

- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 1914-001** room: `Corley 101` -> `Corley 267`
- **MATH 1914-003** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 2914-001** instructor: `Jordan, Susan M.` -> `Growns, Landon C.`
- **MATH 2914-001** time: `MWF 9:00am` -> `MWF 8:00am`
- **MATH 2914-001** room: `Corley 101` -> `Corley 103`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Jordan, Susan M.`
- **MATH 2924-001** time: `MWF 1:00pm` -> `MWF 8:00am`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Xiao, Xinli`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 1:00pm`
- **MATH 2924-003** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 2934-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-002** time: `R 11:00am` -> `T 2:30pm`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 268` -> `Rothwell 306`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 268` -> `Rothwell 306`
- **MATH 0803-001** room: `Corley 103` -> `Corley 269`
- **MATH 0903-002** time: `MWF 8:00am` -> `MWF 2:00pm`
- **MATH 1113-002** time: `TR 8:00am` -> `TR 2:30pm`
- **MATH 0903-TC1** instructor: `Staff` -> `Staff 2`
- **MATH 1113-TC1** instructor: `Staff` -> `Staff 2`
- **MATH 1003-005** instructor: `Winn, Janet L.` -> `Ballard, Kasey L.`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Winn, Janet L.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 11:00am`
- **MATH 1113-006** instructor: `Taylor, Teresa L.` -> `Jordan, Susan M.`
- **MATH 1113-006** room: `Corley 104` -> `Corley 101`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Taylor, Teresa L.`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Jordan, Susan M.`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 101`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Overduin, Matthew D.`
- **MATH 3243-001** instructor: `Xiao, Xinli` -> `Limperis, Thomas G.`
- **MATH 3243-001** time: `MWF 10:00am` -> `MWF 2:00pm`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 10:00am`
- **MATH 4971-001** time: `T 11:00am` -> `W 12:00pm`
- **MATH 1003-007** instructor: `Staff` -> `Staff 3`
- **MATH 1003-007** time: `MWF 1:00pm` -> `MWF 8:00am`
- **MATH 1003-007** room: `` -> `Rothwell 213`
- **STAT 2163-004** instructor: `Staff` -> `King, Jamie L.`
- **STAT 2163-004** room: `` -> `Corley 268`

## Remaining hard violations

- none

## Remaining soft findings

- [under_load] (90) Yousuf, Marium: 7 credit hours is under max_load 15
- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
