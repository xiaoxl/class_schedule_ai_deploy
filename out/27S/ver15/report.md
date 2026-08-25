# 27S ver15 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `fbd2b0f19eb7`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 3 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -965
- Best objective bound: -1715
- Solve time: 45.0108 seconds
- Candidate assignments: 6122
- Hard violations: 0
- Soft penalty: 75 (5 findings)
- Worst instructor overload: 0 credit hours
- Remaining placeholder identities: Staff

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -825 | -1720 | 45.0118 | 175 | 1 | 0 |
| 2 | feasible | -810 | -1675 | 45.0122 | 330 | 2 | 0 |
| 3 | feasible | -965 | -1715 | 45.0108 | 75 | 0 | 0 |
| 4 | feasible | -1075 | -1655 | 45.1405 | 15 | 1 | 0 |
| 5 | feasible | -920 | -1715 | 45.0133 | 105 | 1 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 3 | 0 |
| Soft penalty | 460 | 75 |
| Soft findings | 10 | 5 |
| Worst overload | 0 | 0 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 16 | +1 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 15 | +4 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 17 | +3 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Staff | n/a | 23 | 12 | -11 |
| Staff 2 | n/a | 6 | 0 | -6 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 17 | +2 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 15 | 17 | +2 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Bain, Leslie M.`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Xiao, Xinli`
- **MATH 2914-003** room: `Corley 101` -> `Corley 103`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 2:00pm`
- **MATH 2924-003** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 2934-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-001** time: `T 9:30am` -> `T 2:30pm`
- **MATH 2934-001** time: `MWF 10:00am` -> `MWF 1:00pm`
- **MATH 2934-002** instructor: `Staff` -> `Overduin, Matthew D.`
- **MATH 2934-002** room: `Corley 101` -> `Corley 102`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 10:00am`
- **MATH 4123-001** room: `Corley 268` -> `Rothwell 207`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 10:00am`
- **MATH 4123-H01** room: `Corley 268` -> `Rothwell 207`
- **MATH 0903-001** instructor: `Staff 3` -> `King, Jamie L.`
- **MATH 1113-001** instructor: `Staff 3` -> `King, Jamie L.`
- **MATH 0903-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1113-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1110-003** instructor: `Growns, Landon C.` -> `Winn, Janet L.`
- **MATH 1113-003** instructor: `Growns, Landon C.` -> `Winn, Janet L.`
- **MATH 0803-004** instructor: `Staff 2` -> `Winn, Janet L.`
- **MATH 1003-004** instructor: `Staff 2` -> `Winn, Janet L.`
- **MATH 1003-005** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1003-005** time: `MWF 10:00am` -> `MWF 2:00pm`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Ballard, Kasey L.`
- **MATH 1113-006** instructor: `Taylor, Teresa L.` -> `Jordan, Susan M.`
- **MATH 1113-006** time: `TR 9:30am` -> `TR 2:30pm`
- **MATH 1113-006** room: `Corley 104` -> `Corley 101`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Taylor, Teresa L.`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Cox, Allie M.`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Jordan, Susan M.`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 101`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3033-001** time: `TR 11:00am` -> `TR 2:30pm`
- **MATH 4971-001** time: `T 11:00am` -> `W 12:00pm`
- **STAT 2163-001** instructor: `King, Jamie L.` -> `Bain, Leslie M.`
- **STAT 2163-TC1** instructor: `Bain, Leslie M.` -> `Yousuf, Marium`

## Remaining hard violations

- none

## Remaining soft findings

- [custom_rule] (30) MATH 2914-003: matches a custom dislike rule (weight 30)
- [custom_rule] (30) MATH 2914-003: matches a custom dislike rule (weight 30)
- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 0903-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-001: matches a custom dislike rule (weight 5)
