import datetime
import unittest

from class_schedule.class_model import CrossListingClass, NormalClass, Section
from class_schedule.schedule_model import (
    HAVETO,
    PreferenceRecord,
    PreferenceRule,
    Schedule,
    check_conflicts,
)
from class_schedule.solver import NoFeasibleSchedule, MeetingPattern, RoomRecord, SolverConfig, solve


def make_section(**overrides) -> Section:
    defaults = dict(
        subject="MATH",
        number="1113",
        section="001",
        time_slot="MWF 9:00am",
        duration=50,
        room="101",
        instructor="Alice",
        building="Corley",
    )
    defaults.update(overrides)
    return Section(**defaults)


def empty_config(**overrides) -> SolverConfig:
    defaults = dict(persons={}, preferences={}, meeting_patterns=[], rooms=[], blackouts=[])
    defaults.update(overrides)
    return SolverConfig(**defaults)


class SolveResolvesConflictsTests(unittest.TestCase):
    def test_shifts_one_class_to_an_alternate_time_to_clear_a_real_conflict(self):
        a = NormalClass((make_section(number="1113", section="001"),))
        b = NormalClass((make_section(number="2103", section="002"),))
        schedule = Schedule([a, b])
        self.assertNotEqual(check_conflicts(schedule), [])  # sanity: input really conflicts

        config = empty_config(
            meeting_patterns=[
                MeetingPattern(
                    days="MWF", duration_minutes=50,
                    starts=(datetime.time(9, 0), datetime.time(10, 0)),
                    types=frozenset({"standard"}),
                )
            ],
            rooms=[RoomRecord(building="Corley", room="101")],
        )
        solved = solve(schedule, config, time_limit_seconds=10.0)
        self.assertEqual(check_conflicts(solved), [])


class SolveRaisesWhenInfeasibleTests(unittest.TestCase):
    def test_raises_when_the_only_candidates_force_a_conflict(self):
        # An empty config gives every section exactly one candidate: its
        # own current (instructor, time, room) -- with no alternative to
        # move to, two classes forced onto the same instructor/room/time
        # have no conflict-free assignment at all.
        a = NormalClass((make_section(number="1113", section="001"),))
        b = NormalClass((make_section(number="2103", section="002"),))
        schedule = Schedule([a, b])
        with self.assertRaises(NoFeasibleSchedule):
            solve(schedule, empty_config(), time_limit_seconds=10.0)


class SolveExemptsAClasssOwnSectionsTests(unittest.TestCase):
    def test_does_not_treat_an_honors_pairs_own_two_sections_as_a_conflict(self):
        # Same room/time/instructor by design (see
        # CrossListingClass.is_honors_pair) -- must not be rejected as a
        # self-conflict, even when (as with an empty config) that shared
        # position is each section's *only* candidate.
        left = make_section(section="001", instructor="Alice", room="101")
        right = make_section(section="H01", instructor="Alice", room="101")
        honors = CrossListingClass((left, right))
        schedule = Schedule([honors])
        solved = solve(schedule, empty_config(), time_limit_seconds=10.0)
        self.assertEqual(check_conflicts(solved), [])


class SolveHonorsPreferenceRulesTests(unittest.TestCase):
    def test_moves_a_class_into_a_haveto_preferred_room(self):
        section = make_section(room="101", building="Corley")
        schedule = Schedule([NormalClass((section,))])
        config = empty_config(
            rooms=[
                RoomRecord(building="Corley", room="101"),
                RoomRecord(building="Corley", room="269"),
            ],
            preferences={"Alice": PreferenceRecord(
                name="Alice",
                rules=(PreferenceRule(room="Corley 269", direction="prefer", weight=HAVETO),),
            )},
        )
        solved = solve(schedule, config, time_limit_seconds=10.0)
        solved_section = solved.classes[0].sections[0]
        self.assertEqual(
            f"{solved_section.building} {solved_section.room}".strip(), "Corley 269"
        )

    def test_a_global_rule_applies_even_without_a_preferences_entry(self):
        # No PreferenceRecord for "Alice" at all -- only a top-level rule,
        # scoped to the course/section rather than any instructor.
        section = make_section(
            subject="MATH", number="1113", section="F01", room="101", building="Corley",
        )
        schedule = Schedule([NormalClass((section,))])
        config = empty_config(
            rooms=[
                RoomRecord(building="Corley", room="101"),
                RoomRecord(building="Corley", room="269"),
            ],
            global_rules=(
                PreferenceRule(
                    course="MATH 1113", section="F01", room="Corley 269",
                    direction="prefer", weight=HAVETO,
                ),
            ),
        )
        solved = solve(schedule, config, time_limit_seconds=10.0)
        solved_section = solved.classes[0].sections[0]
        self.assertEqual(
            f"{solved_section.building} {solved_section.room}".strip(), "Corley 269"
        )


if __name__ == "__main__":
    unittest.main()
