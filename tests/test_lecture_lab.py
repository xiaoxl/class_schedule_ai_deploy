import datetime
import itertools
import tempfile
import tomllib
import unittest
from dataclasses import replace
from pathlib import Path

from class_schedule import (
    LabClass,
    LectureLabClass,
    NormalClass,
    Schedule,
    Section,
    teaching_loads,
)
from class_schedule.config_inference import infer_configuration_from_template
from class_schedule.config_schema import CourseRelationshipSchema, CoursesFileSchema
from class_schedule.overrides import OverrideEdit, OverrideFile, apply_overrides
from class_schedule.schedule_io import read_schedule
from class_schedule.schedule_model import GroupingError, check_atomic_class_rules, check_conflicts
from class_schedule.solver import SolverConfig, MeetingPattern, RoomRecord, InfeasibleSchedule, solve
from class_schedule.solver.candidates import section_candidates
from class_schedule.solver.constraints import build_slots
from class_schedule.webapp import _serialize_schedule


def rows(number="3245", section="1"):
    """One CLAS row plus a 50/170 split-room lab, all one course number."""
    base = dict(subject="CHEM", number=number, section=section, instructor="Alice", building="Science")
    return (
        Section(**base, type="CLAS", time_slot="MWF 9:00am", duration=50, room="10"),
        Section(**base, type="LAB", time_slot="M 1:00pm", duration=50, room="20"),
        Section(**base, type="LAB", time_slot="M 1:00pm", duration=170, room="30"),
    )


def sibling_rows():
    """CHEM 3264 CLAS linked to its catalog-sibling CHEM 3260 split lab."""
    lab = dict(subject="CHEM", number="3260", section="1", instructor="Alice", building="Science")
    return (
        Section(subject="CHEM", number="3264", section="1", instructor="Alice",
                building="Science", type="CLAS", time_slot="MWF 9:00am", duration=50, room="10"),
        Section(**lab, type="LAB", time_slot="M 1:00pm", duration=50, room="20"),
        Section(**lab, type="LAB", time_slot="M 1:00pm", duration=170, room="30"),
    )


def config():
    return SolverConfig(persons={}, preferences={}, rooms=[RoomRecord("Science", "99")],
        meeting_patterns=[
            MeetingPattern("MWF", 50, (datetime.time(9), datetime.time(10)),
                           frozenset({"lecture_lab_lecture", "normal"})),
            MeetingPattern("M", 170, (datetime.time(13), datetime.time(16)),
                           frozenset({"lecture_lab_lab"})),
        ])


class LectureLabRecognitionTests(unittest.TestCase):
    def test_same_course_number_three_rows_any_order(self):
        for source in itertools.permutations(rows()):
            item, = Schedule.from_records([s.to_record() for s in source]).classes
            self.assertIsInstance(item, LectureLabClass)
            self.assertEqual([s.room for s in item.sections], [s.room for s in source])
            self.assertEqual([s.duration for s in item.scheduling_entries()], [50, 170])
            self.assertEqual(len(item.to_records()), 3)
        # Shared course number -> catalog credits counted once.
        self.assertEqual(teaching_loads(Schedule([LectureLabClass(rows())])), {"Alice": 5})

    def test_catalog_sibling_lecture_and_lab_are_linked(self):
        item, = Schedule.from_records([s.to_record() for s in sibling_rows()]).classes
        self.assertIsInstance(item, LectureLabClass)
        self.assertEqual(sorted(item.course_ids), ["CHEM 3260-1", "CHEM 3264-1"])
        self.assertEqual(item.lecture.number, "3264")
        self.assertEqual(item.lab_long.number, "3260")
        # Trailing digits add: 3264 -> 4, 3260 -> 0.
        self.assertEqual(item.credit_hours, 4)
        self.assertEqual([s.duration for s in item.scheduling_entries()], [50, 170])

    def test_catalog_sibling_with_a_single_plain_lab(self):
        lecture = Section(subject="CHEM", number="2134", section="2", instructor="Bo",
                          building="Sci", type="CLAS", time_slot="TR 9:30am", duration=80, room="103")
        lab = Section(subject="CHEM", number="2130", section="2", instructor="Bo",
                      building="Sci", type="LAB", time_slot="W 11:00am", duration=170, room="23")
        item, = Schedule.from_records([lecture.to_record(), lab.to_record()]).classes
        self.assertIsInstance(item, LectureLabClass)
        self.assertEqual(item.role(item.lab_long), "lab_single")
        self.assertEqual(item.credit_hours, 4)
        self.assertEqual(list(item.resource_usage(item.lab_long, item.lab_long)), [])

    def test_same_section_and_instructor_but_unrelated_numbers_stay_apart(self):
        lecture = Section(subject="CHEM", number="2124", section="1", instructor="Cy",
                          building="Sci", type="CLAS", time_slot="MWF 11:00am", duration=50, room="152")
        lab = Section(subject="CHEM", number="3250", section="1", instructor="Cy",
                      building="Sci", type="LAB", time_slot="R 11:00am", duration=170, room="20")
        classes = Schedule.from_records([lecture.to_record(), lab.to_record()]).classes
        self.assertEqual({type(c).__name__ for c in classes}, {"NormalClass"})

    def test_arranged_lab_links_only_through_an_explicit_relationship(self):
        lecture = Section(subject="CHEM", number="3344", section="1", instructor="Am",
                          type="CLAS", time_slot="TR 8:00am", duration=80, room="7", building="Sci")
        lab = Section(subject="CHEM", number="3340", section="1", instructor="Am",
                      type="LAB", time_slot="T 2:00pm", duration=170, room="", building="")
        records = [lecture.to_record(), lab.to_record()]
        self.assertEqual(
            {type(c).__name__ for c in Schedule.from_records(records).classes},
            {"NormalClass"},
        )
        relation = CourseRelationshipSchema(kind="lecture_lab", members=["CHEM 3344 1", "CHEM 3340 1"])
        item, = Schedule.from_records(records, relationships=[relation]).classes
        self.assertIsInstance(item, LectureLabClass)

    def test_three_rows_that_are_not_one_lecture_two_labs_are_rejected(self):
        lecture, short, long = rows()
        with self.assertRaises(GroupingError):
            Schedule.from_records([s.to_record() for s in (lecture, short, replace(long, duration=250))])
        with self.assertRaises(GroupingError):
            Schedule.from_records([s.to_record() for s in (lecture, short, replace(long, room="20"))])


class LectureLabEditingTests(unittest.TestCase):
    def test_lecture_room_and_time_are_editable(self):
        item = LectureLabClass(rows())
        self.assertEqual(item.editable_fields(0), frozenset({"instructor", "time", "room", "section"}))
        moved = item.apply_edit("time", 0, time_slot="MWF 10:00am")
        self.assertEqual(moved.lecture.time_slot, "MWF 10:00am")
        self.assertEqual(moved.lab_long.time_slot, "M 1:00pm")
        rehoused = item.apply_edit("room", 0, room="55", building="Science")
        self.assertEqual(rehoused.lecture.room, "55")

    def test_lab_rooms_and_time_stay_locked(self):
        item = LectureLabClass(rows())
        for index in (1, 2):
            with self.assertRaisesRegex(ValueError, "fixed"):
                item.apply_edit("room", index, room="99", building="Science")
            with self.assertRaisesRegex(ValueError, "fixed"):
                item.apply_edit("time", index, time_slot="M 4:00pm")

    def test_instructor_edit_links_every_row(self):
        item = LectureLabClass(tuple(reversed(rows())))
        for index in range(3):
            updated = item.apply_edit("instructor", index, instructor="Bob")
            self.assertEqual({s.instructor for s in updated.sections}, {"Bob"})

    def test_unlocking_lab_time_moves_both_rooms_together(self):
        item = LectureLabClass(rows(), lab_time_editable=True)
        moved = item.apply_edit("time", 2, time_slot="M 4:00pm", duration=170)
        self.assertEqual([s.duration for s in moved._lab_sections()], [50, 170])
        self.assertEqual({s.time_slot for s in moved._lab_sections()}, {"M 4:00pm"})
        relation = CourseRelationshipSchema(kind="lecture_lab", members=["CHEM 3245 1"], lab_time_editable=True)
        restored, = Schedule.from_records(moved.to_records(), relationships=[relation]).classes
        self.assertTrue(restored.lab_time_editable)
        self.assertEqual(restored.fixed_lab_slot, "M 1:00pm")

    def test_internal_overlap_is_a_reportable_issue(self):
        item = LectureLabClass(rows()).apply_edit("time", 0, time_slot="M 1:00pm")
        self.assertFalse(item.validate())
        self.assertEqual(
            check_atomic_class_rules(Schedule([item]))[0].rule, "lecture_lab_invalid",
        )

    def test_baseline_round_trips_and_pins_the_lab(self):
        import pandas as pd
        from class_schedule.data_cleaning import clean_dataframe
        item = LectureLabClass(rows())
        data = item.to_records()
        self.assertEqual(data[0]["Lecture Lab Baseline"], "")
        self.assertTrue(data[2]["Lecture Lab Baseline"])
        cleaned = clean_dataframe(pd.DataFrame(data))
        self.assertFalse(cleaned.warnings)
        restored, = Schedule.from_dataframe(cleaned.normalized).classes
        self.assertEqual(restored.fixed_lab_locations, item.fixed_lab_locations)
        data[2]["Room"] = "99"
        with self.assertRaisesRegex(GroupingError, "fixed"):
            Schedule.from_records(data)

    def test_overrides_enforce_locks_and_link_instructor(self):
        schedule = Schedule([LectureLabClass(rows())])
        edited = apply_overrides(schedule, OverrideFile(edits=(
            OverrideEdit("CHEM 3245-1", record=1, instructor="Bob"),
        )))
        self.assertEqual({s.instructor for s in edited.classes[0].sections}, {"Bob"})
        with self.assertRaisesRegex(ValueError, "fixed"):
            apply_overrides(schedule, OverrideFile(edits=(
                OverrideEdit("CHEM 3245-1", record=1, time_slot="M 4:00pm"),
            )))


class LectureLabSolverTests(unittest.TestCase):
    def test_candidates_lock_the_lab_and_free_the_lecture(self):
        from class_schedule.schedule_model import PersonRecord
        item = LectureLabClass(rows())
        cfg = replace(config(), persons={"Bob": PersonRecord("Bob", 5, ("CHEM 3245",))})
        lab = section_candidates(item, item.lab_long, cfg, 10)
        self.assertEqual({c.instructor for c in lab}, {"Alice", "Bob"})
        self.assertEqual({(c.room, c.time_slot, c.duration) for c in lab}, {("30", "M 1:00pm", 170)})
        lecture = section_candidates(item, item.lecture, cfg, 10)
        self.assertIn("99", {c.room for c in lecture})

    def test_two_decisions_generate_three_room_occupancies(self):
        item = LectureLabClass(rows())
        entries = list(item.scheduling_entries())
        candidates = [section_candidates(item, s, config(), 10) for s in entries]
        slots = build_slots(entries, [0, 0], candidates, class_list=[item])
        lab_slots = [s for s in slots if s.section == 1]
        self.assertEqual(len(lab_slots), 2)
        short = next(s for s in lab_slots if s.room_key.endswith("20"))
        long = next(s for s in lab_slots if s.room_key.endswith("30"))
        self.assertEqual((short.end, long.end), (datetime.time(13, 50), datetime.time(15, 50)))
        self.assertEqual((short.instructor, long.instructor), ("", "Alice"))
        self.assertEqual((short.section, short.candidate), (long.section, long.candidate))

    def test_short_room_hard_rules_and_preferences_are_not_lost(self):
        from class_schedule.schedule_model import ConstraintRule, PreferenceRule, check_soft_preferences
        item = LectureLabClass(rows())
        cfg = replace(config(), constraint_rules=(
            ConstraintRule(direction="-", course="CHEM 3245", room="Science 20"),
        ))
        self.assertEqual(section_candidates(item, item.lab_long, cfg, 10), [])
        rules = (
            PreferenceRule(course="CHEM 3245", direction="dislike", weight=7),
            PreferenceRule(room="Science 20", direction="dislike", weight=11),
        )
        cfg = replace(config(), global_rules=rules)
        candidates = [section_candidates(item, s, cfg, 10) for s in item.scheduling_entries()]
        self.assertEqual(sum(min(c.cost for c in values) for values in candidates), 25)
        _, findings = check_soft_preferences(Schedule([item]), {}, {}, global_rules=rules)
        self.assertEqual(sum(f.penalty for f in findings if f.rule == "custom_rule"), 25)

    def test_solver_preserves_type_and_rows(self):
        item = LectureLabClass(rows())
        solved = solve(Schedule([item]), config(), search_workers=1, time_limit_seconds=5)
        result, = solved.classes
        self.assertIsInstance(result, LectureLabClass)
        self.assertEqual(len(result.sections), 3)
        self.assertEqual(result.fixed_lab_locations, item.fixed_lab_locations)
        self.assertEqual(result.lab_long.time_slot, item.lab_long.time_slot)
        self.assertFalse(check_conflicts(solved))

    def test_solver_can_move_the_lecture_clear_of_the_lab(self):
        item = LectureLabClass(rows()).apply_edit("time", 0, time_slot="M 1:00pm")
        solved = solve(Schedule([item]), config(), search_workers=1, time_limit_seconds=5)
        self.assertTrue(solved.classes[0].validate())

    def test_excluding_a_previous_solution_keeps_the_lab_put(self):
        original = Schedule([LectureLabClass(rows())])
        first = solve(original, config(), search_workers=1, time_limit_seconds=5)
        second = solve(original, config(), previous=first, search_workers=1, time_limit_seconds=5)
        self.assertEqual(
            first.classes[0].lab_long.time_slot, second.classes[0].lab_long.time_slot,
        )
        self.assertNotEqual(
            (first.classes[0].lecture.time_slot, first.classes[0].lecture.room),
            (second.classes[0].lecture.time_slot, second.classes[0].lecture.room),
        )


class LectureLabViewTests(unittest.TestCase):
    def test_serialized_metadata_frees_the_lecture_row(self):
        from class_schedule.webapp import _serialize_schedule
        item = LectureLabClass(tuple(reversed(rows())))  # long, short, lecture
        payload, = _serialize_schedule(Schedule([item]))
        self.assertEqual(payload["scheduling_records"], [0, 2])
        self.assertEqual(payload["editable_fields"], [
            ["instructor", "section"], ["instructor", "section"], ["instructor", "room", "section", "time"],
        ])
        self.assertTrue(payload["linked_fields"]["instructor"])

    def test_web_edit_api_locks_the_lab_only(self):
        import pandas as pd
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        from class_schedule import webapp

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = pd.DataFrame([s.to_record() for s in rows()]).to_csv(index=False).encode()
            with patch.object(webapp, "CONFIG_DIR", root / "config"), patch.object(webapp, "WORK_ROOT", root / "work"):
                client = TestClient(webapp.create_app())
                response = client.post("/api/configuration-packages", data={"current_package": "TEST"},
                    files={"config_files": ("lecture-lab.csv", source, "text/csv")})
                self.assertEqual(response.status_code, 200, response.text)
                cfg = SolverConfig.load(root / "config", package="TEST")
                current = read_schedule(root / "work/TEST/initial/initial.csv",
                                        relationships=cfg.courses.active_relationships)
                self.assertIsInstance(current.classes[0], LectureLabClass)
                records = _serialize_schedule(current)[0]["sections"]

                def request(field, value, record_index):
                    target = records[record_index]
                    return client.post("/api/edit", json={
                        "package": "TEST", "records": records, "class_index": 0, "record_index": record_index,
                        "expected_course_ids": ["CHEM 3245-1"],
                        "expected_record": {"subject": "CHEM", "number": "3245", "section": "1",
                            "expected_time_slot": target["Time Slot"]},
                        "field": field, "value": value,
                    })

                self.assertEqual(request("instructor", "Bob", 1).status_code, 200)
                self.assertEqual(request("room", {"building": "Science", "room": "99"}, 2).status_code, 400)
                self.assertEqual(request("time", {"days": "M", "start": "16:00"}, 2).status_code, 400)
                self.assertEqual(request("room", {"building": "Science", "room": "99"}, 0).status_code, 200)
                response = request("time", {"days": "MWF", "start": "10:00"}, 0)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["classes"][0]["sections"][0]["Duration"], 50)


class DragDurationTests(unittest.TestCase):
    """`_resolve_meeting_duration` -- a drag only changes a meeting's
    length when the day pattern forces it (docs/codes.md)."""

    def _config(self):
        return SolverConfig(persons={}, preferences={}, rooms=[], meeting_patterns=[
            MeetingPattern("T", 50, (datetime.time(14),), frozenset({"normal"})),
            MeetingPattern("W", 50, (datetime.time(14),), frozenset({"normal"})),
            MeetingPattern("MWF", 50, (datetime.time(9),), frozenset({"normal"})),
            MeetingPattern("TR", 80, (datetime.time(9),), frozenset({"normal"})),
        ])

    def _lab(self):
        # An unlinked 170-minute lab with no calendar pattern of its own.
        return NormalClass((Section(
            subject="CHEM", number="3340", section="1", instructor="Am",
            type="LAB", time_slot="T 2:00pm", duration=170, room="", building="",
        ),))

    def test_same_day_nudge_keeps_the_length(self):
        from class_schedule.webapp import _resolve_meeting_duration
        self.assertEqual(
            _resolve_meeting_duration(self._lab(), 0, "T", self._config()), 170,
        )

    def test_cross_day_drag_of_a_pattern_exempt_meeting_keeps_the_length(self):
        from class_schedule.webapp import _resolve_meeting_duration
        # "W" only offers 50 minutes, but 170 was never pattern-pinned.
        self.assertEqual(
            _resolve_meeting_duration(self._lab(), 0, "W", self._config()), 170,
        )

    def test_day_pattern_change_still_snaps_a_day_dependent_meeting(self):
        from class_schedule.webapp import _resolve_meeting_duration
        lecture = NormalClass((Section(
            subject="MATH", number="1113", section="1", instructor="Am",
            type="CLAS", time_slot="MWF 9:00am", duration=50, room="1", building="B",
        ),))
        self.assertEqual(
            _resolve_meeting_duration(lecture, 0, "TR", self._config()), 80,
        )


class LectureLabConfigTests(unittest.TestCase):
    def test_inference_emits_one_member_for_a_shared_number(self):
        schedule = Schedule([LectureLabClass(rows())])
        from class_schedule.config_inference import infer_relationships_from_template
        relations = infer_relationships_from_template(schedule)
        lecture_lab = [r for r in relations if r.kind == "lecture_lab"]
        self.assertEqual([r.members for r in lecture_lab], [["CHEM 3245 1"]])

    def test_inference_emits_two_members_for_catalog_siblings(self):
        schedule = Schedule.from_records([s.to_record() for s in sibling_rows()])
        from class_schedule.config_inference import infer_relationships_from_template
        relations = infer_relationships_from_template(schedule)
        lecture_lab = [r for r in relations if r.kind == "lecture_lab"]
        self.assertEqual([r.members for r in lecture_lab], [["CHEM 3264 1", "CHEM 3260 1"]])

    def test_real_workbook_inference_loads_and_reconciles(self):
        from class_schedule.reconciliation import reconcile_records
        source = Path(__file__).parents[1] / "config/27/template/202720 maps.xlsx"
        if not source.is_file():
            self.skipTest("Local user workbook is not part of the test fixtures")
        original = read_schedule(source)
        # 3 shared-number bundles (3245, 3334, 4424) + 5 catalog-sibling
        # pairs (1111/1113 x2, 2130/2134, 3260/3264 x2); 3260-3 is a lone lab.
        self.assertEqual(sum(isinstance(c, LectureLabClass) for c in original), 8)
        self.assertEqual(sum(isinstance(c, LabClass) for c in original), 1)


if __name__ == "__main__":
    unittest.main()
