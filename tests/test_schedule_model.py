import datetime
import unittest

from class_schedule.class_model import (
    CoreqClass, CrossListingClass, FourCreditClass, HybridClass, NormalClass, Section,
)
from class_schedule.config_schema import NewInstructorPolicySchema, NewProfessorPolicySchema
from class_schedule.instructor_identity import new_instructor_name, new_professor_name
from class_schedule.schedule_model import (
    ConstraintRule,
    GroupingError,
    PersonRecord,
    PreferenceRecord,
    Schedule,
    TimeWindow,
    check_atomic_class_rules,
    check_conflicts,
    check_new_hire_counts,
    check_soft_preferences,
    check_workload_hard_caps,
    evaluate_schedule,
    teaching_loads,
)
from class_schedule.solver import MeetingPattern


def make_record(**overrides) -> dict:
    defaults = dict(
        Subject="MATH",
        Number="1113",
        Section="001",
        **{"Time Slot": "MWF 9:00am"},
        Duration=50,
        Room="101",
        Building="Corley",
        Instructor="Alice",
    )
    defaults.update(overrides)
    return defaults


def make_section(**overrides) -> Section:
    record = make_record(**overrides)
    return Section.from_record(record)


class CheckConflictsTests(unittest.TestCase):
    def test_same_room_overlapping_time_is_room_conflict(self):
        a = NormalClass((make_section(Number="1113", Section="001", Room="101"),))
        b = NormalClass((make_section(Number="2103", Section="002", Room="101", Instructor="Bob"),))
        violations = check_conflicts(Schedule([a, b]))
        conflict = next(v for v in violations if v.rule == "room_conflict")
        # References must point at both classes involved, each at its
        # own class_index/record_index -- room_conflict is the case that
        # never mapped onto the old subject-string scheme at all (subject
        # here is a room label, not a course id).
        self.assertEqual(
            {(r.class_index, r.record_index, r.course_id) for r in conflict.references},
            {(0, 0, "MATH 1113-001"), (1, 0, "MATH 2103-002")},
        )

    def test_same_instructor_overlapping_time_is_instructor_conflict(self):
        a = NormalClass((make_section(Number="1113", Section="001", Instructor="Alice", Room="101"),))
        b = NormalClass((make_section(Number="2103", Section="002", Instructor="Alice", Room="102"),))
        violations = check_conflicts(Schedule([a, b]))
        conflict = next(v for v in violations if v.rule == "instructor_conflict")
        self.assertEqual(
            {(r.class_index, r.record_index, r.course_id) for r in conflict.references},
            {(0, 0, "MATH 1113-001"), (1, 0, "MATH 2103-002")},
        )

    def test_non_overlapping_time_is_no_conflict(self):
        a = NormalClass((make_section(**{"Time Slot": "MWF 9:00am"}, Room="101", Instructor="Alice"),))
        b = NormalClass((make_section(**{"Time Slot": "MWF 10:00am"}, Room="101", Instructor="Alice"),))
        self.assertEqual(check_conflicts(Schedule([a, b])), [])

    def test_a_classs_own_two_rows_are_never_compared(self):
        # Honors pair: same time/room/instructor by design -- must never
        # be reported as a conflict against itself.
        left = make_section(Section="001", Instructor="Alice", Room="101")
        right = make_section(Section="H01", Instructor="Alice", Room="101")
        honors = CrossListingClass((left, right))
        self.assertEqual(check_conflicts(Schedule([honors])), [])

    def test_different_rooms_overlapping_time_different_instructors_is_no_conflict(self):
        a = NormalClass((make_section(Room="101", Instructor="Alice"),))
        b = NormalClass((make_section(Number="2103", Section="002", Room="102", Instructor="Bob"),))
        self.assertEqual(check_conflicts(Schedule([a, b])), [])


class EvaluateConstraintTimeTests(unittest.TestCase):
    def test_negative_time_rule_overlap_is_a_hard_violation(self):
        schedule = Schedule([NormalClass((make_section(
            **{"Time Slot": "MWF 12:00pm"}, Room="101", Instructor="Alice"
        ),))])
        evaluation = evaluate_schedule(
            schedule, {}, {}, constraint_rules=(ConstraintRule(
                direction="-", time=TimeWindow(
                frozenset("F"),
                datetime.time(12),
                datetime.time(12, 50),
                "Friday noon",
                ),
            ),),
        )
        self.assertEqual(len(evaluation.hard_violations), 1)
        self.assertEqual(
            evaluation.hard_violations[0].rule, "constraint_negative"
        )

    def test_mw_noon_does_not_match_a_friday_negative_time_rule(self):
        schedule = Schedule([NormalClass((make_section(
            **{"Time Slot": "MW 12:00pm"}, Room="101", Instructor="Alice"
        ),))])
        evaluation = evaluate_schedule(
            schedule, {}, {}, constraint_rules=(ConstraintRule(
                direction="-", time=TimeWindow(
                frozenset("F"),
                datetime.time(12),
                datetime.time(12, 50),
                "Friday noon",
                ),
            ),),
        )
        self.assertEqual(evaluation.hard_violations, ())


class EvaluateMeetingPatternTests(unittest.TestCase):
    def test_unconfigured_physical_pattern_is_a_hard_violation(self):
        schedule = Schedule([NormalClass((make_section(
            **{"Time Slot": "MW 12:00pm"}, Room="101", Instructor="Alice"
        ),))])
        evaluation = evaluate_schedule(
            schedule, {}, {}, meeting_patterns=(MeetingPattern(
                "MWF", 50, (datetime.time(11),), frozenset({"normal"})
            ),),
        )
        self.assertEqual(len(evaluation.hard_violations), 1)
        self.assertEqual(
            evaluation.hard_violations[0].rule, "meeting_pattern"
        )

    def test_configured_physical_pattern_is_valid(self):
        schedule = Schedule([NormalClass((make_section(
            **{"Time Slot": "MWF 11:00am"}, Room="101", Instructor="Alice"
        ),))])
        evaluation = evaluate_schedule(
            schedule, {}, {}, meeting_patterns=(MeetingPattern(
                "MWF", 50, (datetime.time(11),), frozenset({"normal"})
            ),),
        )
        self.assertEqual(evaluation.hard_violations, ())


class EvaluateFourCreditTests(unittest.TestCase):
    def test_large_start_difference_is_a_nonfatal_construction_violation(self):
        item = FourCreditClass((
            make_section(**{"Time Slot": "MWF 8:00am"}),
            make_section(**{"Time Slot": "T 1:00pm"}, Duration=80),
        ))

        evaluation = evaluate_schedule(Schedule([item]), {}, {})

        self.assertEqual(len(evaluation.hard_violations), 1)
        violation = evaluation.hard_violations[0]
        self.assertEqual(violation.rule, "four_credit_invalid")
        # Both rows share one course_id (same course/section, only the
        # weekday pattern differs) -- references must still tell them
        # apart by record_index, or a web client can't know which block
        # to highlight (see docs/codes.md).
        self.assertEqual(
            {(r.class_index, r.record_index) for r in violation.references},
            {(0, 0), (0, 1)},
        )
        self.assertTrue(all(r.course_id == "MATH 1113-001" for r in violation.references))


class EvaluateCoreqTests(unittest.TestCase):
    def test_both_linked_courses_are_referenced_not_just_the_first(self):
        # CoreqClass links two *different* courses (unlike FourCredit) --
        # check_atomic_class_rules used to report only item.course_ids[0],
        # silently dropping the second course from a Coreq violation (see
        # docs/codes.md).
        item = CoreqClass((
            make_section(Number="0903", Section="001", Instructor="Alice"),
            make_section(Number="1113", Section="001", Instructor="Bob"),
        ))

        violations = check_atomic_class_rules(Schedule([item]))

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].rule, "coreq_invalid")
        self.assertEqual(
            {(r.class_index, r.record_index, r.course_id) for r in violations[0].references},
            {(0, 0, "MATH 0903-001"), (0, 1, "MATH 1113-001")},
        )


class EvaluateHybridShapeTests(unittest.TestCase):
    def test_two_physical_rows_is_a_nonfatal_construction_violation(self):
        # Reachable via a courses.toml "hybrid" relationship whose declared
        # member no longer looks like a physical+companion pair (see
        # docs/codes.md). Construction never rejects this -- it is
        # reported, not raised -- and the solver still enforces the full
        # rule via pairwise_predicate like every other kind; a pairing
        # this broken simply can't be scheduled (a section's online/
        # physical shape isn't something candidate selection can fix), so
        # solving it would report infeasible rather than repair it.
        item = HybridClass((
            make_section(Section="M01", **{"Time Slot": "MWF 8:00am"}),
            make_section(Section="M01", **{"Time Slot": "MWF 9:00am"}),
        ))

        predicate = item.pairwise_predicate()
        self.assertIsNotNone(predicate)
        self.assertFalse(predicate(*item.sections))
        evaluation = evaluate_schedule(Schedule([item]), {}, {})

        self.assertEqual(len(evaluation.hard_violations), 1)
        self.assertEqual(evaluation.hard_violations[0].rule, "hybrid_invalid")


class EvaluateRequiredRoomTests(unittest.TestCase):
    def test_nonphysical_hybrid_companion_does_not_require_a_room(self):
        online = make_section(
            Section="F01", **{"Time Slot": "TBA"}, Duration="", Room="",
        )
        physical = make_section(Section="F01", Room="269")
        schedule = Schedule([HybridClass((online, physical))])

        evaluation = evaluate_schedule(
            schedule, {}, {}, constraint_rules=(ConstraintRule(
                course="MATH 1113", section="F01",
                room=("Corley 269",),
            ),),
        )

        self.assertEqual(evaluation.hard_violations, ())

    def test_hybrid_physical_section_reference_is_not_assumed_to_be_row_zero(self):
        # The online/TBA row comes first here (row 0) and the physical
        # row second (row 1) -- physical_section is found by content, not
        # position (see docs/codes.md), so a naive "row 0" assumption
        # would misreport which record this constraint violation is
        # actually about.
        online = make_section(
            Section="F01", **{"Time Slot": "TBA"}, Duration="", Room="",
        )
        physical = make_section(Section="F01", Room="205")
        schedule = Schedule([HybridClass((online, physical))])

        evaluation = evaluate_schedule(
            schedule, {}, {}, constraint_rules=(ConstraintRule(
                course="MATH 1113", section="F01",
                room=("Corley 269",),
            ),),
        )

        self.assertEqual(len(evaluation.hard_violations), 1)
        violation = evaluation.hard_violations[0]
        self.assertEqual(len(violation.references), 1)
        ref = violation.references[0]
        self.assertEqual((ref.class_index, ref.record_index), (0, 1))
        self.assertEqual(ref.course_id, "MATH 1113-F01")


class GroupingTests(unittest.TestCase):
    def test_invalid_section_is_reported_as_grouping_error_with_source_row(self):
        record = make_record(Section="")

        with self.assertRaises(GroupingError) as caught:
            Schedule.from_records([record])

        self.assertEqual(caught.exception.records[0]["Subject"], "MATH")
        self.assertIn("Section", str(caught.exception))

    def test_mwf_and_tr_same_course_same_instructor_groups_as_four_credit(self):
        records = [
            make_record(**{"Time Slot": "MWF 9:00am"}, Duration=50),
            make_record(**{"Time Slot": "T 9:00am"}, Duration=75),
        ]
        schedule = Schedule.from_records(records)
        self.assertEqual(len(schedule), 1)
        self.assertIsInstance(schedule.classes[0], FourCreditClass)

    def test_cross_list_column_pairs_different_courses(self):
        records = [
            make_record(Subject="MATH", Number="1113", **{"Cross-List": "XL1"}),
            make_record(Subject="STAT", Number="2103", **{"Cross-List": "XL1"}),
        ]
        schedule = Schedule.from_records(records)
        self.assertEqual(len(schedule), 1)
        self.assertIsInstance(schedule.classes[0], CrossListingClass)

    def test_known_cross_list_without_source_marker_groups_and_counts_once(self):
        records = [
            make_record(
                Subject="MATH", Number="5173", Section="TC1",
                **{"Time Slot": "TBA"}, Duration="", Room="",
                Instructor="Jordan, Scott M.",
            ),
            make_record(
                Subject="STAT", Number="4173", Section="TC1",
                **{"Time Slot": "TBA"}, Duration="", Room="",
                Instructor="Jordan, Scott M.",
            ),
        ]
        schedule = Schedule.from_records(records)
        self.assertEqual(len(schedule), 1)
        self.assertIsInstance(schedule.classes[0], CrossListingClass)
        self.assertEqual(teaching_loads(schedule)["Jordan, Scott M."], 3)
        evaluation = evaluate_schedule(
            schedule,
            {},
            {"Jordan, Scott M.": PersonRecord(
                name="Jordan, Scott M.", max_load=3
            )},
        )
        self.assertEqual(evaluation.atomic_classes, 1)
        self.assertEqual(evaluation.row_count, 2)
        self.assertEqual(evaluation.loads["Jordan, Scott M."], 3)
        self.assertEqual(evaluation.hard_violations, ())
        self.assertEqual(evaluation.soft_penalty, 0)
        self.assertTrue(all(
            not section.cross_list for section in schedule.classes[0].sections
        ))

    def test_two_different_instructors_each_get_full_credit_for_a_diverging_cross_listing(self):
        # synced_fields need not include "instructor" (see docs/codes.md)
        # -- when it doesn't, the two rows can genuinely have different
        # instructors. credit_hours still counts once per the course
        # (SpecialClass.credit_hours, from the first row: 3, from the
        # trailing digit of "5173"/"4173"), but teaching_loads() credits
        # every distinct instructor teaching the class with that full
        # amount, not a split -- a cross-listed section is a real
        # teaching assignment for each of them, not one assignment shared
        # between two people.
        records = [
            make_record(
                Subject="MATH", Number="5173", Section="TC1",
                Instructor="Jordan, Scott M.",
            ),
            make_record(
                Subject="STAT", Number="4173", Section="TC1",
                Instructor="Growns, Landon C.",
            ),
        ]
        schedule = Schedule.from_records(records)
        self.assertIsInstance(schedule.classes[0], CrossListingClass)
        self.assertEqual(schedule.classes[0].credit_hours, 3)
        loads = teaching_loads(schedule)
        self.assertEqual(loads["Jordan, Scott M."], 3)
        self.assertEqual(loads["Growns, Landon C."], 3)

    def test_math_1110_credit_override_survives_atomic_round_trip(self):
        schedule = Schedule.from_records([
            make_record(
                Subject="MATH", Number="1110", Section="003", Credits="0",
            ),
        ])
        item = schedule.classes[0]
        self.assertEqual(item.credit_hours, 2)
        self.assertEqual(item.sections[0].credits, 2)
        self.assertEqual(schedule.to_records()[0]["Credits"], 2)

    def test_known_cross_list_different_sections_remain_separate(self):
        records = [
            make_record(Subject="MATH", Number="5173", Section="TC1"),
            make_record(Subject="STAT", Number="4173", Section="TC2"),
        ]
        schedule = Schedule.from_records(records)
        self.assertEqual(len(schedule), 2)

    def test_legacy_configured_marker_is_removed_on_import(self):
        records = [
            make_record(
                Subject="MATH", Number="5173", Section="TC1",
                **{"Cross-List": "configured:MATH 5173|STAT 4173"},
            ),
            make_record(
                Subject="STAT", Number="4173", Section="TC1",
                **{"Cross-List": "configured:MATH 5173|STAT 4173"},
            ),
        ]
        schedule = Schedule.from_records(records)
        self.assertEqual(len(schedule), 1)
        self.assertTrue(all(
            not section.cross_list for section in schedule.classes[0].sections
        ))

    def test_honors_pair_without_cross_list_column_still_groups(self):
        records = [
            make_record(Section="001", Instructor="Alice", Room="101"),
            make_record(Section="H01", Instructor="Alice", Room="101"),
        ]
        schedule = Schedule.from_records(records)
        self.assertEqual(len(schedule), 1)
        self.assertIsInstance(schedule.classes[0], CrossListingClass)

    def test_coreq_whitelist_pair_groups_as_coreq(self):
        from class_schedule.class_model import CoreqClass

        records = [
            make_record(Subject="MATH", Number="1113", Section="001", **{"Time Slot": "MWF 9:00am"}),
            make_record(Subject="MATH", Number="0903", Section="001", **{"Time Slot": "MWF 9:50am"}),
        ]
        schedule = Schedule.from_records(records)
        self.assertEqual(len(schedule), 1)
        self.assertIsInstance(schedule.classes[0], CoreqClass)

    def test_unrelated_single_row_becomes_normal_class(self):
        schedule = Schedule.from_records([make_record()])
        self.assertEqual(len(schedule), 1)
        self.assertIsInstance(schedule.classes[0], NormalClass)

    def test_three_rows_same_identity_is_grouping_error(self):
        records = [make_record() for _ in range(3)]
        with self.assertRaises(GroupingError):
            Schedule.from_records(records)

    def test_course_schedule_report_shaped_hybrid_pair_groups_correctly(self):
        # Shaped exactly like ATU's "Course Schedule Report" export (see
        # examples/Course Schedule Report_*.csv): Meeting_Days/
        # Meeting_Times instead of Time Slot/Duration, and "Unassigned"
        # (not blank) for the online row's Room/Building. Normalization must
        # produce one nonphysical and one physical record before strict Hybrid
        # grouping runs.
        records = [
            {
                "Subject": "MATH", "Number": "1113", "Section": "F01",
                "Meeting_Days": "TBA", "Meeting_Times": "TBA",
                "Room": "Unassigned", "Building": "Unassigned",
                "Instructor": "Hogan, Jessica L.",
            },
            {
                "Subject": "MATH", "Number": "1113", "Section": "F01",
                "Meeting_Days": "MWF", "Meeting_Times": "10:00 am-10:50 am",
                "Room": "269", "Building": "Corley",
                "Instructor": "Hogan, Jessica L.",
            },
        ]
        schedule = Schedule.from_records(records)
        self.assertEqual(len(schedule), 1)
        self.assertIsInstance(schedule.classes[0], HybridClass)
        online, in_person = schedule.classes[0].sections
        self.assertTrue(online.is_online)
        self.assertEqual(in_person.time_slot, "MWF 10:00am")
        self.assertEqual(in_person.duration, 50)
        self.assertEqual(in_person.room, "269")

    def test_single_hybrid_physical_row_generates_online_companion(self):
        schedule = Schedule.from_records([
            make_record(
                Subject="MATH", Number="1113", Section="F01",
                **{"Time Slot": "MWF 10:00am"}, Duration=50,
                Room="269", Building="Corley",
                Instructor="Hogan, Jessica L.",
            ),
        ])

        self.assertEqual(len(schedule), 1)
        hybrid = schedule.classes[0]
        self.assertIsInstance(hybrid, HybridClass)
        self.assertEqual(hybrid.room, "269")
        self.assertEqual(hybrid.building, "Corley")
        exported = schedule.to_records()
        self.assertEqual(len(exported), 2)
        online = next(row for row in exported if row["Time Slot"] == "ONLINE")
        self.assertIsNone(online["Room"])
        self.assertEqual(online["Instructor"], "Hogan, Jessica L.")

    def test_ambiguous_coreq_pairing_is_grouping_error(self):
        # MATH 1113-001 is a whitelisted coreq partner for *both*
        # MATH 0903-001 and MATH 1110-001 -- with all three present at the
        # same section number, 1113 can't be unambiguously paired with
        # just one of them.
        records = [
            make_record(Subject="MATH", Number="1113", Section="001"),
            make_record(Subject="MATH", Number="0903", Section="001"),
            make_record(Subject="MATH", Number="1110", Section="001"),
        ]
        with self.assertRaises(GroupingError):
            Schedule.from_records(records)

    def test_concurrent_enrollment_prefix_is_dropped(self):
        records = [make_record(Section="P01")]
        schedule = Schedule.from_records(records)
        self.assertEqual(len(schedule), 0)


def _references(schedule: Schedule) -> set[tuple[int, int, str]]:
    return {
        (class_index, record_index, section.course_id)
        for class_index, item in enumerate(schedule.classes)
        for record_index, section in enumerate(item.sections)
    }


class RoundTripReferenceStabilityTests(unittest.TestCase):
    def test_flatten_and_regroup_reproduces_the_same_references(self):
        # This is the assumption RecordReference's validity rests on (see
        # docs/codes.md): POST /api/analyze rebuilds a Schedule from the
        # browser's flattened records every time, rather than replacing
        # data.classes -- so class_index/record_index have to survive a
        # to_records()/from_records() round trip unchanged, with no
        # config or edit involved, for every one of the five atomic-class
        # kinds. If grouping order ever became data-dependent in a new
        # way, this is what would catch it.
        records = [
            make_record(Number="2003", Section="001", Instructor="Alice"),
            make_record(Number="1914", Section="001", Instructor="Bob", **{"Time Slot": "MWF 9:00am"}),
            make_record(Number="1914", Section="001", Instructor="Bob", **{"Time Slot": "T 9:30am"}, Duration=80),
            make_record(Number="2924", Section="F01", Instructor="Carol"),
            make_record(
                Number="2924", Section="F01", Instructor="Carol",
                **{"Time Slot": "TBA"}, Duration="", Room="",
            ),
            make_record(Number="5173", Section="TC1", Instructor="Dave", **{"Cross-List": "XL1"}),
            make_record(Subject="STAT", Number="4173", Section="TC1", Instructor="Dave", **{"Cross-List": "XL1"}),
            make_record(Number="0903", Section="002", Instructor="Eve"),
            make_record(
                Number="1113", Section="002", Instructor="Eve",
                **{"Time Slot": "T 9:20am"}, Duration=75,
            ),
        ]
        # Built through the same grouping pipeline the real system always
        # uses (Schedule.from_records), not by hand-assembling atomic
        # classes in an arbitrary order -- the pipeline's own stage order
        # (special kinds recognized first, plain rows last) is part of
        # what has to survive the round trip, not something this test
        # should sidestep.
        schedule = Schedule.from_records(records)
        self.assertEqual(
            sorted(type(item).__name__ for item in schedule.classes),
            ["CoreqClass", "CrossListingClass", "FourCreditClass", "HybridClass", "NormalClass"],
        )
        before = _references(schedule)

        reloaded = Schedule.from_records(schedule.to_records())

        self.assertEqual(_references(reloaded), before)
        self.assertEqual(
            [type(item).__name__ for item in reloaded.classes],
            [type(item).__name__ for item in schedule.classes],
        )


def _schedule_with_load(credit_hours_list, instructor="Alice") -> Schedule:
    """One single-row class per entry in ``credit_hours_list`` (last digit
    of a synthetic course number), all taught by ``instructor``."""
    classes = []
    for i, hours in enumerate(credit_hours_list):
        classes.append(NormalClass((make_section(
            Number=f"{i}00{hours}", Section=f"{i:03d}", Instructor=instructor,
        ),)))
    return Schedule(classes)


class OverloadPenaltyTests(unittest.TestCase):
    """max_load=10 throughout; OVERLOAD_TOLERANCE=2 (2 is fine, 3+
    triggers), OVERLOAD_FAR_THRESHOLD=4 (4 is fine, 5+ triggers -- same
    "last safe value" convention as OVERLOAD_TOLERANCE). Overload is priced
    per credit past tolerance; permissive far overload adds 50."""

    def test_within_tolerance_is_no_overload_finding(self):
        schedule = _schedule_with_load([9, 3])  # 12 total, 2 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=True)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        self.assertFalse(any(f.rule == "overload" for f in findings))

    def test_permissive_base_penalty_only(self):
        schedule = _schedule_with_load([9, 4])  # 13 total, 3 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=True)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 10.0)

    def test_permissive_at_exactly_the_far_threshold_does_not_trigger_the_extra(self):
        # OVERLOAD_FAR_THRESHOLD=4 is the last *fine* value, same
        # convention as OVERLOAD_TOLERANCE -- only 5+ triggers it.
        schedule = _schedule_with_load([9, 5])  # 14 total, exactly 4 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=True)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 20.0)  # two credits past tolerance

    def test_permissive_one_past_the_far_threshold_triggers(self):
        schedule = _schedule_with_load([9, 6])  # 15 total, exactly 5 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=True)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 80.0)  # 3 * 10 + far 50

    def test_permissive_past_the_far_threshold_adds_the_extra_penalty(self):
        schedule = _schedule_with_load([9, 8])  # 17 total, 7 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=True)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 100.0)  # 5 * 10 + far 50

    def test_permissive_penalty_keeps_scaling_far_over(self):
        schedule = _schedule_with_load([9, 9, 9])  # 27 total, 17 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=True)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 200.0)  # 15 * 10 + far 50

    def test_strict_instructor_costs_100_per_credit_past_tolerance(self):
        schedule = _schedule_with_load([9, 4])  # 13 total, 3 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=False)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 100.0)

    def test_strict_instructor_keeps_scaling_far_over(self):
        # The far-threshold extra penalty never applies to a strict instructor;
        # its 100-per-credit base continues to scale on its own.
        schedule = _schedule_with_load([9, 9, 9, 3])  # 30 total, 20 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=False)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 1800.0)

    def test_overload_references_cover_every_record_of_a_multi_row_atomic_class(self):
        # teaching_loads() credits a whole atomic class to an instructor
        # the moment any row names them -- overload/under_load references
        # follow that same rule, not just the literal matching row (see
        # docs/codes.md).
        pair = CrossListingClass((
            make_section(Number="5173", Section="TC1", Instructor="Alice", **{"Cross-List": "XL1"}),
            make_section(Subject="STAT", Number="4173", Section="TC1", Instructor="Alice", **{"Cross-List": "XL1"}),
        ))
        extra = NormalClass((make_section(Number="9006", Section="002", Instructor="Alice"),))
        schedule = Schedule([pair, extra])
        persons = {"Alice": PersonRecord(name="Alice", max_load=1)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=True)}

        _, findings = check_soft_preferences(schedule, preferences, persons)

        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(
            {(r.class_index, r.record_index) for r in overload.references},
            {(0, 0), (0, 1), (1, 0)},
        )


class UnderloadPenaltyTests(unittest.TestCase):
    def test_penalty_scales_with_missing_credit_hours(self):
        schedule = _schedule_with_load([3])
        persons = {"Alice": PersonRecord(name="Alice", max_load=12)}

        _, findings = check_soft_preferences(schedule, {}, persons)

        underload = next(f for f in findings if f.rule == "under_load")
        self.assertEqual(underload.penalty, 270.0)
        self.assertEqual(
            {(r.class_index, r.record_index) for r in underload.references},
            {(0, 0)},
        )

    def test_underload_references_are_empty_for_an_instructor_teaching_nothing(self):
        # Legitimate, not a bug (see docs/codes.md) -- the web UI falls
        # back to a plain instructor-tab link off `subject` for this case
        # instead of a course link.
        schedule = Schedule([])
        persons = {"Alice": PersonRecord(name="Alice", max_load=12)}

        _, findings = check_soft_preferences(schedule, {}, persons)

        underload = next(f for f in findings if f.rule == "under_load")
        self.assertEqual(underload.references, ())


class CheckWorkloadHardCapsTests(unittest.TestCase):
    """Plan A (see docs/codes.md): mirrors solver/constraints.py's
    add_load_terms exactly -- each class's full credit_hours attributed
    to its first row's instructor only, and no tolerance at all for a
    New Instructor/New Professor identity's contract load."""

    def test_within_hard_cap_tolerance_is_not_reported(self):
        # max_load=10, hard_load_cap_tolerance defaults to 6 -> 16 is fine.
        schedule = _schedule_with_load([9, 6])  # 15 total
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        violations = check_workload_hard_caps(schedule, persons)
        self.assertEqual([v for v in violations if v.rule == "hard_load_cap"], [])

    def test_past_hard_cap_tolerance_is_a_hard_violation(self):
        schedule = _schedule_with_load([9, 9])  # 18 total, 2 past the 16 cap
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        violations = check_workload_hard_caps(schedule, persons)
        capped = [v for v in violations if v.rule == "hard_load_cap"]
        self.assertEqual(len(capped), 1)
        self.assertEqual(capped[0].subject, "Alice")
        self.assertEqual(
            {(r.class_index, r.record_index) for r in capped[0].references},
            {(0, 0), (1, 0)},
        )

    def test_new_instructor_contract_load_has_no_tolerance(self):
        name = new_instructor_name(1)
        schedule = _schedule_with_load([9, 6], instructor=name)  # 15 total
        policy = NewInstructorPolicySchema(contract_load=15)
        # Exactly at the cap is fine...
        self.assertEqual(
            [v for v in check_workload_hard_caps(
                schedule, {}, new_instructor_policy=policy,
            ) if v.rule == "new_hire_contract_load"],
            [],
        )
        # ...one credit hour over is not, unlike a configured instructor
        # (who'd still have hard_load_cap_tolerance=6 of room left).
        over_schedule = _schedule_with_load([9, 7], instructor=name)  # 16 total
        violations = check_workload_hard_caps(
            over_schedule, {}, new_instructor_policy=policy,
        )
        capped = [v for v in violations if v.rule == "new_hire_contract_load"]
        self.assertEqual(len(capped), 1)
        self.assertEqual(capped[0].subject, name)

    def test_diverging_cross_listing_load_is_charged_to_every_instructor(self):
        # solver/constraints.py's add_load_terms was fixed to count every
        # row of a class, not just the first (see docs/codes.md) --
        # check_workload_hard_caps now shares teaching_loads()'s
        # definition directly, so a CrossListingClass with two different
        # (unsynced) instructors caps *both* of them on the class's full
        # credit_hours, matching what the solver itself now enforces.
        pair = CrossListingClass((
            make_section(Number="9009", Section="TC1", Instructor="Alice", **{"Cross-List": "XL1"}),
            make_section(Subject="STAT", Number="9009", Section="TC1", Instructor="Bob", **{"Cross-List": "XL1"}),
        ))
        schedule = Schedule([pair])
        persons = {
            "Alice": PersonRecord(name="Alice", max_load=1),
            "Bob": PersonRecord(name="Bob", max_load=1),
        }
        violations = check_workload_hard_caps(schedule, persons)
        capped = {v.subject for v in violations if v.rule == "hard_load_cap"}
        self.assertEqual(capped, {"Alice", "Bob"})
        for violation in violations:
            self.assertEqual(
                {(r.class_index, r.record_index) for r in violation.references},
                {(0, 0), (0, 1)},
            )


class CheckNewHireCountsTests(unittest.TestCase):
    def test_count_within_allowed_counts_is_not_reported(self):
        schedule = Schedule([
            NormalClass((make_section(Number="2003", Section="001", Instructor=new_instructor_name(1)),)),
            NormalClass((make_section(Number="2004", Section="001", Instructor=new_instructor_name(2)),)),
        ])
        violations = check_new_hire_counts(schedule)
        self.assertEqual(
            [v for v in violations if v.rule == "new_instructor_count"], [],
        )

    def test_count_outside_allowed_counts_is_a_hard_violation(self):
        schedule = Schedule([
            NormalClass((make_section(Number="2003", Section="001", Instructor=new_instructor_name(1)),)),
            NormalClass((make_section(Number="2004", Section="001", Instructor=new_instructor_name(2)),)),
        ])
        policy = NewInstructorPolicySchema(allowed_counts=[1])
        violations = check_new_hire_counts(schedule, new_instructor_policy=policy)
        capped = [v for v in violations if v.rule == "new_instructor_count"]
        self.assertEqual(len(capped), 1)
        self.assertEqual(
            {(r.class_index, r.record_index) for r in capped[0].references},
            {(0, 0), (1, 0)},
        )

    def test_required_count_of_one_with_zero_used_has_empty_references(self):
        schedule = Schedule([
            NormalClass((make_section(Number="2003", Section="001", Instructor="Alice"),)),
        ])
        policy = NewProfessorPolicySchema(allowed_counts=[1])
        violations = check_new_hire_counts(schedule, new_professor_policy=policy)
        capped = [v for v in violations if v.rule == "new_professor_count"]
        self.assertEqual(len(capped), 1)
        self.assertEqual(capped[0].references, ())


if __name__ == "__main__":
    unittest.main()
