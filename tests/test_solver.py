import datetime
import tempfile
import unittest
from pathlib import Path

from class_schedule.class_model import (
    CrossListingClass,
    FourCreditClass,
    NormalClass,
    Section,
)
from class_schedule.config_schema import (
    NewInstructorPolicySchema,
    NewProfessorPolicySchema,
)
from class_schedule.schedule_model import (
    ConstraintRule,
    PersonRecord,
    PreferenceRecord,
    PreferenceRule,
    Schedule,
    TimeWindow,
    check_conflicts,
    evaluate_schedule,
    teaching_loads,
)
from class_schedule.solver import NoFeasibleSchedule, MeetingPattern, RoomRecord, SolverConfig, solve
from class_schedule.solver.candidates import preference_cost
from class_schedule.solver.config import load_constraint_rules


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
    defaults = dict(persons={}, preferences={}, meeting_patterns=[], rooms=[])
    defaults.update(overrides)
    return SolverConfig(**defaults)


class NamedPreferenceCostTests(unittest.TestCase):
    def test_matching_preferred_fields_reward_the_candidate(self):
        preference = PreferenceRecord(
            name="Alice",
            rules=(
                PreferenceRule(time=TimeWindow(
                    frozenset("MWF"), datetime.time(8), datetime.time(10),
                ), direction="prefer", weight=7),
                PreferenceRule(room="Corley", direction="prefer", weight=11),
                PreferenceRule(course="MATH 1113", direction="prefer", weight=13),
            ),
        )
        cost = preference_cost(
            "Alice", "MWF", datetime.time(9), datetime.time(9, 50),
            "Corley", "101", "MATH 1113", "001", {"Alice": preference},
        )
        self.assertEqual(cost, -31.0)

    def test_nonmatching_preferred_fields_do_not_change_cost(self):
        preference = PreferenceRecord(
            name="Alice",
            rules=(
                PreferenceRule(time=TimeWindow(
                    frozenset("TR"), datetime.time(13), datetime.time(15),
                ), direction="prefer", weight=7),
                PreferenceRule(room="Rothwell", direction="prefer", weight=11),
                PreferenceRule(course="MATH 2934", direction="prefer", weight=13),
            ),
        )
        cost = preference_cost(
            "Alice", "MWF", datetime.time(9), datetime.time(9, 50),
            "Corley", "101", "MATH 1113", "001", {"Alice": preference},
        )
        self.assertEqual(cost, 0.0)


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
                    roles=frozenset({"normal"}),
                )
            ],
            rooms=[RoomRecord(building="Corley", room="101")],
        )
        solved = solve(schedule, config, time_limit_seconds=10.0)
        self.assertEqual(check_conflicts(solved), [])

    def test_four_credit_candidates_repair_a_large_start_difference(self):
        item = FourCreditClass((
            make_section(
                number="1914", section="001", time_slot="MWF 8:00am",
                duration=50,
            ),
            make_section(
                number="1914", section="001", time_slot="T 2:30pm",
                duration=80,
            ),
        ))
        config = empty_config(
            meeting_patterns=[
                MeetingPattern(
                    days="MWF", duration_minutes=50,
                    starts=(datetime.time(8),),
                    roles=frozenset({"four_credit_primary"}),
                ),
                MeetingPattern(
                    days="T", duration_minutes=80,
                    starts=(datetime.time(8), datetime.time(14, 30)),
                    roles=frozenset({"four_credit_partial"}),
                ),
            ],
            rooms=[RoomRecord(building="Corley", room="101")],
        )

        solved = solve(Schedule([item]), config, time_limit_seconds=10.0)
        result = solved.classes[0]

        self.assertIsInstance(result, FourCreditClass)
        self.assertEqual(result.validation_report(), ())
        self.assertLessEqual(
            FourCreditClass.start_difference_minutes(*result.sections), 90
        )


class ConstraintRuleTests(unittest.TestCase):
    def test_constraint_file_uses_preference_selector_syntax(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "constraints.toml"
            path.write_text(
                '[[rules]]\n'
                'direction = "+"\n'
                'name = "Bob"\n'
                'course = "MATH 2103"\n'
                'section_prefix = "TC"\n'
                'room = ["Corley 101", "Corley 269"]\n'
                'time = "8-12"\n',
                encoding="utf-8",
            )
            rule, = load_constraint_rules(path)

        self.assertEqual(rule.name, "Bob")
        self.assertEqual(rule.direction, "+")
        self.assertEqual(rule.course, "MATH 2103")
        self.assertEqual(rule.section_prefix, "TC")
        self.assertEqual(rule.rooms, ("Corley 101", "Corley 269"))
        self.assertTrue(rule.time.overlaps(
            "MWF", datetime.time(9), datetime.time(9, 50)
        ))

    def test_negative_constraint_forbids_only_the_matching_combination(self):
        rule = ConstraintRule(
            direction="-", name="Bob", room="Corley 269",
        )

        def allowed(instructor, room):
            return rule.allows(
                instructor=instructor, building="Corley", room=room,
                days="MWF", start=datetime.time(9),
                end=datetime.time(9, 50), is_online=False,
            )

        self.assertFalse(allowed("Bob", "269"))
        self.assertTrue(allowed("Bob", "101"))
        self.assertTrue(allowed("Alice", "269"))

    def test_constraint_instructor_is_the_only_solver_candidate(self):
        section = make_section(
            number="2103", instructor="Staff", room="101",
        )
        config = empty_config(
            persons={
                "Alice": PersonRecord(
                    name="Alice", max_load=15, courses=("MATH 2103",),
                ),
                "Bob": PersonRecord(
                    name="Bob", max_load=15, courses=("MATH 2103",),
                ),
            },
            constraint_rules=(ConstraintRule(
                name="Bob", course="MATH 2103",
            ),),
        )

        solved = solve(
            Schedule([NormalClass((section,))]), config,
            time_limit_seconds=10.0,
        )

        self.assertEqual(
            solved.get("MATH 2103-001").sections[0].instructor, "Bob"
        )

    def test_constraint_instructor_is_a_hard_validation_rule(self):
        schedule = Schedule([NormalClass((make_section(
            number="2103", instructor="Alice",
        ),))])

        evaluation = evaluate_schedule(
            schedule, {}, {}, constraint_rules=(ConstraintRule(
                name="Bob", course="MATH 2103",
            ),),
        )

        self.assertEqual(len(evaluation.hard_violations), 1)
        self.assertEqual(
            evaluation.hard_violations[0].rule, "constraint_positive"
        )

    def test_production_constraint_is_loaded(self):
        config = SolverConfig.load(
            Path(__file__).parents[1] / "config", package="27S"
        )
        room_rule = next(
            rule for rule in config.constraints_for("MATH 1113", "F01")
            if rule.room is not None
        )
        instructor_rule = next(
            rule for rule in config.constraints_for("MATH 4123", "001")
            if rule.name is not None
        )
        self.assertEqual(room_rule.rooms, ("Corley 269",))
        self.assertEqual(instructor_rule.name, "Limperis, Thomas G.")

    def test_constraint_room_is_the_only_solver_room_candidate(self):
        section = make_section(section="F01", room="101")
        config = empty_config(
            meeting_patterns=[MeetingPattern(
                days="MWF", duration_minutes=50,
                starts=(datetime.time(9),), roles=frozenset({"normal"}),
            )],
            rooms=[
                RoomRecord(building="Corley", room="101"),
                RoomRecord(building="Corley", room="269"),
            ],
            constraint_rules=(ConstraintRule(
                course="MATH 1113", section="F01",
                room=("Corley 269",),
            ),),
        )

        solved = solve(
            Schedule([NormalClass((section,))]), config,
            time_limit_seconds=10.0,
        )

        result = solved.get("MATH 1113-F01").sections[0]
        self.assertEqual((result.building, result.room), ("Corley", "269"))

    def test_one_constraint_rule_can_require_instructor_and_room(self):
        section = make_section(
            number="2103", instructor="Staff", room="101",
        )
        config = empty_config(
            persons={
                "Bob": PersonRecord(
                    name="Bob", max_load=15, courses=("MATH 2103",),
                ),
            },
            meeting_patterns=[MeetingPattern(
                days="MWF", duration_minutes=50,
                starts=(datetime.time(9),), roles=frozenset({"normal"}),
            )],
            rooms=[
                RoomRecord(building="Corley", room="101"),
                RoomRecord(building="Corley", room="269"),
            ],
            constraint_rules=(ConstraintRule(
                name="Bob", course="MATH 2103",
                room=("Corley 269",),
            ),),
        )

        solved = solve(
            Schedule([NormalClass((section,))]), config,
            time_limit_seconds=10.0,
        )

        result = solved.get("MATH 2103-001").sections[0]
        self.assertEqual(result.instructor, "Bob")
        self.assertEqual((result.building, result.room), ("Corley", "269"))

    def test_constraint_room_is_a_hard_validation_rule(self):
        schedule = Schedule([NormalClass((make_section(
            section="F01", room="101",
        ),))])

        evaluation = evaluate_schedule(
            schedule, {}, {}, constraint_rules=(ConstraintRule(
                course="MATH 1113", section="F01",
                room=("Corley 269",),
            ),),
        )

        self.assertEqual(len(evaluation.hard_violations), 1)
        self.assertEqual(
            evaluation.hard_violations[0].rule, "constraint_positive"
        )


class SolveAdjustsPlaceholderCountTests(unittest.TestCase):
    def test_zero_allowed_professors_disables_that_pool(self):
        item = NormalClass((make_section(
            number="2914", instructor="Staff", credits=4,
        ),))
        config = empty_config(
            persons={"Bob": PersonRecord(
                name="Bob", max_load=12, courses=("MATH 2914",),
            )},
            new_professor_policy=NewProfessorPolicySchema(allowed_counts=[0]),
        )

        solved = solve(Schedule([item]), config, time_limit_seconds=10.0)

        self.assertEqual(solved.classes[0].sections[0].instructor, "Bob")

    def test_one_allowed_professor_requires_exactly_one(self):
        item = NormalClass((make_section(
            number="2914", instructor="Bob", credits=4,
        ),))
        config = empty_config(
            persons={"Bob": PersonRecord(
                name="Bob", max_load=12, courses=("MATH 2914",),
            )},
            new_instructor_policy=NewInstructorPolicySchema(allowed_counts=[0]),
            new_professor_policy=NewProfessorPolicySchema(allowed_counts=[1]),
        )

        solved = solve(Schedule([item]), config, time_limit_seconds=10.0)

        self.assertEqual(solved.classes[0].sections[0].instructor, "new_professor")

    def test_uses_dynamic_professor_for_course_above_instructor_limit(self):
        item = NormalClass((make_section(
            number="2914", instructor="Staff", credits=4,
        ),))

        solved = solve(Schedule([item]), empty_config(), time_limit_seconds=10.0)

        self.assertEqual(
            solved.get("MATH 2914-001").sections[0].instructor,
            "new_professor",
        )

    def test_adds_and_numbers_professors_only_when_concurrency_requires_it(self):
        a = NormalClass((make_section(
            number="2914", section="001", instructor="Staff", room="101",
            credits=4,
        ),))
        b = NormalClass((make_section(
            number="2924", section="002", instructor="Staff", room="102",
            credits=4,
        ),))

        solved = solve(Schedule([a, b]), empty_config(), time_limit_seconds=10.0)

        self.assertEqual(
            {s.instructor for item in solved.classes for s in item.sections},
            {"new_professor", "new_professor 2"},
        )

    def test_staff_credit_cost_assigns_a_qualified_named_instructor(self):
        item = NormalClass((make_section(
            number="1113", instructor="Staff",
        ),))
        config = empty_config(
            persons={
                "Bob": PersonRecord(
                    name="Bob", max_load=0, courses=("MATH 1113",),
                ),
            },
            staff_count_weight=0,
            staff_credit_weight=30,
        )

        solved = solve(Schedule([item]), config, time_limit_seconds=10.0)

        self.assertEqual(
            solved.get("MATH 1113-001").sections[0].instructor, "Bob"
        )

    def test_keeps_staff_when_assignment_would_exceed_load_tolerance(self):
        fixed = NormalClass((make_section(
            number="1005", section="001", instructor="Bob", credits=5,
        ),))
        open_class = NormalClass((make_section(
            number="1113", section="002", instructor="Staff", credits=3,
            time_slot="MWF 10:00am", room="102",
        ),))
        config = empty_config(
            persons={
                "Bob": PersonRecord(
                    name="Bob", max_load=3,
                    courses=("MATH 1005", "MATH 1113"),
                ),
            },
            preferences={
                "Bob": PreferenceRecord(name="Bob", allow_overload=True),
            },
            staff_count_weight=10,
            staff_credit_weight=5,
        )

        solved = solve(
            Schedule([fixed, open_class]), time_limit_seconds=10.0,
            config=config,
        )

        self.assertEqual(
            solved.get("MATH 1113-002").sections[0].instructor, "new_instructor"
        )

    def test_collapses_numbered_staff_when_times_do_not_conflict(self):
        a = NormalClass((make_section(
            number="1113", section="001", instructor="Staff",
            time_slot="MWF 9:00am", room="101",
        ),))
        b = NormalClass((make_section(
            number="2103", section="002", instructor="Staff 2",
            time_slot="MWF 10:00am", room="102",
        ),))
        solved = solve(Schedule([a, b]), empty_config(), time_limit_seconds=10.0)
        self.assertEqual(
            {s.instructor for item in solved.classes for s in item.sections},
            {"new_instructor"},
        )

    def test_adds_numbered_staff_for_overlapping_placeholder_courses(self):
        a = NormalClass((make_section(
            number="1113", section="001", instructor="Staff", room="101",
        ),))
        b = NormalClass((make_section(
            number="2103", section="002", instructor="Staff", room="102",
        ),))
        solved = solve(Schedule([a, b]), empty_config(), time_limit_seconds=10.0)
        instructors = {
            s.instructor for item in solved.classes for s in item.sections
        }
        self.assertEqual(instructors, {"new_instructor", "new_instructor 2"})
        self.assertEqual(check_conflicts(solved), [])

    def test_global_staff_cost_moves_time_to_use_one_identity(self):
        a = NormalClass((make_section(
            number="1113", section="001", instructor="Staff",
            time_slot="MWF 9:00am", room="101",
        ),))
        b = NormalClass((make_section(
            number="2103", section="002", instructor="Staff",
            time_slot="MWF 9:00am", room="102",
        ),))
        config = empty_config(
            meeting_patterns=[MeetingPattern(
                days="MWF", duration_minutes=50,
                starts=(datetime.time(9), datetime.time(10)),
                roles=frozenset({"normal"}),
            )],
            rooms=[
                RoomRecord(building="Corley", room="101"),
                RoomRecord(building="Corley", room="102"),
            ],
            staff_count_weight=100,
        )

        solved = solve(Schedule([a, b]), config, time_limit_seconds=10.0)

        sections = [section for item in solved for section in item.sections]
        self.assertEqual(
            {section.instructor for section in sections}, {"new_instructor"}
        )
        self.assertEqual({section.start for section in sections}, {
            datetime.time(9), datetime.time(10),
        })


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

    def test_cross_listing_counts_once_in_solver_result_load(self):
        left = make_section(
            subject="MATH", number="5173", section="TC1",
            instructor="Alice", time_slot="TBA", duration=None, room="",
        )
        right = make_section(
            subject="STAT", number="4173", section="TC1",
            instructor="Alice", time_slot="TBA", duration=None, room="",
        )
        left.cross_list = right.cross_list = "advanced_biostatistics"
        schedule = Schedule([CrossListingClass((left, right))])
        solved = solve(schedule, empty_config(), time_limit_seconds=10.0)
        self.assertEqual(teaching_loads(solved)["Alice"], 3)


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
                rules=(PreferenceRule(room="Corley 269", direction="prefer", weight=100),),
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
                    direction="prefer", weight=100,
                ),
            ),
        )
        solved = solve(schedule, config, time_limit_seconds=10.0)
        solved_section = solved.classes[0].sections[0]
        self.assertEqual(
            f"{solved_section.building} {solved_section.room}".strip(), "Corley 269"
        )


class SolveTcWebPreferenceTests(unittest.TestCase):
    def test_avoids_instructor_who_dislikes_tc_section(self):
        # Bob is double-booked (same instructor, overlapping time) --
        # only MATH 1113 has another qualified instructor, so resolving
        # the conflict means reassigning it away from Bob to whichever of
        # Alice/Carol the solver picks. Alice dislikes TC sections, Carol has
        # no preference; both cost the same INSTRUCTOR_CHANGE_COST, so
        # Alice's configured TC penalty (for landing on this TC-labeled
        # section) should make Carol the strictly cheaper pick.
        moved = make_section(
            subject="MATH", number="1113", section="TC1", instructor="Bob", room="101",
        )
        conflicting = make_section(
            subject="MATH", number="2103", section="002", instructor="Bob", room="102",
        )
        schedule = Schedule([NormalClass((moved,)), NormalClass((conflicting,))])
        config = empty_config(
            persons={
                "Bob": PersonRecord(name="Bob", max_load=15, courses=["MATH 2103"]),
                "Alice": PersonRecord(name="Alice", max_load=15, courses=["MATH 1113"]),
                "Carol": PersonRecord(name="Carol", max_load=15, courses=["MATH 1113"]),
            },
            preferences={
                "Alice": PreferenceRecord(
                    name="Alice",
                    rules=(PreferenceRule(
                        section_prefix="TC", direction="dislike", weight=5,
                    ),),
                ),
                "Carol": PreferenceRecord(name="Carol"),
            },
        )
        solved = solve(schedule, config, time_limit_seconds=10.0)
        self.assertEqual(check_conflicts(solved), [])
        self.assertEqual(solved.get("MATH 1113-TC1").sections[0].instructor, "Carol")


class SolveMaxBackToBackTests(unittest.TestCase):
    def test_moves_a_class_to_break_an_over_cap_back_to_back_chain(self):
        a = make_section(number="1113", section="001", instructor="Alice", room="101", time_slot="MWF 9:00am", duration=50)
        b = make_section(number="1003", section="001", instructor="Alice", room="101", time_slot="MWF 9:50am", duration=50)
        c = make_section(number="2914", section="001", instructor="Alice", room="101", time_slot="MWF 10:40am", duration=50)
        schedule = Schedule([NormalClass((a,)), NormalClass((b,)), NormalClass((c,))])
        config = empty_config(
            meeting_patterns=[
                MeetingPattern(
                    days="MWF", duration_minutes=50,
                    starts=(
                        datetime.time(9, 0), datetime.time(9, 50),
                        datetime.time(10, 40), datetime.time(13, 0),
                    ),
                    roles=frozenset({"normal"}),
                )
            ],
            rooms=[RoomRecord(building="Corley", room="101")],
            preferences={"Alice": PreferenceRecord(
                name="Alice", allow_back_to_back=True, max_back_to_back=2,
            )},
        )
        solved = solve(schedule, config, time_limit_seconds=15.0)
        self.assertEqual(check_conflicts(solved), [])
        starts = sorted(item.sections[0].start for item in solved.classes)
        self.assertNotEqual(
            starts, [datetime.time(9, 0), datetime.time(9, 50), datetime.time(10, 40)],
        )


if __name__ == "__main__":
    unittest.main()
