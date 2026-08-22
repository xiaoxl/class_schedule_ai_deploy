import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from class_schedule.class_model import (
    CrossListingClass,
    DeliveryMode,
    NormalClass,
    Section,
)
from class_schedule.schedule_model import load_persons, resolve_person_name, Schedule
from class_schedule.solver import (
    MeetingPattern,
    RoomRecord,
    SolveStatus,
    SolverConfig,
    solve,
    solve_detailed,
)


class DomainSemanticsTests(unittest.TestCase):
    def test_delivery_mode_distinguishes_online_from_tba(self):
        online = Section("MATH", "1113", "001", "ONLINE", None, "", "Staff")
        tba = Section("MATH", "1113", "002", "TBA", None, "", "Staff")
        self.assertEqual(online.delivery_mode, DeliveryMode.ONLINE)
        self.assertEqual(tba.delivery_mode, DeliveryMode.ARRANGED)

    def test_explicit_credits_override_course_number_convention(self):
        section = Section(
            "MATH", "9999", "001", "MWF 9:00am", 50, "101", "Alice",
            credits=2.5,
        )
        self.assertEqual(NormalClass((section,)).credit_hours, 2.5)


class StrictConfigurationTests(unittest.TestCase):
    def test_aliases_are_loaded_and_subject_scoped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "persons.toml"
            path.write_text(
                '[[persons]]\nname="Jordan, Scott"\nmax_load=12\n'
                'aliases=[{short="Jordan", subject="STAT"}]\n'
                'courses=["STAT 2163"]\n',
                encoding="utf-8",
            )
            persons = load_persons(path)
        self.assertEqual(resolve_person_name("Jordan", persons, subject="STAT"), "Jordan, Scott")
        self.assertIsNone(resolve_person_name("Jordan", persons, subject="MATH"))

    def test_unknown_person_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "persons.toml"
            path.write_text(
                '[[persons]]\nname="Alice"\nmax_load=12\nunknown=true\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValidationError):
                load_persons(path)


class SolverArchitectureTests(unittest.TestCase):
    def test_solver_public_api_is_backed_by_the_split_package(self):
        import class_schedule.solver as solver_package

        self.assertEqual(Path(solver_package.__file__).name, "__init__.py")
        self.assertEqual(SolverConfig.__module__, "class_schedule.solver.config")
        self.assertEqual(solve_detailed.__module__, "class_schedule.solver.engine")

    def _config(self, courses=("MATH 1113",)):
        from class_schedule.schedule_model import PersonRecord

        return SolverConfig(
            persons={"Alice": PersonRecord("Alice", 3, courses)},
            preferences={},
            meeting_patterns=[MeetingPattern("MWF", 50, (__import__("datetime").time(9),), frozenset({"standard"}))],
            rooms=[RoomRecord("Corley", "101")],
            blackouts=[],
            version="test-config",
        )

    def test_online_staff_can_receive_a_qualified_instructor(self):
        section = Section("MATH", "1113", "001", "ONLINE", None, "", "Staff")
        solved = solve(Schedule([NormalClass((section,))]), self._config())
        self.assertEqual(solved.classes[0].sections[0].instructor, "Alice")
        self.assertEqual(solved.classes[0].sections[0].time_slot, "ONLINE")

    def test_explicit_cross_listing_is_one_shared_meeting_after_solve(self):
        left = Section(
            "MATH", "1113", "001", "MWF 8:00am", 50, "102", "Alice",
            building="Corley", cross_list="XL1",
        )
        right = Section(
            "STAT", "2163", "001", "MWF 10:00am", 50, "103", "Alice",
            building="Corley", cross_list="XL1",
        )
        config = self._config(("MATH 1113", "STAT 2163"))
        solved = solve(Schedule([CrossListingClass((left, right))]), config)
        a, b = solved.classes[0].sections
        self.assertTrue(CrossListingClass.is_shared_meeting(a, b))

    def test_detailed_result_reports_solver_metadata(self):
        section = Section("MATH", "1113", "001", "MWF 9:00am", 50, "101", "Alice", building="Corley")
        result = solve_detailed(Schedule([NormalClass((section,))]), self._config())
        self.assertIn(result.status, (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE))
        self.assertGreater(result.candidate_count, 0)
        self.assertEqual(result.config_version, "test-config")


if __name__ == "__main__":
    unittest.main()
