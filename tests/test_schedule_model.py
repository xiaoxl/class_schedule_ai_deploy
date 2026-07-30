import unittest

from class_schedule.class_model import CrossListingClass, FourCreditClass, NormalClass, Section
from class_schedule.schedule_model import (
    GroupingError,
    PersonRecord,
    PreferenceRecord,
    Schedule,
    check_conflicts,
    check_soft_preferences,
)


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


class GroupingTests(unittest.TestCase):
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
    OVERLOAD_FAR_PENALTY=50."""

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
