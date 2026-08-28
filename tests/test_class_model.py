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

    def test_explicit_credit_is_authoritative(self):
        section = make_section(number="1110", credits=2)
        self.assertEqual(section.credit_hours, 2)

    def test_missing_credit_is_inferred_from_final_digit(self):
        section = make_section(number="1914", credits=None)
        self.assertEqual(section.credit_hours, 4)

    def test_credit_override_is_scoped_to_math_1110(self):
        section = make_section(subject="STAT", number="1110", credits=1.5)
        self.assertEqual(section.credit_hours, 1.5)


class FourCreditClassTests(unittest.TestCase):
    def test_mwf_plus_t_same_instructor_is_four_credit(self):
        left = make_section(number="1914", time_slot="MWF 9:00am", section="001")
        right = make_section(number="1914", time_slot="T 9:00am", duration=80, section="001")
        self.assertTrue(FourCreditClass.is_four_credit(left, right))
        FourCreditClass((left, right))  # constructs without raising

    def test_mwf_plus_r_same_instructor_is_four_credit(self):
        left = make_section(number="1914", time_slot="MWF 9:00am")
        right = make_section(number="1914", time_slot="R 9:00am", duration=80)
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
        left = make_section(number="1914", time_slot="MWF 8:00am")
        right = make_section(number="1914", time_slot="T 1:00pm", duration=80)

        item = FourCreditClass((left, right))

        self.assertTrue(FourCreditClass.is_four_credit(left, right))
        self.assertFalse(FourCreditClass.is_valid_schedule(left, right))
        self.assertEqual(len(item.validation_report()), 1)
        self.assertIn("300 minutes apart", item.validation_report()[0])

    def test_ninety_minute_time_gap_is_valid(self):
        left = make_section(number="1914", time_slot="MWF 8:00am")
        right = make_section(number="1914", time_slot="R 9:30am", duration=80)

        item = FourCreditClass((left, right))

        self.assertTrue(FourCreditClass.is_valid_schedule(left, right))
        self.assertEqual(item.validation_report(), ())
        self.assertTrue(item.validate())
        self.assertEqual(item.validation_report(), ())

    def test_partial_meeting_must_be_eighty_minutes(self):
        item = FourCreditClass((
            make_section(number="1914", time_slot="MWF 9:00am"),
            make_section(number="1914", time_slot="T 9:30am", duration=75),
        ))
        self.assertFalse(item.validate())
        self.assertIn("80 minutes", item.validation_report()[0])

    def test_instructor_links_both_rows_time_and_room_stay_independent(self):
        item = FourCreditClass((
            make_section(time_slot="MWF 9:00am", room="101"),
            make_section(time_slot="T 9:00am", duration=75, room="205"),
        ))
        self.assertEqual(item.edit_targets("instructor", 0), (0, 1))
        self.assertEqual(item.edit_targets("instructor", 1), (0, 1))
        self.assertEqual(item.edit_targets("time", 0), (0,))
        self.assertEqual(item.edit_targets("room", 1), (1,))


class HybridClassTests(unittest.TestCase):
    def test_m_prefixed_physical_and_tba_pair_is_hybrid(self):
        left = make_section(section="M01", room="101")
        right = make_section(
            section="M01", time_slot="TBA", duration=None, room="", building=""
        )
        self.assertTrue(HybridClass.is_hybrid(left, right))

    def test_f_prefixed_online_and_physical_pair_is_hybrid(self):
        left = make_section(
            section="F01", time_slot="ONLINE", duration=None, room="", building=""
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

    def test_time_and_room_edits_always_route_to_the_physical_row(self):
        physical = make_section(section="F01", room="269", building="Corley")
        hybrid = HybridClass((physical,))  # sections = (companion, physical)
        physical_index = hybrid.sections.index(hybrid.physical_section)
        self.assertEqual(physical_index, 1)
        self.assertEqual(hybrid.edit_targets("time", 0), (1,))
        self.assertEqual(hybrid.edit_targets("room", 0), (1,))
        self.assertEqual(hybrid.edit_targets("time", 1), (1,))

    def test_instructor_links_both_rows(self):
        hybrid = HybridClass((make_section(section="F01", room="269"),))
        self.assertEqual(hybrid.edit_targets("instructor", 0), (0, 1))

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
    def test_three_members_are_supported_and_credit_uses_the_maximum(self):
        sections = (
            make_section(subject="MATH", number="1113", section="001", credits=3),
            make_section(subject="STAT", number="2104", section="001", credits=4),
            make_section(subject="CS", number="2002", section="001", credits=2),
        )
        item = CrossListingClass.from_configured_sections(sections)
        self.assertEqual(item.credit_hours, 4)
        self.assertEqual(item.edit_targets("instructor", 1), (0, 1, 2))
        self.assertTrue(item.validate())

    def test_configured_members_do_not_need_an_inference_marker(self):
        item = CrossListingClass.from_configured_sections((
            make_section(subject="MATH", number="3003", section="001"),
            make_section(subject="STAT", number="4003", section="002"),
        ))
        self.assertTrue(item.validate())
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

    def test_honors_pair_recognition_does_not_require_a_shared_room(self):
        # Recognition is purely structural (see docs/codes.md): a regular/
        # honors pair that started out in different rooms is still one
        # cross-listing, free to stay that way.
        left = make_section(section="001", instructor="Alice", room="101")
        right = make_section(section="H01", instructor="Alice", room="102")
        self.assertTrue(CrossListingClass.is_honors_pair(left, right))
        self.assertFalse(CrossListingClass.is_shared_meeting(left, right))

    def test_fully_matching_pair_locks_all_three_fields(self):
        left = make_section(subject="MATH", number="1113", cross_list="XL1")
        right = make_section(subject="STAT", number="2103", cross_list="XL1")
        item = CrossListingClass((left, right))
        self.assertEqual(item.synced_fields, frozenset({"instructor", "room", "time"}))
        predicate = item.pairwise_predicate()
        self.assertIsNotNone(predicate)
        self.assertTrue(predicate(left, right))
        moved = make_section(
            subject="STAT", number="2103", cross_list="XL1",
            room="102", time_slot="MWF 10:00am",
        )
        self.assertFalse(predicate(left, moved))

    def test_partially_matching_pair_locks_only_the_shared_fields(self):
        left = make_section(
            subject="MATH", number="1113", cross_list="XL1",
            room="101", time_slot="MWF 9:00am",
        )
        right = make_section(
            subject="STAT", number="2103", cross_list="XL1",
            room="205", time_slot="TR 11:00am", duration=80,
        )
        item = CrossListingClass((left, right))
        self.assertEqual(item.synced_fields, frozenset({"instructor"}))
        predicate = item.pairwise_predicate()
        self.assertIsNotNone(predicate)
        # Room/time may move independently -- only instructor is enforced.
        self.assertTrue(predicate(
            left, make_section(
                subject="STAT", number="2103", cross_list="XL1",
                room="310", time_slot="TR 1:00pm", duration=80,
            ),
        ))
        self.assertFalse(predicate(
            left, make_section(
                subject="STAT", number="2103", cross_list="XL1",
                instructor="Bob", room="205", time_slot="TR 11:00am", duration=80,
            ),
        ))

    def test_configured_pair_that_currently_violates_its_own_lock_reports_a_schedule_issue(self):
        # Regression: validation reporting used to check only recognition
        # (_issues) -- a configured pair whose synced_fields lock the two
        # rows to match, but whose actual current data doesn't (e.g. a
        # declared relationship defaulting to ALL_SYNCED_FIELDS over a
        # template that still shows different rooms), was reported as
        # clean everywhere except pairwise_predicate. See docs/codes.md.
        left = make_section(
            subject="MATH", number="5173", section="TC1",
            instructor="Alice", room="101", time_slot="TR 11:00am", duration=80,
        )
        right = make_section(
            subject="STAT", number="4173", section="TC1",
            instructor="Bob", room="205", time_slot="TR 2:00pm", duration=50,
        )
        item = CrossListingClass.from_configured_sections((left, right))
        self.assertEqual(item.synced_fields, CrossListingClass.ALL_SYNCED_FIELDS)
        self.assertEqual(len(item.validation_report()), 3)
        predicate = item.pairwise_predicate()
        self.assertFalse(predicate(left, right))

    def test_configured_pair_that_currently_satisfies_its_own_lock_has_no_schedule_issue(self):
        left = make_section(
            subject="MATH", number="5173", section="TC1",
            instructor="Alice", room="101", time_slot="TR 11:00am", duration=80,
        )
        right = make_section(
            subject="STAT", number="4173", section="TC1",
            instructor="Alice", room="101", time_slot="TR 11:00am", duration=80,
        )
        item = CrossListingClass.from_configured_sections((left, right))
        self.assertEqual(item.validation_report(), ())
        predicate = item.pairwise_predicate()
        self.assertTrue(predicate(left, right))

    def test_apply_edit_does_not_report_a_sync_issue_for_an_unlocked_field(self):
        # validation_report uses the restored persisted lock policy
        # synced_fields (see docs/codes.md) -- confirms that recompute
        # doesn't false-positive on a field that was never locked to
        # begin with.
        left = make_section(
            subject="MATH", number="5173", section="TC1",
            instructor="Alice", room="101", time_slot="TR 11:00am", duration=80,
        )
        right = make_section(
            subject="STAT", number="4173", section="TC1",
            instructor="Alice", room="101", time_slot="TR 11:00am", duration=80,
        )
        item = CrossListingClass.from_configured_sections(
            (left, right), synced_fields=frozenset({"instructor"}),
        )
        self.assertEqual(item.validation_report(), ())
        updated = item.apply_edit("room", 0, building="Rothwell", room="205")
        self.assertEqual(updated.synced_fields, frozenset({"instructor"}))
        self.assertEqual(updated.validation_report(), ())

    def test_no_shared_fields_leaves_instructor_room_time_unconstrained(self):
        left = make_section(
            subject="MATH", number="1113", cross_list="XL1",
            instructor="Alice", room="101", time_slot="MWF 9:00am",
        )
        right = make_section(
            subject="STAT", number="2103", cross_list="XL1",
            instructor="Bob", room="205", time_slot="TR 11:00am", duration=80,
        )
        item = CrossListingClass((left, right))
        self.assertEqual(item.synced_fields, frozenset())
        # Recognition (is_cross_listing) still has to hold -- the predicate
        # is never None -- but with nothing synced, no field comparison
        # blocks any instructor/room/time combination.
        predicate = item.pairwise_predicate()
        self.assertIsNotNone(predicate)
        self.assertTrue(predicate(left, right))
        self.assertTrue(predicate(
            left, make_section(
                subject="STAT", number="2103", cross_list="XL1",
                instructor="Carol", room="310", time_slot="F 1:00pm", duration=50,
            ),
        ))

    def test_edit_targets_follow_synced_fields_per_field(self):
        left = make_section(
            subject="MATH", number="1113", cross_list="XL1",
            instructor="Alice", room="101", time_slot="MWF 9:00am",
        )
        right = make_section(
            subject="STAT", number="2103", cross_list="XL1",
            instructor="Alice", room="205", time_slot="MWF 9:00am",
        )
        item = CrossListingClass((left, right))
        self.assertEqual(item.synced_fields, frozenset({"instructor", "time"}))
        self.assertEqual(item.edit_targets("instructor", 0), (0, 1))
        self.assertEqual(item.edit_targets("time", 1), (0, 1))
        self.assertEqual(item.edit_targets("room", 0), (0,))

    def test_apply_edit_keeps_the_original_synced_fields_even_when_rows_coincidentally_match(self):
        # Regression: NormalClass.apply_edit ends in replace(self,
        # sections=...), which reruns __post_init__ -- and __post_init__
        # always auto-detects synced_fields from the (possibly just-edited)
        # rows. Without CrossListingClass's own apply_edit override, an
        # edit that happens to make two independent rooms equal would
        # silently promote "room" to synced (and, for a
        # from_configured_sections instance, would silently discard
        # whatever courses.toml actually declared).
        left = make_section(
            subject="MATH", number="1113", cross_list="XL1",
            instructor="Alice", room="101", time_slot="MWF 9:00am",
        )
        right = make_section(
            subject="STAT", number="2103", cross_list="XL1",
            instructor="Alice", room="205", time_slot="MWF 9:00am",
        )
        item = CrossListingClass((left, right))
        self.assertEqual(item.synced_fields, frozenset({"instructor", "time"}))
        updated = item.apply_edit("room", 1, building="Corley", room="101")
        self.assertEqual(updated.sections[0].room, "101")
        self.assertEqual(updated.sections[1].room, "101")
        self.assertEqual(updated.synced_fields, frozenset({"instructor", "time"}))

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
        left = make_section(
            number="1113", time_slot="ONLINE", duration=None, instructor="Alice",
        )
        right = make_section(
            number="0903", time_slot="ONLINE", duration=None, instructor="Alice",
        )
        self.assertTrue(CoreqClass.is_valid_schedule(left, right))

    def test_back_to_back_same_room_is_valid_schedule(self):
        left = make_section(number="1113", time_slot="MWF 9:00am", duration=50, room="101")
        right = make_section(number="0903", time_slot="MWF 9:50am", duration=50, room="101")
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
        left = make_section(number="1113", time_slot="MWF 9:00am", duration=50, room="101")
        right = make_section(number="0903", time_slot="TR 9:20am", duration=80, room="102")
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

    def test_instructor_edit_links_both_rows(self):
        # is_valid_schedule requires a shared instructor (class_model.py
        # ~L795) -- editing just one row's instructor is never legal on
        # its own, so it must always be routed to both (see docs/codes.md).
        left = make_section(number="1113", time_slot="MWF 9:00am", duration=50, room="101")
        right = make_section(number="0903", time_slot="T 9:30am", duration=80, room="102")
        item = CoreqClass((left, right))
        self.assertEqual(item.edit_targets("instructor", 0), (0, 1))
        self.assertEqual(item.edit_targets("instructor", 1), (0, 1))

    def test_time_edit_never_links(self):
        left = make_section(number="1113", time_slot="MWF 9:00am", duration=50, room="101")
        right = make_section(number="0903", time_slot="T 9:30am", duration=80, room="102")
        item = CoreqClass((left, right))
        self.assertEqual(item.edit_targets("time", 0), (0,))
        self.assertEqual(item.edit_targets("time", 1), (1,))

    def test_room_edit_links_only_when_currently_back_to_back(self):
        back_to_back = CoreqClass((
            make_section(number="1113", time_slot="MWF 9:00am", duration=50, room="101"),
            make_section(number="0903", time_slot="MWF 9:50am", duration=50, room="101"),
        ))
        self.assertEqual(back_to_back.edit_targets("room", 0), (0, 1))
        disjoint_days = CoreqClass((
            make_section(number="1113", time_slot="MWF 9:00am", duration=50, room="101"),
            make_section(number="0903", time_slot="TR 9:20am", duration=80, room="102"),
        ))
        self.assertEqual(disjoint_days.edit_targets("room", 0), (0,))

    def test_time_edit_that_creates_back_to_back_follows_the_other_rows_room(self):
        # Moving the disjoint-day meeting onto the other's weekday, right
        # after it, makes the pair back-to-back -- which requires a
        # matching room. apply_edit should carry the untouched row's room
        # over automatically instead of leaving a fresh coreq_invalid gap.
        left = make_section(number="1113", time_slot="MWF 9:00am", duration=50, room="101")
        right = make_section(number="0903", time_slot="TR 9:20am", duration=80, room="205")
        item = CoreqClass((left, right))
        self.assertEqual(item.validation_report(), ())

        moved = item.apply_edit("time", 1, time_slot="MWF 9:50am", duration=50)

        moved_left, moved_right = moved.sections
        self.assertTrue(CoreqClass._back_to_back(moved_left, moved_right))
        self.assertEqual(moved_right.room, "101")
        self.assertEqual(moved_right.building, moved_left.building)
        self.assertEqual(moved.validation_report(), ())

    def test_time_edit_that_stays_disjoint_does_not_touch_room(self):
        left = make_section(number="1113", time_slot="MWF 9:00am", duration=50, room="101")
        right = make_section(number="0903", time_slot="TR 9:20am", duration=80, room="205")
        item = CoreqClass((left, right))

        moved = item.apply_edit("time", 1, time_slot="R 9:10am", duration=75)

        self.assertEqual(moved.sections[1].room, "205")


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
