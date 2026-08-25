# 27S ver11 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `f8999ff1ca54`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 4 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -630
- Best objective bound: -1785
- Solve time: 45.0067 seconds
- Candidate assignments: 6120
- Hard violations: 0
- Soft penalty: 55 (5 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -665 | -1575 | 45.0084 | 380 | 6 | 0 |
| 2 | feasible | -755 | -1780 | 45.0111 | 20 | 3 | 0 |
| 3 | feasible | -500 | -1775 | 45.0111 | 365 | 6 | 0 |
| 4 | feasible | -630 | -1785 | 45.0067 | 55 | 2 | 0 |
| 5 | feasible | -680 | -1790 | 45.0095 | 110 | 3 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 3 | 0 |
| Soft penalty | 520 | 55 |
| Soft findings | 10 | 5 |
| Worst overload | 1 | 2 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 16 | +1 |
| Ballard, Kasey L. | 12 | 13 | 12 | -1 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 16 | +5 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 15 | +1 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 23 | 15 | -8 |
| Staff 2 | n/a | 6 | 0 | -6 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 17 | +2 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 15 | 17 | +2 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 1914-003** instructor: `Ballard, Kasey L.` -> `Bain, Leslie M.`
- **MATH 2914-001** instructor: `Jordan, Susan M.` -> `Growns, Landon C.`
- **MATH 2914-001** time: `MWF 9:00am` -> `MWF 8:00am`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Jordan, Susan M.`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Limperis, Thomas G.`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 1:00pm`
- **MATH 2924-003** room: `Rothwell 206` -> `Rothwell 306`
- **MATH 2934-001** instructor: `Staff` -> `Xiao, Xinli`
- **MATH 2934-002** instructor: `Staff` -> `Yousuf, Marium`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 268` -> `Rothwell 312`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 268` -> `Rothwell 312`
- **MATH 0803-001** instructor: `Winn, Janet L.` -> `King, Jamie L.`
- **MATH 1003-001** instructor: `Winn, Janet L.` -> `King, Jamie L.`
- **MATH 0803-003** room: `Corley 103` -> `Corley 267`
- **MATH 1003-003** room: `Corley 103` -> `Corley 267`
- **MATH 0903-001** instructor: `Staff 3` -> `Staff`
- **MATH 1113-001** instructor: `Staff 3` -> `Staff`
- **MATH 0903-TC1** instructor: `Staff` -> `Growns, Landon C.`
- **MATH 1113-TC1** instructor: `Staff` -> `Growns, Landon C.`
- **MATH 1110-003** instructor: `Growns, Landon C.` -> `Winn, Janet L.`
- **MATH 1113-003** instructor: `Growns, Landon C.` -> `Winn, Janet L.`
- **MATH 0803-004** instructor: `Staff 2` -> `Staff`
- **MATH 0803-004** time: `MWF 11:00am` -> `MWF 9:00am`
- **MATH 1003-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Winn, Janet L.`
- **MATH 1003-TC2** instructor: `King, Jamie L.` -> `Ballard, Kasey L.`
- **MATH 1113-006** time: `TR 9:30am` -> `TR 8:00am`
- **MATH 1113-006** room: `Corley 104` -> `Corley 102`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Cox, Allie M.`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Ballard, Kasey L.`
- **MATH 3243-001** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Overduin, Matthew D.`
- **STAT 2163-TC1** instructor: `Bain, Leslie M.` -> `Yousuf, Marium`
- **STAT 2163-004** instructor: `Staff` -> `Yousuf, Marium`
- **STAT 2163-004** room: `` -> `Rothwell 312`

## Remaining hard violations

- none

## Remaining soft findings

- [custom_rule] (20) MATH 2934-001: matches a custom dislike rule (weight 20)
- [custom_rule] (20) MATH 2934-001: matches a custom dislike rule (weight 20)
- [custom_rule] (5) MATH 0903-002: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
