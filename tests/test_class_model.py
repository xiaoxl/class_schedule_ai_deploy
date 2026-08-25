import unittest

from class_schedule.class_model import (
    CoreqClass,
    CrossListingClass,
    FourCreditClass,
    HybridClass,
    NormalClass,
    Section,
)


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


class SectionTests(unittest.TestCase):
    def test_requires_subject_number_section(self):
        with self.assertRaises(ValueError):
            make_section(subject="")

    def test_subject_normalized_to_uppercase(self):
        self.assertEqual(make_section(subject="math").subject, "MATH")

    def test_legacy_staff_identity_is_canonicalized_on_input_and_output(self):
        section = make_section(instructor="Staff 02")
        self.assertEqual(section.instructor, "new_instructor 2")
        self.assertEqual(section.to_record()["Instructor"], "new_instructor 2")

    def test_canonical_new_instructor_identity_is_preserved(self):
        section = make_section(instructor="new_instructor 3")
        self.assertEqual(section.instructor, "new_instructor 3")

    def test_course_id(self):
        section = make_section(subject="MATH", number="1113", section="001")
        self.assertEqual(section.course_id, "MATH 1113-001")

    def test_is_online_for_online_and_tba_and_blank(self):
        for value in ("ONLINE", "TBA", "", "online"):
            with self.subTest(value=value):
                section = make_section(time_slot=value, duration=None)
                self.assertTrue(section.is_online)

    def test_physical_section_requires_duration(self):
        with self.assertRaises(ValueError):
            make_section(time_slot="MWF 9:00am", duration=None)

    def test_end_computed_from_start_and_duration(self):
        section = make_section(time_slot="MWF 9:00am", duration=50)
        self.assertEqual(section.end.strftime("%H:%M"), "09:50")

    def test_math_1110_credit_override_is_applied_at_construction(self):
        section = make_section(number="1110", credits=0)
        self.assertEqual(section.credits, 2)
        self.assertEqual(section.credit_hours, 2)

    def test_credit_override_is_scoped_to_math_1110(self):
        section = make_section(subject="STAT", number="1110", credits=1.5)
        self.assertEqual(section.credit_hours, 1.5)


class FourCreditClassTests(unittest.TestCase):
    def test_mwf_plus_t_same_instructor_is_four_credit(self):
        left = make_section(time_slot="MWF 9:00am", section="001")
        right = make_section(time_slot="T 9:00am", duration=75, section="001")
        self.assertTrue(FourCreditClass.is_four_credit(left, right))
        FourCreditClass((left, right))  # constructs without raising

    def test_mwf_plus_r_same_instructor_is_four_credit(self):
        left = make_section(time_slot="MWF 9:00am")
        right = make_section(time_slot="R 9:00am", duration=75)
        self.assertTrue(FourCreditClass.is_four_credit(left, right))

    def test_same_days_is_not_four_credit(self):
        left = make_section(time_slot="MWF 9:00am")
        right = make_section(time_slot="MWF 10:00am")
        self.assertFalse(FourCreditClass.is_four_credit(left, right))

    def test_different_instructor_is_not_four_credit(self):
        left = make_section(time_slot="MWF 9:00am", instructor="Alice")
        right = make_section(time_slot="T 9:00am", duration=75, instructor="Bob")
        self.assertFalse(FourCreditClass.is_four_credit(left, right))

    def test_either_online_is_not_four_credit(self):
        left = make_section(time_slot="ONLINE", duration=None)
        right = make_section(time_slot="T 9:00am", duration=75)
        self.assertFalse(FourCreditClass.is_four_credit(left, right))

    def test_large_time_gap_constructs_with_a_schedule_issue(self):
        left = make_section(time_slot="MWF 8:00am")
        right = make_section(time_slot="T 1:00pm", duration=80)

        item = FourCreditClass((left, right))

        self.assertTrue(FourCreditClass.is_four_credit(left, right))
        self.assertFalse(FourCreditClass.is_valid_schedule(left, right))
        self.assertEqual(len(item.schedule_issues), 1)
        self.assertIn("300 minutes apart", item.schedule_issues[0])

    def test_ninety_minute_time_gap_is_valid(self):
        left = make_section(time_slot="MWF 8:00am")
        right = make_section(time_slot="R 9:30am", duration=80)

        item = FourCreditClass((left, right))

        self.assertTrue(FourCreditClass.is_valid_schedule(left, right))
        self.assertEqual(item.schedule_issues, ())


class HybridClassTests(unittest.TestCase):
    def test_m_prefixed_physical_and_tba_pair_is_hybrid(self):
        left = make_section(section="M01", room="101")
        right = make_section(
            section="M01", time_slot="TBA", duration=None, room=""
        )
        self.assertTrue(HybridClass.is_hybrid(left, right))

    def test_f_prefixed_online_and_physical_pair_is_hybrid(self):
        left = make_section(
            section="F01", time_slot="ONLINE", duration=None, room=""
        )
        right = make_section(section="F01", room="101")
        self.assertTrue(HybridClass.is_hybrid(left, right))

    def test_physical_row_is_the_hybrid_location_authority(self):
        stale_online = make_section(
            section="F01", time_slot="ONLINE", duration=None,
            room="", building="", instructor="Old",
        )
        physical = make_section(
            section="F01", room="269", building="Corley",
            instructor="Alice",
        )

        hybrid = HybridClass((stale_online, physical))

        self.assertEqual(hybrid.building, "Corley")
        self.assertEqual(hybrid.room, "269")
        self.assertEqual(hybrid.time_slot, physical.time_slot)
        self.assertEqual(hybrid.online_section.instructor, "Alice")

    def test_online_export_row_is_generated_from_the_physical_row(self):
        physical = make_section(
            section="F01", room="269", building="Corley",
            instructor="Alice",
        )
        hybrid = HybridClass((physical,))

        records = hybrid.to_records()

        self.assertEqual(len(records), 2)
        online = next(record for record in records if record["Time Slot"] == "ONLINE")
        in_person = next(record for record in records if record["Time Slot"] != "ONLINE")
        self.assertEqual(online["Instructor"], "Alice")
        self.assertIsNone(online["Room"])
        self.assertEqual(in_person["Room"], "269")

    def test_non_prefixed_section_is_not_hybrid(self):
        left = make_section(section="001", room="101")
        right = make_section(
            section="001", time_slot="TBA", duration=None, room=""
        )
        self.assertFalse(HybridClass.is_hybrid(left, right))

    def test_both_or_neither_having_a_room_is_not_hybrid(self):
        left = make_section(section="M01", room="101")
        right = make_section(section="M01", room="102")
        self.assertFalse(HybridClass.is_hybrid(left, right))

    def test_two_physical_rows_with_one_missing_room_are_not_hybrid(self):
        left = make_section(section="M01", room="101")
        right = make_section(section="M01", room="")
        self.assertFalse(HybridClass.is_hybrid(left, right))

    def test_non_physical_row_with_room_is_not_hybrid(self):
        left = make_section(
            section="M01", time_slot="TBA", duration=None, room="101"
        )
        right = make_section(section="M01", room="")
        self.assertFalse(HybridClass.is_hybrid(left, right))


class CrossListingClassTests(unittest.TestCase):
    def test_matching_cross_list_value_is_cross_listing(self):
        left = make_section(subject="MATH", number="1113", cross_list="XL1")
        right = make_section(subject="STAT", number="2103", cross_list="XL1")
        self.assertTrue(CrossListingClass.is_cross_listing(left, right))

    def test_known_course_pair_same_section_is_cross_listing(self):
        left = make_section(subject="MATH", number="5173", section="TC1")
        right = make_section(subject="STAT", number="4173", section="TC1")
        self.assertTrue(CrossListingClass.is_cross_listing(left, right))

    def test_known_course_pair_different_section_is_not_cross_listing(self):
        left = make_section(subject="MATH", number="5173", section="TC1")
        right = make_section(subject="STAT", number="4173", section="TC2")
        self.assertFalse(CrossListingClass.is_cross_listing(left, right))

    def test_honors_pair_same_time_room_instructor_is_honors_pair(self):
        left = make_section(section="001", instructor="Alice", room="101")
        right = make_section(section="H01", instructor="Alice", room="101")
        self.assertTrue(CrossListingClass.is_honors_pair(left, right))

    def test_honors_pair_different_room_is_not_honors_pair(self):
        left = make_section(section="001", instructor="Alice", room="101")
        right = make_section(section="H01", instructor="Alice", room="102")
        self.assertFalse(CrossListingClass.is_honors_pair(left, right))

    def test_two_honors_sections_is_not_honors_pair(self):
        left = make_section(section="H01", instructor="Alice", room="101")
        right = make_section(section="H02", instructor="Alice", room="101")
        self.assertFalse(CrossListingClass.is_honors_pair(left, right))


class CoreqClassTests(unittest.TestCase):
    def test_whitelisted_pair_same_section_is_coreq(self):
        left = make_section(subject="MATH", number="1113", section="001")
        right = make_section(subject="MATH", number="0903", section="001")
        self.assertTrue(CoreqClass.is_coreq_pair(left, right))

    def test_non_whitelisted_pair_is_not_coreq(self):
        left = make_section(subject="MATH", number="1113", section="001")
        right = make_section(subject="MATH", number="2103", section="001")
        self.assertFalse(CoreqClass.is_coreq_pair(left, right))

    def test_whitelisted_pair_different_section_is_not_coreq(self):
        left = make_section(subject="MATH", number="1113", section="001")
        right = make_section(subject="MATH", number="0903", section="002")
        self.assertFalse(CoreqClass.is_coreq_pair(left, right))

    def test_both_online_same_instructor_is_valid_schedule(self):
        left = make_section(time_slot="ONLINE", duration=None, instructor="Alice")
        right = make_section(time_slot="ONLINE", duration=None, instructor="Alice")
        self.assertTrue(CoreqClass.is_valid_schedule(left, right))

    def test_back_to_back_same_room_is_valid_schedule(self):
        left = make_section(time_slot="MWF 9:00am", duration=50, room="101")
        right = make_section(time_slot="MWF 9:50am", duration=50, room="101")
        self.assertTrue(CoreqClass.is_valid_schedule(left, right))

    def test_back_to_back_different_room_is_not_valid_schedule(self):
        left = make_section(time_slot="MWF 9:00am", duration=50, room="101")
        right = make_section(time_slot="MWF 9:50am", duration=50, room="102")
        self.assertFalse(CoreqClass.is_valid_schedule(left, right))

    def test_back_to_back_blank_rooms_are_invalid(self):
        left = make_section(time_slot="MWF 9:00am", duration=50, room="")
        right = make_section(time_slot="MWF 9:50am", duration=50, room="")
        self.assertFalse(CoreqClass.is_valid_schedule(left, right))

    def test_back_to_back_same_room_number_different_building_is_invalid(self):
        left = make_section(
            time_slot="MWF 9:00am", duration=50, room="101", building="Corley"
        )
        right = make_section(
            time_slot="MWF 9:50am", duration=50, room="101", building="Rothwell"
        )
        self.assertFalse(CoreqClass.is_valid_schedule(left, right))

    def test_clock_adjacent_on_different_days_is_not_back_to_back(self):
        left = make_section(time_slot="MWF 9:00am", duration=50, room="101")
        right = make_section(time_slot="T 9:50am", duration=50, room="101")
        self.assertFalse(CoreqClass.is_valid_schedule(left, right))

    def test_overlapping_same_day_not_back_to_back_is_invalid(self):
        left = make_section(time_slot="MWF 9:00am", duration=50, room="101")
        right = make_section(time_slot="MWF 9:20am", duration=50, room="102")
        self.assertFalse(CoreqClass.is_valid_schedule(left, right))

    def test_within_30_minutes_different_days_is_valid_schedule(self):
        left = make_section(time_slot="MWF 9:00am", duration=50, room="101")
        right = make_section(time_slot="T 9:20am", duration=75, room="102")
        self.assertTrue(CoreqClass.is_valid_schedule(left, right))

    def test_credit_hours_add_both_courses(self):
        left = make_section(
            subject="MATH", number="1113", section="001",
            time_slot="MWF 9:00am", duration=50, room="101",
        )
        right = make_section(
            subject="MATH", number="0903", section="001",
            time_slot="MWF 9:50am", duration=50, room="101",
        )
        coreq = CoreqClass((left, right))
        self.assertEqual(coreq.credit_hours, 6)  # 1113 -> 3, 0903 -> 3 (last digit each)


class NormalClassTests(unittest.TestCase):
    def test_single_row_credit_hours_from_course_number(self):
        item = NormalClass((make_section(number="1113"),))
        self.assertEqual(item.credit_hours, 3)

    def test_change_instructor_returns_new_instance(self):
        item = NormalClass((make_section(instructor="Alice"),))
        updated = item.change_instructor("Bob")
        self.assertEqual(updated.sections[0].instructor, "Bob")
        self.assertEqual(item.sections[0].instructor, "Alice")


if __name__ == "__main__":
    unittest.main()
