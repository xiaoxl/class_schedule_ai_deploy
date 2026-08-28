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
from class_schedule.solver.config import load_meeting_patterns


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
    def test_meeting_pattern_days_requires_an_array(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "timeslot.toml"
            path.write_text(
                "[[calendar.meeting_patterns]]\n"
                'days = "MWF"\n'
                "duration_minutes = 50\n"
                'starts = ["09:00"]\n'
                'roles = ["normal"]\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValidationError):
                load_meeting_patterns(path)

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
            meeting_patterns=[MeetingPattern(
                "MWF", 50, (__import__("datetime").time(9),),
                frozenset({"normal", "cross_listing"}),
            )],
            rooms=[RoomRecord("Corley", "101")],
            version="test-config",
        )

    def test_online_staff_can_receive_a_qualified_instructor(self):
        section = Section("MATH", "1113", "001", "ONLINE", None, "", "Staff")
        solved = solve(Schedule([NormalClass((section,))]), self._config())
        self.assertEqual(solved.classes[0].sections[0].instructor, "Alice")
        self.assertEqual(solved.classes[0].sections[0].time_slot, "ONLINE")

    def test_cross_listing_rows_are_never_forced_to_converge(self):
        """Cross-listing rows are never required to match (see
        docs/codes.md): a pair whose source template already had them in
        different rooms/times is free to stay that way -- the solver has
        no pairwise rule pulling them back together."""
        from class_schedule.schedule_model import PersonRecord

        left = Section(
            "MATH", "1113", "001", "MWF 8:00am", 50, "102", "Alice",
            building="Corley", cross_list="XL1",
        )
        right = Section(
            "STAT", "2163", "001", "TR 10:00am", 80, "103", "Alice",
            building="Corley", cross_list="XL1",
        )
        config = SolverConfig(
            persons={"Alice": PersonRecord("Alice", 6, ("MATH 1113", "STAT 2163"))},
            preferences={},
            meeting_patterns=[
                MeetingPattern(
                    "MWF", 50, (__import__("datetime").time(8),),
                    frozenset({"normal", "cross_listing"}),
                ),
                MeetingPattern(
                    "TR", 80, (__import__("datetime").time(10),),
                    frozenset({"normal", "cross_listing"}),
                ),
            ],
            rooms=[RoomRecord("Corley", "102"), RoomRecord("Corley", "103")],
            version="test-config",
        )
        solved = solve(Schedule([CrossListingClass((left, right))]), config)
        a, b = solved.classes[0].sections
        self.assertFalse(CrossListingClass.is_shared_meeting(a, b))

    def test_declared_cross_listing_without_synced_fields_actually_converges_when_solved(self):
        """The inverse of the test above, for the *declared*-relationship
        path (see docs/codes.md's opt-in addendum): a courses.toml
        cross_listing relationship that doesn't name synced_fields at all
        defaults to fully locked, and that has to actually be enforced by
        the solver, not just recorded on the instance -- both rows start
        in different rooms/patterns (so the solver has real freedom not
        to converge them), and pairwise_predicate must still force them
        together.
        """
        from class_schedule.schedule_model import PersonRecord

        # Same subject/number/duration family for both rows (only section
        # differs) so a shared meeting is actually reachable -- room and
        # start time still have two real options each, so a solve that
        # converges them is choosing to, not forced by having nowhere else
        # to go.
        left = Section(
            "MATH", "1113", "001", "MWF 8:00am", 50, "102", "Alice",
            building="Corley", cross_list="XL1",
        )
        right = Section(
            "MATH", "1113", "002", "MWF 9:00am", 50, "103", "Alice",
            building="Corley", cross_list="XL1",
        )
        config = SolverConfig(
            persons={"Alice": PersonRecord("Alice", 6, ("MATH 1113",))},
            preferences={},
            meeting_patterns=[
                MeetingPattern(
                    "MWF", 50,
                    (__import__("datetime").time(8), __import__("datetime").time(9)),
                    frozenset({"normal", "cross_listing"}),
                ),
            ],
            rooms=[RoomRecord("Corley", "102"), RoomRecord("Corley", "103")],
            version="test-config",
        )
        item = CrossListingClass.from_configured_sections((left, right))
        self.assertEqual(item.synced_fields, CrossListingClass.ALL_SYNCED_FIELDS)
        solved = solve(Schedule([item]), config)
        a, b = solved.classes[0].sections
        self.assertTrue(CrossListingClass.is_shared_meeting(a, b))

    def test_detailed_result_reports_solver_metadata(self):
        section = Section("MATH", "1113", "001", "MWF 9:00am", 50, "101", "Alice", building="Corley")
        result = solve_detailed(Schedule([NormalClass((section,))]), self._config())
        self.assertIn(result.status, (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE))
        self.assertGreater(result.candidate_count, 0)
        self.assertEqual(result.config_version, "test-config")
        self.assertEqual(result.search_workers, 8)

    def test_solver_rejects_nonpositive_worker_count(self):
        section = Section(
            "MATH", "1113", "001", "MWF 9:00am", 50, "101", "Alice",
            building="Corley",
        )
        with self.assertRaisesRegex(ValueError, "search_workers"):
            solve_detailed(
                Schedule([NormalClass((section,))]), self._config(),
                search_workers=0,
            )


if __name__ == "__main__":
    unittest.main()
