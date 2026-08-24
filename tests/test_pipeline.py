from __future__ import annotations

import tempfile
import unittest
import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from class_schedule.class_model import NormalClass, Section
from class_schedule.data_cleaning import (
    NORMALIZED_COLUMNS,
    clean_dataframe,
    clean_file,
    initialize_input,
)
from class_schedule.overrides import (
    apply_overrides,
    load_overrides,
    locks_for_section,
    validate_override_context,
)
from class_schedule.schedule_model import Schedule, TimeWindow
from class_schedule.schedule_io import read_schedule
from class_schedule.solver import MeetingPattern, RoomRecord, SolverConfig, diff_schedules
from class_schedule.solver.candidates import section_candidates
from class_schedule.solver.config import resolve_config_paths


class DataCleaningTests(unittest.TestCase):
    def test_normalizes_alias_columns_and_rejects_bad_rows(self):
        frame = pd.DataFrame([
            {
                "Subject": "math", "Number": "1113", "Section": "001",
                "Meeting_Days": "MWF", "Meeting_Times": "9:00 am-9:50 am",
                "Instructor Name": "Alice", "Room": "101", "Building": "Corley",
                "CRN": "12345", "Seats_Avail": "4",
            },
            {"Subject": "MATH", "Number": "", "Section": "002"},
        ])
        result = clean_dataframe(frame)
        self.assertEqual(tuple(result.normalized.columns), NORMALIZED_COLUMNS)
        self.assertEqual(result.normalized.iloc[0]["Time Slot"], "MWF 9:00am")
        self.assertEqual(result.normalized.iloc[0]["Delivery Mode"], "in_person")
        self.assertEqual(result.normalized.iloc[0]["CRN"], "12345")
        self.assertEqual(result.normalized.iloc[0]["Source Row"], 2)
        self.assertEqual(result.rejected.iloc[0]["Source Row"], 3)

    def test_clean_file_writes_auditable_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "raw.csv"
            pd.DataFrame([{
                "Subject": "MATH", "Number": "1113", "Section": "001",
                "Time Slot": "ONLINE", "Instructor": "Alice",
            }]).to_csv(source, index=False)
            destination = root / "normalized"
            clean_file(source, destination)
            self.assertTrue((destination / "sections.csv").is_file())
            self.assertTrue((destination / "rejected_rows.csv").is_file())
            self.assertTrue((destination / "validation.md").is_file())
            self.assertTrue((destination / "source_manifest.json").is_file())

    def test_initialize_writes_pre_change_views_beside_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Course Schedule Report.csv"
            pd.DataFrame([
                {
                    "Subject": "MATH", "Number": "1113", "Section": "001",
                    "Time Slot": "MWF 9:00am", "Duration": "50",
                    "Instructor": "Original Instructor", "Room": "101",
                    "Building": "Corley",
                },
                {
                    "Subject": "STAT", "Number": "2163", "Section": "001",
                    "Time Slot": "ONLINE", "Instructor": "Online Instructor",
                },
            ]).to_csv(source, index=False)

            result = initialize_input(source, root / "normalized")

            instructor_path = root / "Course Schedule Report_instructor.xlsx"
            room_path = root / "Course Schedule Report_room.xlsx"
            self.assertEqual(result.instructor_path, instructor_path)
            self.assertEqual(result.room_path, room_path)
            workbook = load_workbook(instructor_path, read_only=True)
            try:
                self.assertEqual(
                    set(workbook.sheetnames),
                    {"Original Instructor", "Online Instructor"},
                )
            finally:
                workbook.close()
            workbook = load_workbook(room_path, read_only=True)
            try:
                self.assertEqual(workbook.sheetnames, ["Corley 101"])
            finally:
                workbook.close()

    def test_initialize_skips_views_when_a_source_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "raw.csv"
            pd.DataFrame([
                {"Subject": "MATH", "Number": "", "Section": "001"},
            ]).to_csv(source, index=False)

            result = initialize_input(source, root / "normalized")

            self.assertIsNone(result.instructor_path)
            self.assertIsNone(result.room_path)
            self.assertFalse((root / "raw_instructor.xlsx").exists())
            self.assertFalse((root / "raw_room.xlsx").exists())

    def test_known_cross_list_stays_unmarked_but_groups_during_validation(self):
        frame = pd.DataFrame([
            {"Subject": "MATH", "Number": "5173", "Section": "TC1",
             "Time Slot": "TBA", "Instructor": "Jordan, Scott M."},
            {"Subject": "STAT", "Number": "4173", "Section": "TC1",
             "Time Slot": "TBA", "Instructor": "Jordan, Scott M."},
        ])
        result = clean_dataframe(frame)
        self.assertEqual(len(set(result.normalized["Cross-List"])), 1)
        self.assertEqual(result.normalized.iloc[0]["Cross-List"], "")
        self.assertEqual(len(Schedule.from_dataframe(result.normalized)), 1)


class ScheduleIOTests(unittest.TestCase):
    def test_csv_becomes_a_grouped_schedule_at_the_file_boundary(self):
        frame = pd.DataFrame([
            {"Subject": "MATH", "Number": "5173", "Section": "TC1",
             "Time Slot": "TBA", "Instructor": "Jordan, Scott M."},
            {"Subject": "STAT", "Number": "4173", "Section": "TC1",
             "Time Slot": "TBA", "Instructor": "Jordan, Scott M."},
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.csv"
            frame.to_csv(path, index=False)
            schedule = read_schedule(path)

        self.assertEqual(len(schedule), 1)
        self.assertEqual(
            set(schedule.classes[0].course_ids),
            {"MATH 5173-TC1", "STAT 4173-TC1"},
        )


class OverrideTests(unittest.TestCase):
    def test_load_and_apply_edit_and_lock(self):
        schedule = Schedule([NormalClass((Section(
            "MATH", "1113", "001", "MWF 9:00am", 50,
            "101", "Alice", "Corley",
        ),))])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overrides.toml"
            path.write_text(
                '[[edits]]\ncourse_id = "MATH 1113-001"\n'
                'time_slot = "TR 9:30am"\nroom = "269"\nbuilding = "Corley"\n\n'
                '[[locks]]\ncourse_id = "MATH 1113-001"\n'
                'fields = ["time", "room", "building"]\n',
                encoding="utf-8",
            )
            overrides = load_overrides(path)
        changed = apply_overrides(schedule, overrides)
        section = changed.get("MATH 1113-001").sections[0]
        self.assertEqual(section.time_slot, "TR 9:30am")
        self.assertEqual(section.room, "269")
        self.assertEqual(
            locks_for_section(overrides.locks, ("MATH 1113-001",), 0),
            frozenset({"time", "room", "building"}),
        )

    def test_lock_filters_solver_candidates(self):
        section = Section(
            "MATH", "1113", "001", "MWF 9:00am", 50,
            "101", "Alice", "Corley",
        )
        config = SolverConfig(
            persons={}, preferences={},
            meeting_patterns=[MeetingPattern(
                "MWF", 50, (datetime.time(9), datetime.time(10)),
                frozenset({"normal"}),
            )],
            rooms=[RoomRecord("Corley", "101")], blackouts=[],
        )
        candidates = section_candidates(
            NormalClass((section,)), section, config, 40, frozenset({"time"})
        )
        self.assertTrue(candidates)
        self.assertEqual({candidate.time_slot for candidate in candidates}, {"MWF 9:00am"})

    def test_configured_time_family_rejects_an_unlisted_current_start(self):
        section = Section(
            "MATH", "1003", "004", "MWF 11:50am", 50,
            "269", "Staff", "Corley",
        )
        config = SolverConfig(
            persons={}, preferences={},
            meeting_patterns=[MeetingPattern(
                "MWF", 50,
                (datetime.time(10), datetime.time(11), datetime.time(12)),
                frozenset({"normal"}),
            )],
            rooms=[RoomRecord("Corley", "269")],
            blackouts=[TimeWindow(
                frozenset("F"), datetime.time(12), datetime.time(12, 50)
            )],
        )
        candidates = section_candidates(
            NormalClass((section,)), section, config, 40,
        )
        slots = {candidate.time_slot for candidate in candidates}
        self.assertNotIn("MWF 11:50am", slots)
        self.assertNotIn("MWF 12:00pm", slots)
        self.assertIn("MWF 10:00am", slots)

    def test_explicit_seminar_pattern_keeps_a_nonstandard_time(self):
        section = Section(
            "MATH", "4971", "001", "T 11:00am", 80,
            "101", "Alice", "Corley",
        )
        config = SolverConfig(
            persons={}, preferences={},
            meeting_patterns=[
                MeetingPattern(
                    "TR", 80, (datetime.time(11),),
                    frozenset({"normal"}),
                ),
                MeetingPattern(
                    "T", 80, (datetime.time(11),),
                    frozenset({"normal"}),
                    frozenset({"MATH 4971"}),
                ),
            ],
            rooms=[RoomRecord("Corley", "101")], blackouts=[],
        )
        candidates = section_candidates(
            NormalClass((section,)), section, config, 40
        )
        self.assertIn(
            "T 11:00am", {candidate.time_slot for candidate in candidates}
        )

    def test_version_bound_override_rejects_the_wrong_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overrides.toml"
            path.write_text(
                'term = "27S"\nsource_version = "ver10"\n',
                encoding="utf-8",
            )
            overrides = load_overrides(path)
        validate_override_context(overrides, term="27S", source_version="ver10")
        with self.assertRaisesRegex(ValueError, "source_version"):
            validate_override_context(overrides, term="27S", source_version="ver9")
        with self.assertRaisesRegex(ValueError, "term"):
            validate_override_context(overrides, term="27F", source_version="ver10")


class ConfigLayoutTests(unittest.TestCase):
    def test_term_files_override_flat_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog").mkdir()
            (root / "terms" / "27S").mkdir(parents=True)
            for name in ("persons.toml", "locations.toml"):
                (root / "catalog" / name).write_text("", encoding="utf-8")
            for name in ("preferences.toml", "timeslot.toml"):
                (root / "terms" / "27S" / name).write_text("", encoding="utf-8")
                (root / name).write_text("legacy", encoding="utf-8")
            paths = resolve_config_paths(root, "27S")
            self.assertEqual(paths["preferences.toml"].parent.name, "27S")
            self.assertEqual(paths["persons.toml"].parent.name, "catalog")


class CumulativeDiffTests(unittest.TestCase):
    def test_matches_by_course_identity_not_row_position(self):
        first = NormalClass((Section(
            "MATH", "1113", "001", "MWF 9:00am", 50,
            "101", "Alice", "Corley",
        ),))
        second = NormalClass((Section(
            "MATH", "2103", "002", "MWF 10:00am", 50,
            "102", "Bob", "Corley",
        ),))
        changed_first = NormalClass((Section(
            "MATH", "1113", "001", "MWF 11:00am", 50,
            "101", "Alice", "Corley",
        ),))
        changes = diff_schedules(
            Schedule([first, second]), Schedule([second, changed_first])
        )
        self.assertEqual(
            [(change.course_id, change.field) for change in changes],
            [("MATH 1113-001", "time")],
        )

    def test_reports_added_and_removed_sections(self):
        before = Schedule([NormalClass((Section(
            "MATH", "1113", "001", "ONLINE", None, "", "Alice",
        ),))])
        after = Schedule([NormalClass((Section(
            "MATH", "2103", "002", "ONLINE", None, "", "Bob",
        ),))])
        changes = diff_schedules(before, after)
        self.assertEqual(
            [(change.course_id, change.field, change.after) for change in changes],
            [
                ("MATH 1113-001", "status", "removed"),
                ("MATH 2103-002", "status", "added"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
