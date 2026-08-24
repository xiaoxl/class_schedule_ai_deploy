import datetime
import unittest

from class_schedule.class_model import CrossListingClass, FourCreditClass, HybridClass, NormalClass, Section
from class_schedule.schedule_model import (
    ConstraintRule,
    GroupingError,
    PersonRecord,
    PreferenceRecord,
    Schedule,
    TimeWindow,
    check_conflicts,
    check_soft_preferences,
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
        self.assertTrue(any(v.rule == "room_conflict" for v in violations))

    def test_same_instructor_overlapping_time_is_instructor_conflict(self):
        a = NormalClass((make_section(Number="1113", Section="001", Instructor="Alice", Room="101"),))
        b = NormalClass((make_section(Number="2103", Section="002", Instructor="Alice", Room="102"),))
        violations = check_conflicts(Schedule([a, b]))
        self.assertTrue(any(v.rule == "instructor_conflict" for v in violations))

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
    "last safe value" convention as OVERLOAD_TOLERANCE),
    OVERLOAD_FAR_PENALTY=50 (base 10 + far 50 = 60)."""

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
        self.assertEqual(overload.penalty, 10.0)  # base only, far threshold not yet crossed

    def test_permissive_one_past_the_far_threshold_triggers(self):
        schedule = _schedule_with_load([9, 6])  # 15 total, exactly 5 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=True)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 60.0)  # base (10) + far (50)

    def test_permissive_past_the_far_threshold_adds_the_extra_penalty(self):
        schedule = _schedule_with_load([9, 8])  # 17 total, 7 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=True)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 60.0)  # base (10) + far (50)

    def test_permissive_stays_at_60_far_over(self):
        schedule = _schedule_with_load([9, 9, 9])  # 27 total, 17 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=True)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 60.0)  # flat -- not scaled further

    def test_strict_instructor_uses_the_flat_ceiling(self):
        schedule = _schedule_with_load([9, 4])  # 13 total, 3 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=False)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 100.0)

    def test_strict_instructor_stays_at_100_far_over(self):
        # The far-threshold extra penalty never applies to a strict
        # instructor -- they're already at this system's ceiling.
        schedule = _schedule_with_load([9, 9, 9, 3])  # 30 total, 20 credit hours over
        persons = {"Alice": PersonRecord(name="Alice", max_load=10)}
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_overload=False)}
        _, findings = check_soft_preferences(schedule, preferences, persons)
        overload = next(f for f in findings if f.rule == "overload")
        self.assertEqual(overload.penalty, 100.0)


if __name__ == "__main__":
    unittest.main()
