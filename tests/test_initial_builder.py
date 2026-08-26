import unittest

from class_schedule.class_model import NormalClass, Section
from class_schedule.initial_builder import _classes_conflict, recolor_placeholder
from class_schedule.schedule_model import Schedule, check_conflicts


def make_class(number, section, time_slot, instructor="Staff", room="101"):
    return NormalClass((Section(
        subject="MATH", number=number, section=section, time_slot=time_slot,
        duration=50, room=room, instructor=instructor, building="Corley",
    ),))


class ClassesConflictTests(unittest.TestCase):
    def test_overlapping_times_conflict(self):
        self.assertTrue(_classes_conflict(
            make_class("1113", "001", "MWF 9:00am"),
            make_class("1003", "001", "MWF 9:00am"),
        ))

    def test_non_overlapping_times_do_not_conflict(self):
        self.assertFalse(_classes_conflict(
            make_class("1113", "001", "MWF 9:00am"),
            make_class("1003", "001", "MWF 10:00am"),
        ))

    def test_online_sections_never_conflict(self):
        def online(number):
            return NormalClass((Section(
                subject="MATH", number=number, section="TC1", time_slot="TBA",
                duration=None, room="", instructor="Staff",
            ),))
        self.assertFalse(_classes_conflict(online("1113"), online("1003")))


class RecolorPlaceholderTests(unittest.TestCase):
    def test_nonconflicting_classes_share_one_identity(self):
        schedule = Schedule([
            make_class("1113", "001", "MWF 9:00am"),
            make_class("1003", "001", "MWF 10:00am"),
        ])
        recolored, assignments = recolor_placeholder(schedule, seed=1)
        self.assertEqual(set(assignments), {"new_instructor"})
        self.assertEqual(check_conflicts(recolored), [])

    def test_overlapping_classes_receive_numbered_identities(self):
        schedule = Schedule([
            make_class("1113", "001", "MWF 9:00am", room="101"),
            make_class("1003", "001", "MWF 9:00am", room="102"),
            make_class("2914", "001", "MWF 9:00am", room="103"),
        ])
        recolored, assignments = recolor_placeholder(schedule, seed=1)
        self.assertEqual(
            list(assignments),
            ["new_instructor", "new_instructor 2", "new_instructor 3"],
        )
        self.assertEqual(check_conflicts(recolored), [])

    def test_existing_numbered_identity_can_collapse(self):
        schedule = Schedule([
            make_class("1113", "001", "MWF 9:00am", instructor="Staff"),
            make_class("1003", "001", "MWF 10:00am", instructor="Staff 2"),
        ])
        recolored, assignments = recolor_placeholder(schedule, seed=1)
        self.assertEqual(set(assignments), {"new_instructor"})
        self.assertEqual({
            section.instructor for item in recolored for section in item.sections
        }, {"new_instructor"})

    def test_real_instructor_is_unchanged(self):
        real = make_class(
            "9999", "001", "MWF 9:00am", instructor="Bain, Leslie M.",
        )
        recolored, assignments = recolor_placeholder(Schedule([
            real, make_class("1113", "001", "MWF 10:00am"),
        ]), seed=1)
        self.assertNotIn("Bain, Leslie M.", assignments)
        self.assertEqual(
            recolored.get("MATH 9999-001").sections[0].instructor,
            "Bain, Leslie M.",
        )

    def test_same_seed_is_reproducible(self):
        schedule = Schedule([
            make_class("1113", "001", "MWF 9:00am"),
            make_class("1003", "001", "MWF 9:00am"),
            make_class("2914", "001", "MWF 10:00am"),
        ])
        first = recolor_placeholder(schedule, seed=7)
        second = recolor_placeholder(schedule, seed=7)
        self.assertEqual(first[1], second[1])


if __name__ == "__main__":
    unittest.main()
