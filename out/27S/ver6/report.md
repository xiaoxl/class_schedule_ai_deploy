# 27S ver6 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `9ce9a12c7dc8`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 3 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -840
- Best objective bound: -2020
- Solve time: 45.0152 seconds
- Candidate assignments: 5998
- Hard violations: 0
- Soft penalty: 100 (3 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff, Staff 3

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -865 | -1865 | 45.0142 | 420 | 6 | 0 |
| 2 | feasible | -780 | -1885 | 45.0132 | 275 | 4 | 0 |
| 3 | feasible | -840 | -2020 | 45.0152 | 100 | 2 | 0 |
| 4 | feasible | -615 | -1805 | 45.0142 | 440 | 6 | 0 |
| 5 | feasible | -815 | -1815 | 45.0116 | 150 | 2 | 0 |

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
| Ballard, Kasey L. | 12 | 13 | 12 | -1 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 16 | +2 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 14 | +5 |
| Staff | n/a | 23 | 6 | -17 |
| Staff 2 | n/a | 6 | 0 | -6 |
| Staff 3 | n/a | 6 | 13 | +7 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 10 | +0 |
| Yousuf, Marium | 15 | 15 | 16 | +1 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 2:00pm`
- **MATH 1914-003** instructor: `Ballard, Kasey L.` -> `Jordan, Susan M.`
- **MATH 1914-003** time: `R 9:30am` -> `T 1:00pm`
- **MATH 1914-003** room: `Corley 102` -> `Corley 101`
- **MATH 1914-003** room: `Corley 268` -> `Corley 101`
- **MATH 2914-003** room: `Corley 101` -> `Corley 268`
- **MATH 2924-001** instructor: `Yousuf, Marium` -> `Overduin, Matthew D.`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Overduin, Matthew D.`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 11:00am`
- **MATH 2924-003** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 2934-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-002** instructor: `Staff` -> `Staff 3`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 268` -> `Rothwell 306`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 268` -> `Rothwell 306`
- **MATH 0903-001** instructor: `Staff 3` -> `Winn, Janet L.`
- **MATH 1113-001** instructor: `Staff 3` -> `Winn, Janet L.`
- **MATH 0903-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1113-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 0903-TC1** instructor: `Staff` -> `Staff 3`
- **MATH 1113-TC1** instructor: `Staff` -> `Staff 3`
- **MATH 0803-004** instructor: `Staff 2` -> `Staff`
- **MATH 0803-004** room: `Corley 267` -> `Corley 268`
- **MATH 1003-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-004** room: `Corley 267` -> `Corley 268`
- **MATH 1113-006** room: `Corley 104` -> `Corley 102`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Ballard, Kasey L.`
- **MATH 2243-001** instructor: `Overduin, Matthew D.` -> `Cox, Allie M.`
- **MATH 2703-001** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 2703-001** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 2703-001** room: `Corley 101` -> `Corley 267`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Yousuf, Marium`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 2:00pm`
- **MATH 1003-007** instructor: `Staff` -> `Staff 3`
- **MATH 1003-007** time: `MWF 1:00pm` -> `MWF 8:00am`
- **MATH 1003-007** room: `` -> `Rothwell 306`
- **STAT 2163-004** instructor: `Staff` -> `Bain, Leslie M.`
- **STAT 2163-004** room: `` -> `Corley 104`

## Remaining hard violations

- none

## Remaining soft findings

- [under_load] (90) Xiao, Xinli: 10 credit hours is under max_load 12
- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 0903-001: matches a custom dislike rule (weight 5)
