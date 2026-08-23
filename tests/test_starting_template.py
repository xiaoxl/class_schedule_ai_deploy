import tempfile
import unittest
from pathlib import Path

import pandas as pd

from class_schedule.class_model import NormalClass, Section
from class_schedule.schedule_model import PersonRecord, Schedule, check_conflicts
from class_schedule.starting_template import (
    _classes_conflict,
    build_starting_templates,
    place_new_hires,
    recolor_placeholder,
)


def make_class(number, section, time_slot, instructor="Staff", room="101") -> NormalClass:
    return NormalClass((Section(
        subject="MATH", number=number, section=section, time_slot=time_slot,
        duration=50, room=room, instructor=instructor, building="Corley",
    ),))


class ClassesConflictTests(unittest.TestCase):
    def test_overlapping_times_conflict(self):
        a = make_class("1113", "001", "MWF 9:00am")
        b = make_class("1003", "001", "MWF 9:00am")
        self.assertTrue(_classes_conflict(a, b))

    def test_non_overlapping_times_do_not_conflict(self):
        a = make_class("1113", "001", "MWF 9:00am")
        b = make_class("1003", "001", "MWF 10:00am")
        self.assertFalse(_classes_conflict(a, b))

    def test_online_sections_never_conflict(self):
        online = NormalClass((Section(
            subject="MATH", number="1113", section="TC1", time_slot="TBA",
            duration=None, room="", instructor="Staff",
        ),))
        also_online = NormalClass((Section(
            subject="MATH", number="1003", section="TC1", time_slot="TBA",
            duration=None, room="", instructor="Staff",
        ),))
        self.assertFalse(_classes_conflict(online, also_online))


class PlaceNewHiresTests(unittest.TestCase):
    def test_takes_over_a_qualified_open_position(self):
        open_slot = make_class("1113", "001", "MWF 9:00am")
        schedule = Schedule([open_slot])
        persons = {"Yousuf, Marium": PersonRecord(
            name="Yousuf, Marium", max_load=15, courses=["MATH 1113"],
        )}
        placed, assignments = place_new_hires(schedule, ("Yousuf, Marium",), persons)
        self.assertEqual(assignments, {"Yousuf, Marium": ("MATH 1113-001",)})
        self.assertEqual(placed.get("MATH 1113-001").sections[0].instructor, "Yousuf, Marium")

    def test_ignores_an_open_position_the_hire_is_not_qualified_for(self):
        open_slot = make_class("2703", "001", "MWF 9:00am")
        schedule = Schedule([open_slot])
        persons = {"Yousuf, Marium": PersonRecord(
            name="Yousuf, Marium", max_load=15, courses=["MATH 1113"],
        )}
        placed, assignments = place_new_hires(schedule, ("Yousuf, Marium",), persons)
        self.assertEqual(assignments, {})
        self.assertEqual(placed.get("MATH 2703-001").sections[0].instructor, "Staff")

    def test_stops_at_max_load_rather_than_overfilling(self):
        # Two qualified, non-conflicting 3-credit open slots; max_load 3
        # should only pick up one of them.
        a = make_class("1113", "001", "MWF 9:00am")
        b = make_class("1113", "002", "MWF 10:00am")
        schedule = Schedule([a, b])
        persons = {"Yousuf, Marium": PersonRecord(
            name="Yousuf, Marium", max_load=3, courses=["MATH 1113"],
        )}
        _, assignments = place_new_hires(schedule, ("Yousuf, Marium",), persons)
        self.assertEqual(len(assignments["Yousuf, Marium"]), 1)

    def test_skips_a_qualified_open_position_that_would_conflict(self):
        # Two qualified open slots that overlap in time -- only one can
        # be taken, since the hire can't teach both at once.
        a = make_class("1113", "001", "MWF 9:00am")
        b = make_class("1113", "002", "MWF 9:00am")
        schedule = Schedule([a, b])
        persons = {"Yousuf, Marium": PersonRecord(
            name="Yousuf, Marium", max_load=15, courses=["MATH 1113"],
        )}
        _, assignments = place_new_hires(schedule, ("Yousuf, Marium",), persons)
        self.assertEqual(len(assignments["Yousuf, Marium"]), 1)

    def test_falls_back_to_an_overloaded_instructors_class(self):
        overloaded = make_class("1113", "001", "MWF 9:00am", instructor="Bain, Leslie M.")
        schedule = Schedule([overloaded])
        persons = {
            # MATH 1113 is 3 credit hours -- max_load 2 makes her over it.
            "Bain, Leslie M.": PersonRecord(name="Bain, Leslie M.", max_load=2, courses=["MATH 1113"]),
            "Yousuf, Marium": PersonRecord(name="Yousuf, Marium", max_load=15, courses=["MATH 1113"]),
        }
        _, assignments = place_new_hires(schedule, ("Yousuf, Marium",), persons)
        self.assertEqual(assignments, {"Yousuf, Marium": ("MATH 1113-001",)})

    def test_never_touches_a_not_overloaded_instructors_class(self):
        fine = make_class("1113", "001", "MWF 9:00am", instructor="Bain, Leslie M.")
        schedule = Schedule([fine])
        persons = {
            "Bain, Leslie M.": PersonRecord(name="Bain, Leslie M.", max_load=15, courses=["MATH 1113"]),
            "Yousuf, Marium": PersonRecord(name="Yousuf, Marium", max_load=15, courses=["MATH 1113"]),
        }
        placed, assignments = place_new_hires(schedule, ("Yousuf, Marium",), persons)
        self.assertEqual(assignments, {})
        self.assertEqual(placed.get("MATH 1113-001").sections[0].instructor, "Bain, Leslie M.")

    def test_prefers_an_open_position_over_an_overloaded_instructor(self):
        overloaded = make_class("1113", "001", "MWF 9:00am", instructor="Bain, Leslie M.")
        open_slot = make_class("1113", "002", "MWF 10:00am")
        schedule = Schedule([overloaded, open_slot])
        persons = {
            "Bain, Leslie M.": PersonRecord(name="Bain, Leslie M.", max_load=2, courses=["MATH 1113"]),
            "Yousuf, Marium": PersonRecord(name="Yousuf, Marium", max_load=3, courses=["MATH 1113"]),
        }
        _, assignments = place_new_hires(schedule, ("Yousuf, Marium",), persons)
        self.assertEqual(assignments, {"Yousuf, Marium": ("MATH 1113-002",)})

    def test_stops_rather_than_forcing_a_bad_fit(self):
        # Nothing qualified is open, and no one qualified is overloaded --
        # placement should simply do nothing, not raise or force a pick.
        someone_elses = make_class("2703", "001", "MWF 9:00am", instructor="Overduin, Matthew D.")
        schedule = Schedule([someone_elses])
        persons = {
            "Overduin, Matthew D.": PersonRecord(name="Overduin, Matthew D.", max_load=12, courses=["MATH 2703"]),
            "Yousuf, Marium": PersonRecord(name="Yousuf, Marium", max_load=15, courses=["MATH 1113"]),
        }
        placed, assignments = place_new_hires(schedule, ("Yousuf, Marium",), persons)
        self.assertEqual(assignments, {})
        self.assertEqual(check_conflicts(placed), [])

    def test_unknown_hire_name_is_skipped_not_an_error(self):
        schedule = Schedule([make_class("1113", "001", "MWF 9:00am")])
        placed, assignments = place_new_hires(schedule, ("Nobody, Real",), {})
        self.assertEqual(assignments, {})


class RecolorPlaceholderTests(unittest.TestCase):
    def test_no_conflicts_everyone_keeps_the_plain_placeholder(self):
        a = make_class("1113", "001", "MWF 9:00am")
        b = make_class("1003", "001", "MWF 10:00am")
        schedule = Schedule([a, b])
        recolored, assignments = recolor_placeholder(schedule, seed=1)
        self.assertEqual(set(assignments), {"Staff"})
        self.assertEqual(check_conflicts(recolored), [])

    def test_existing_numbered_placeholders_collapse_when_no_longer_needed(self):
        a = make_class("1113", "001", "MWF 9:00am", instructor="Staff")
        b = make_class("1003", "001", "MWF 10:00am", instructor="Staff 2")
        recolored, assignments = recolor_placeholder(Schedule([a, b]), seed=1)
        self.assertEqual(set(assignments), {"Staff"})
        self.assertEqual(
            {s.instructor for item in recolored.classes for s in item.sections},
            {"Staff"},
        )

    def test_two_overlapping_classes_split_into_two_identities(self):
        a = make_class("1113", "001", "MWF 9:00am", room="101")
        b = make_class("1003", "001", "MWF 9:00am", room="102")
        schedule = Schedule([a, b])
        recolored, assignments = recolor_placeholder(schedule, seed=1)
        self.assertEqual(len(assignments), 2)
        self.assertEqual(check_conflicts(recolored), [])
        instructors = {s.instructor for item in recolored.classes for s in item.sections}
        self.assertEqual(len(instructors), 2)

    def test_three_mutually_overlapping_classes_need_three_identities(self):
        a = make_class("1113", "001", "MWF 9:00am", room="101")
        b = make_class("1003", "001", "MWF 9:00am", room="102")
        c = make_class("2914", "001", "MWF 9:00am", room="103")
        schedule = Schedule([a, b, c])
        recolored, assignments = recolor_placeholder(schedule, seed=1)
        self.assertEqual(len(assignments), 3)
        self.assertEqual(check_conflicts(recolored), [])

    def test_a_real_instructors_class_is_left_untouched(self):
        real = NormalClass((Section(
            subject="MATH", number="9999", section="001", time_slot="MWF 9:00am",
            duration=50, room="999", instructor="Bain, Leslie M.",
        ),))
        placeholder = make_class("1113", "001", "MWF 10:00am")
        schedule = Schedule([real, placeholder])
        recolored, assignments = recolor_placeholder(schedule, seed=1)
        self.assertNotIn("Bain, Leslie M.", assignments)
        result_instructor = recolored.get("MATH 9999-001").sections[0].instructor
        self.assertEqual(result_instructor, "Bain, Leslie M.")

    def test_same_seed_is_reproducible(self):
        a = make_class("1113", "001", "MWF 9:00am")
        b = make_class("1003", "001", "MWF 9:00am")
        c = make_class("2914", "001", "MWF 10:00am")
        first, first_assignments = recolor_placeholder(Schedule([a, b, c]), seed=7)
        second, second_assignments = recolor_placeholder(Schedule([a, b, c]), seed=7)
        self.assertEqual(first_assignments, second_assignments)


class BuildStartingTemplatesTests(unittest.TestCase):
    def test_writes_both_conflict_free_csvs_and_places_a_new_hire(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            template_path = tmp_path / "26S.csv"
            pd.DataFrame.from_records([
                {
                    "Subject": "MATH", "Number": "1113", "Section": "001",
                    "Time Slot": "MWF 9:00am", "Duration": 50, "Room": "101",
                    "Building": "Corley", "Instructor": "Bain, Leslie M.",
                },
            ]).to_csv(template_path, index=False)

            changes_path = tmp_path / "changes.toml"
            changes_path.write_text(
                'departures = ["Bain, Leslie M."]\n'
                'new_hires = ["Yousuf, Marium"]\n'
                "\n"
                "[[new_courses]]\n"
                'Subject = "MATH"\n'
                'Number = "1003"\n'
                'Section = "001"\n'
                '"Time Slot" = "MWF 11:00am"\n'
                "Duration = 50\n",
                encoding="utf-8",
            )
            persons_path = tmp_path / "persons.toml"
            persons_path.write_text(
                '[[persons]]\n'
                'name = "Yousuf, Marium"\n'
                "max_load = 15\n"
                'courses = ["MATH 1113"]\n',
                encoding="utf-8",
            )

            results = build_starting_templates(
                template_path, changes_path, persons_path,
                output_dir=tmp_path, seed=1,
            )

            self.assertTrue((tmp_path / "starting.csv").exists())
            self.assertTrue((tmp_path / "starting_noadding.csv").exists())

            starting = results["starting"]
            self.assertEqual(
                starting["hire_assignments"], {"Yousuf, Marium": ("MATH 1113-001",)}
            )
            self.assertEqual(check_conflicts(starting["schedule"]), [])

            # starting_noadding never sees the new MATH 1003 course at all.
            noadding = results["starting_noadding"]
            with self.assertRaises(KeyError):
                noadding["schedule"].get("MATH 1003-001")
            self.assertEqual(check_conflicts(noadding["schedule"]), [])

            written_back = Schedule.from_dataframe(
                pd.read_csv(tmp_path / "starting.csv", dtype=str)
            )
            self.assertEqual(check_conflicts(written_back), [])


if __name__ == "__main__":
    unittest.main()
