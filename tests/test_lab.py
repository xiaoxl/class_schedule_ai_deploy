import datetime
import unittest
from dataclasses import replace

from class_schedule import LabClass, NormalClass, Schedule, Section, teaching_loads
from class_schedule.schedule_model import GroupingError, check_conflicts
from class_schedule.solver import MeetingPattern, RoomRecord, SolverConfig, solve
from class_schedule.solver.candidates import section_candidates
from class_schedule.solver.constraints import build_slots


def lab_rows(number="3260", section="3", instructor="Rajib"):
    """A 50/170 split-room lab with no lecture (e.g. CHEM 3260-3)."""
    base = dict(subject="CHEM", number=number, section=section,
                instructor=instructor, building="Science")
    return (
        Section(**base, type="LAB", time_slot="W 2:00pm", duration=170, room="20"),
        Section(**base, type="LAB", time_slot="W 2:00pm", duration=50, room="29"),
    )


def config():
    return SolverConfig(persons={}, preferences={}, rooms=[RoomRecord("Science", "20")],
        meeting_patterns=[
            MeetingPattern("W", 170, (datetime.time(14),), frozenset({"lecture_lab_lab"})),
        ])


class LabClassRecognitionTests(unittest.TestCase):
    def test_two_lab_rows_of_one_identity_become_a_lab_class(self):
        for source in (lab_rows(), tuple(reversed(lab_rows()))):
            item, = Schedule.from_records([s.to_record() for s in source]).classes
            self.assertIsInstance(item, LabClass)
            self.assertEqual(sorted(map(item.role, item.sections)), ["lab_long", "lab_short"])
            self.assertEqual([s.duration for s in item.scheduling_entries()], [170])
            self.assertEqual([s.room for s in item.sections], [s.room for s in source])

    def test_credit_hours_estimated_from_the_long_lab_length(self):
        item = LabClass(lab_rows())
        self.assertEqual(item.credit_hours, 3)  # round(170 / 60)
        self.assertEqual(teaching_loads(Schedule([item])), {"Rajib": 3})

    def test_a_lone_split_lab_raises_no_self_conflict(self):
        schedule = Schedule([LabClass(lab_rows())])
        self.assertEqual(check_conflicts(schedule), [])

    def test_a_5070_split_that_is_malformed_is_rejected_outright(self):
        long, short = lab_rows()
        for bad in (
            replace(short, room="20"),               # same room as the long lab
            replace(short, time_slot="W 3:00pm"),     # different start
            replace(short, instructor="Someone Else"),  # instructor mismatch
        ):
            with self.subTest(bad=bad), self.assertRaises(GroupingError):
                Schedule.from_records([long.to_record(), bad.to_record()])

    def test_two_same_identity_labs_that_are_not_a_split_stay_separate(self):
        long, short = lab_rows()
        classes = Schedule.from_records(
            [long.to_record(), replace(short, duration=80).to_record()]
        ).classes
        self.assertTrue(all(type(c) is NormalClass for c in classes))


class LabClassBehaviourTests(unittest.TestCase):
    def test_rooms_and_time_are_locked_instructor_links(self):
        item = LabClass(lab_rows())
        self.assertEqual(item.editable_fields(0), frozenset({"instructor"}))
        for index in (0, 1):
            with self.assertRaisesRegex(ValueError, "fixed"):
                item.apply_edit("room", index, room="7", building="Science")
            with self.assertRaisesRegex(ValueError, "fixed"):
                item.apply_edit("time", index, time_slot="W 4:00pm")
        linked = item.apply_edit("instructor", 1, instructor="Sam")
        self.assertEqual({s.instructor for s in linked.sections}, {"Sam"})

    def test_short_room_reservation_follows_the_long_lab(self):
        item = LabClass(lab_rows())
        (reservation,) = item.resource_usage(item.lab_long, item.lab_long)
        self.assertEqual(reservation.room, "29")
        self.assertEqual(reservation.instructor, "")
        self.assertEqual(reservation.time_slot, item.lab_long.time_slot)
        self.assertEqual(list(item.resource_usage(item.lab_short, item.lab_short)), [])

    def test_baseline_round_trips_and_pins_the_rooms(self):
        item = LabClass(lab_rows())
        data = item.to_records()
        self.assertTrue(all(row["Lecture Lab Baseline"] for row in data))
        restored, = Schedule.from_records(data).classes
        self.assertEqual(restored.fixed_lab_locations, item.fixed_lab_locations)
        self.assertEqual(restored.fixed_lab_slot, "W 2:00pm")
        data[0]["Room"] = "99"
        with self.assertRaisesRegex(GroupingError, "fixed"):
            Schedule.from_records(data)

    def test_unlocking_time_moves_both_rows(self):
        item = LabClass(lab_rows(), lab_time_editable=True)
        moved = item.apply_edit("time", 0, time_slot="W 4:00pm")
        self.assertEqual({s.time_slot for s in moved.sections}, {"W 4:00pm"})
        self.assertEqual([s.duration for s in moved.sections], [170, 50])


class LabClassSolverTests(unittest.TestCase):
    def test_one_decision_books_two_rooms(self):
        item = LabClass(lab_rows())
        entries = list(item.scheduling_entries())
        candidates = [section_candidates(item, s, config(), 10) for s in entries]
        self.assertEqual({(c.room, c.time_slot, c.duration) for c in candidates[0]},
                         {("20", "W 2:00pm", 170)})
        slots = build_slots(entries, [0], candidates, class_list=[item])
        self.assertEqual(len(slots), 2)
        short = next(s for s in slots if s.room_key.endswith("29"))
        self.assertEqual(short.end, datetime.time(14, 50))
        self.assertEqual(short.instructor, "")

    def test_solver_preserves_type_and_both_rows(self):
        solved = solve(Schedule([LabClass(lab_rows())]), config(),
                       search_workers=1, time_limit_seconds=5)
        result, = solved.classes
        self.assertIsInstance(result, LabClass)
        self.assertEqual(len(result.sections), 2)
        self.assertFalse(check_conflicts(solved))


if __name__ == "__main__":
    unittest.main()
