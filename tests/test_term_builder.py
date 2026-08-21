import tempfile
import unittest
from pathlib import Path

import pandas as pd

from class_schedule.class_model import CrossListingClass, FourCreditClass, NormalClass, Section
from class_schedule.schedule_model import PersonRecord, Schedule
from class_schedule.term_builder import (
    CancelSpec,
    TermChanges,
    build_draft,
    build_draft_schedule,
    load_changes,
    summarize_roster_impact,
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
        Instructor="Bain, Leslie M.",
    )
    defaults.update(overrides)
    return defaults


class CancelTests(unittest.TestCase):
    def test_cancel_with_section_removes_only_that_section(self):
        keep = NormalClass((Section(
            subject="MATH", number="0803", section="001", time_slot="MWF 9:00am",
            duration=50, room="101", instructor="Ballard, Kasey L.",
        ),))
        drop = NormalClass((Section(
            subject="MATH", number="0803", section="003", time_slot="MWF 11:00am",
            duration=50, room="102", instructor="Bain, Leslie M.",
        ),))
        template = Schedule([keep, drop])
        changes = TermChanges(cancel=(CancelSpec("MATH", "0803", "003"),))

        draft, report = build_draft_schedule(template, changes)

        self.assertEqual(draft.course_ids, ["MATH 0803-001"])
        self.assertEqual(report.cancelled, ("MATH 0803-003",))
        self.assertEqual(report.unmatched_cancels, ())

    def test_cancel_without_section_removes_every_section(self):
        a = NormalClass((Section(
            subject="MATH", number="2243", section="001", time_slot="MWF 9:00am",
            duration=50, room="101", instructor="Overduin, Matthew D.",
        ),))
        b = NormalClass((Section(
            subject="MATH", number="2243", section="002", time_slot="TR 9:30am",
            duration=80, room="102", instructor="Overduin, Matthew D.",
        ),))
        template = Schedule([a, b])
        changes = TermChanges(cancel=(CancelSpec("MATH", "2243"),))

        draft, report = build_draft_schedule(template, changes)

        self.assertEqual(draft.course_ids, [])
        self.assertEqual(set(report.cancelled), {"MATH 2243-001", "MATH 2243-002"})

    def test_unmatched_cancel_spec_is_reported(self):
        template = Schedule.from_records([make_record()])
        changes = TermChanges(cancel=(CancelSpec("MATH", "9999"),))

        draft, report = build_draft_schedule(template, changes)

        self.assertEqual(len(draft), 1)
        self.assertEqual(report.unmatched_cancels, (CancelSpec("MATH", "9999"),))


class DepartureReassignmentTests(unittest.TestCase):
    def test_normal_class_instructor_replaced_with_placeholder(self):
        template = Schedule.from_records([make_record(Instructor="Bain, Leslie M.")])
        changes = TermChanges(departures=("Bain, Leslie M.",))

        draft, report = build_draft_schedule(template, changes)

        self.assertEqual(draft.classes[0].sections[0].instructor, "Staff")
        self.assertEqual(report.reassigned, ("MATH 1113-001",))
        self.assertEqual(report.departures_not_found, ())

    def test_four_credit_class_both_rows_reassigned_together(self):
        records = [
            make_record(**{"Time Slot": "MWF 9:00am"}, Duration=50, Instructor="Bain, Leslie M."),
            make_record(**{"Time Slot": "T 9:00am"}, Duration=75, Instructor="Bain, Leslie M."),
        ]
        template = Schedule.from_records(records)
        self.assertIsInstance(template.classes[0], FourCreditClass)
        changes = TermChanges(departures=("Bain, Leslie M.",))

        draft, report = build_draft_schedule(template, changes)

        item = draft.classes[0]
        self.assertTrue(all(s.instructor == "Staff" for s in item.sections))

    def test_departure_not_present_in_template_is_reported(self):
        template = Schedule.from_records([make_record(Instructor="Ballard, Kasey L.")])
        changes = TermChanges(departures=("Nobody, Real N.",))

        draft, report = build_draft_schedule(template, changes)

        self.assertEqual(report.departures_not_found, ("Nobody, Real N.",))
        self.assertEqual(report.reassigned, ())


class NewCourseTests(unittest.TestCase):
    def test_new_normal_course_added_with_placeholder_instructor(self):
        template = Schedule([])
        changes = TermChanges(new_sections=(make_record(Number="1013", Instructor=""),))

        draft, report = build_draft_schedule(template, changes)

        self.assertEqual(draft.course_ids, ["MATH 1013-001"])
        self.assertEqual(draft.classes[0].sections[0].instructor, "Staff")
        self.assertEqual(report.added, ("MATH 1013-001",))

    def test_new_cross_listed_pair_grouped_automatically(self):
        template = Schedule([])
        changes = TermChanges(new_sections=(
            make_record(Subject="MATH", Number="1113", **{"Cross-List": "XL9"}, Instructor=""),
            make_record(Subject="STAT", Number="2163", **{"Cross-List": "XL9"}, Instructor=""),
        ))

        draft, report = build_draft_schedule(template, changes)

        self.assertEqual(len(draft), 1)
        self.assertIsInstance(draft.classes[0], CrossListingClass)
        self.assertEqual(len(report.added), 1)


class RosterImpactTests(unittest.TestCase):
    def test_splits_known_from_unknown_departures(self):
        persons = {"Bain, Leslie M.": PersonRecord(name="Bain, Leslie M.", max_load=15)}
        changes = TermChanges(departures=("Bain, Leslie M.", "Typo, Person"))

        confirmed, unknown = summarize_roster_impact(changes, persons)

        self.assertEqual(confirmed, ("Bain, Leslie M.",))
        self.assertEqual(unknown, ("Typo, Person",))


class LoadChangesAndBuildDraftTests(unittest.TestCase):
    def test_load_changes_parses_toml(self):
        with tempfile.TemporaryDirectory() as tmp:
            changes_path = Path(tmp) / "changes.toml"
            changes_path.write_text(
                """
                departures = ["Bain, Leslie M."]

                [[cancel_courses]]
                subject = "MATH"
                number = "0803"
                section = "003"

                [[new_courses]]
                Subject = "MATH"
                Number = "1013"
                Section = "001"
                "Time Slot" = "MWF 9:00am"
                Duration = 50
                """,
                encoding="utf-8",
            )
            changes = load_changes(changes_path)

        self.assertEqual(changes.departures, ("Bain, Leslie M.",))
        self.assertEqual(changes.cancel, (CancelSpec("MATH", "0803", "003"),))
        self.assertEqual(len(changes.new_sections), 1)

    def test_build_draft_end_to_end_from_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            template_path = tmp_path / "26S.csv"
            pd.DataFrame.from_records([make_record(Instructor="Bain, Leslie M.")]).to_csv(
                template_path, index=False
            )
            changes_path = tmp_path / "changes.toml"
            changes_path.write_text(
                'departures = ["Bain, Leslie M."]\n', encoding="utf-8"
            )
            output_path = tmp_path / "27S_draft.xlsx"

            draft, report = build_draft(
                template_path, changes_path, output_path=output_path
            )

            self.assertEqual(draft.classes[0].sections[0].instructor, "Staff")
            self.assertEqual(report.reassigned, ("MATH 1113-001",))
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
