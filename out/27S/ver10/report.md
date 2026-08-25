# 27S ver10 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `d669fab0b281`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -725
- Best objective bound: -1760
- Solve time: 45.0103 seconds
- Candidate assignments: 5998
- Hard violations: 0
- Soft penalty: 5 (1 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -725 | -1760 | 45.0103 | 5 | 2 | 0 |
| 2 | feasible | -430 | -1770 | 45.0123 | 225 | 2 | 0 |
| 3 | feasible | -535 | -1830 | 45.0109 | 245 | 5 | 0 |
| 4 | feasible | -720 | -1730 | 45.0129 | 120 | 3 | 0 |
| 5 | feasible | -570 | -1765 | 45.0072 | 210 | 4 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 3 | 0 |
| Soft penalty | 520 | 5 |
| Soft findings | 10 | 1 |
| Worst overload | 1 | 2 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 16 | +1 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 17 | +3 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Staff | n/a | 23 | 15 | -8 |
| Staff 2 | n/a | 6 | 0 | -6 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 13 | +3 |
| Yousuf, Marium | 15 | 15 | 15 | +0 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 11:00am`
- **MATH 2914-002** instructor: `Jordan, Susan M.` -> `Bain, Leslie M.`
- **MATH 2914-002** time: `R 1:00pm` -> `T 2:30pm`
- **MATH 2914-002** room: `Corley 101` -> `Corley 267`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Overduin, Matthew D.`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 2:00pm`
- **MATH 2924-003** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 2934-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-002** instructor: `Staff` -> `Yousuf, Marium`
- **MATH 2934-002** room: `Corley 101` -> `Corley 268`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 268` -> `Rothwell 312`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 268` -> `Rothwell 312`
- **MATH 0903-001** instructor: `Staff 3` -> `Staff`
- **MATH 1113-001** instructor: `Staff 3` -> `Staff`
- **MATH 0903-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1113-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 0803-004** instructor: `Staff 2` -> `Winn, Janet L.`
- **MATH 1003-004** instructor: `Staff 2` -> `Winn, Janet L.`
- **MATH 1003-005** time: `MWF 10:00am` -> `MWF 2:00pm`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Jordan, Susan M.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 1:00pm`
- **MATH 1003-006** room: `Rothwell 221` -> `Corley 101`
- **MATH 1113-006** instructor: `Taylor, Teresa L.` -> `Jordan, Susan M.`
- **MATH 1113-006** time: `TR 9:30am` -> `TR 1:00pm`
- **MATH 1113-006** room: `Corley 104` -> `Corley 101`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Taylor, Teresa L.`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Cox, Allie M.`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Ballard, Kasey L.`
- **MATH 3123-001** time: `MWF 2:00pm` -> `MWF 8:00am`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 2:00pm`
- **STAT 2163-004** instructor: `Staff` -> `King, Jamie L.`
- **STAT 2163-004** room: `` -> `Corley 269`

## Remaining hard violations

- none

## Remaining soft findings

- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
