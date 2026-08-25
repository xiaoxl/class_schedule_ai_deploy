# Configuration

Configuration lives under `config/`. Term-specific files override flat defaults. Unknown fields are rejected so mistakes cannot silently alter solver behavior.

## People and preferences

Person records define names, qualified courses, and contract load. Preferences control availability, preferred or disliked combinations, overload policy, and back-to-back behavior.

New Instructor identities are dynamic and need no individual person record. Each has a 15-credit contract, may teach numeric course numbers below `2703`, and may teach back-to-back.

Preference rules use selectors such as course, section, section prefix, room, and time. Positive weights reward matches; negative weights penalize them. Named rules apply to one instructor; unnamed rules are global.

## Rooms and meeting patterns

Rooms preserve building and room as separate values. Meeting patterns define legal days, durations, starts, and structural roles. Course-specific patterns replace generic patterns for that course. Exceptional seminars should have explicit patterns.

## Constraints and term changes

Constraints are hard requirements that can require or forbid instructor, physical room, time, and course combinations. Term changes describe cancellations, departures, and new sections. New physical sections must match a configured meeting pattern before publication.

The CLI supports time limits, attempts, random seeds, and worker counts. Configuration files used for publication are hashed in the version manifest.
