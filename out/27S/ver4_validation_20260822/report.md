# 27S ver4 solve report

Input: `work/27S/draft/starting.csv` (59 atomic classes, 80 rows)

Configuration version: `b23b6042112a`

Ran 1 independent attempt(s), each with a 20s CP-SAT budget. Selected attempt 1 by lowest worst instructor overload, then lowest reported soft solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -360
- Best objective bound: -1270
- Solve time: 20.0074 seconds
- Candidate assignments: 5629
- Hard violations: 0
- Soft penalty: 385 (5 findings)
- Worst instructor overload: 6 credit hours
- Remaining placeholder identities: Staff, Staff 2, Staff 3

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -360 | -1270 | 20.0074 | 385 | 6 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 0 | 0 |
| Soft penalty | 475 | 385 |
| Soft findings | 8 | 5 |
| Worst overload | 3 | 6 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 12 | -1 |
| Cox, Allie M. | 15 | 16 | 16 | +0 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 15 | 15 | +0 |
| Jordan, Susan M. | 15 | 14 | 21 | +7 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 13 | 14 | +1 |
| Overduin, Matthew D. | 12 | 9 | 6 | -3 |
| Staff | n/a | 25 | 22 | -3 |
| Staff 2 | n/a | 6 | 6 | +0 |
| Staff 3 | n/a | 4 | 4 | +0 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 15 | 4 | -11 |

## Changes from input

- **MATH 1113-F01** instructor: `Yousuf, Marium` -> `Taylor, Teresa L.`
- **MATH 1113-F01** time: `MWF 10:00am` -> `MWF 2:00pm`
- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-003** instructor: `Ballard, Kasey L.` -> `Cox, Allie M.`
- **MATH 1914-003** room: `Corley 102` -> `Corley 269`
- **MATH 1914-003** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Limperis, Thomas G.`
- **MATH 2914-003** time: `MWF 2:00pm` -> `MWF 10:00am`
- **MATH 2914-003** room: `Corley 101` -> `Corley 102`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Xiao, Xinli`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 8:00am`
- **MATH 2924-002** room: `Rothwell 206` -> `Corley 103`
- **MATH 2924-003** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 0803-001** instructor: `Winn, Janet L.` -> `King, Jamie L.`
- **MATH 1003-001** instructor: `Winn, Janet L.` -> `King, Jamie L.`
- **MATH 0803-002** instructor: `Growns, Landon C.` -> `Winn, Janet L.`
- **MATH 1003-002** instructor: `Growns, Landon C.` -> `Winn, Janet L.`
- **MATH 1003-005** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Growns, Landon C.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 11:00am`
- **MATH 1003-TC2** instructor: `King, Jamie L.` -> `Winn, Janet L.`
- **MATH 1113-006** instructor: `Taylor, Teresa L.` -> `Jordan, Susan M.`
- **MATH 1113-006** time: `TR 9:30am` -> `TR 8:00am`
- **MATH 1113-006** room: `Corley 104` -> `Corley 101`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Growns, Landon C.`
- **MATH 2243-001** instructor: `Overduin, Matthew D.` -> `Bain, Leslie M.`
- **MATH 2703-001** time: `MWF 10:00am` -> `MWF 2:00pm`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Jordan, Susan M.`
- **MATH 2703-002** time: `TR 11:00am` -> `TR 2:30pm`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 101`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Ballard, Kasey L.`
- **STAT 2163-002** time: `MWF 9:00am` -> `MWF 2:00pm`
- **MATH 1003-007** instructor: `Staff` -> `Growns, Landon C.`
- **MATH 1003-007** time: `MWF 1:00pm` -> `MWF 9:00am`
- **MATH 1003-007** room: `` -> `Corley 104`

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (100) Jordan, Scott M.: 15 credit hours exceeds max_load 12
- [overload] (100) Jordan, Susan M.: 21 credit hours exceeds max_load 15
- [under_load] (90) Overduin, Matthew D.: 6 credit hours is under max_load 12
- [under_load] (90) Yousuf, Marium: 4 credit hours is under max_load 15
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
