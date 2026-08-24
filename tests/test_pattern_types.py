import datetime
import tempfile
import unittest
from pathlib import Path

from class_schedule.class_model import (
    CoreqClass,
    CrossListingClass,
    FourCreditClass,
    HybridClass,
    NormalClass,
    Section,
)
from class_schedule.pattern_rules import pattern_applies, section_pattern_role
from class_schedule.solver import MeetingPattern
from class_schedule.solver.config import load_meeting_patterns


ROOT = Path(__file__).resolve().parents[1]


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


class StructuralRoleTests(unittest.TestCase):
    def test_roles_depend_on_atomic_structure_not_course_number(self):
        normal = make_section()
        self.assertEqual(section_pattern_role(NormalClass((normal,)), normal), "normal")

        hybrid_physical = make_section(section="M01")
        hybrid_online = make_section(
            section="M01", time_slot="TBA", duration=None, room=""
        )
        hybrid = HybridClass((hybrid_physical, hybrid_online))
        self.assertEqual(
            section_pattern_role(hybrid, hybrid_physical), "hybrid_physical"
        )

        regular = make_section(section="001")
        honors = make_section(section="H01")
        cross_listing = CrossListingClass((regular, honors))
        self.assertEqual(
            section_pattern_role(cross_listing, regular), "cross_listing"
        )

        mwf = make_section(time_slot="MWF 9:00am", duration=50)
        t_half = make_section(time_slot="T 9:00am", duration=80)
        four_credit = FourCreditClass((mwf, t_half))
        self.assertEqual(
            section_pattern_role(four_credit, mwf), "four_credit_primary"
        )
        self.assertEqual(
            section_pattern_role(four_credit, t_half), "four_credit_partial"
        )

    def test_coreq_role_uses_relative_record_credits(self):
        lecture = make_section(
            number="1113", time_slot="MWF 11:00am", credits=3
        )
        lab = make_section(
            number="1110", time_slot="MW 12:00pm", credits=2
        )
        item = CoreqClass((lecture, lab))
        self.assertEqual(section_pattern_role(item, lecture), "coreq")
        self.assertEqual(
            section_pattern_role(item, lab), "coreq_supplement"
        )


class ConfiguredSelectorTests(unittest.TestCase):
    def test_days_array_expands_options_but_preserves_compound_days(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timeslot.toml"
            path.write_text(
                "[[calendar.meeting_patterns]]\n"
                'days = ["M", "W", "MWF"]\n'
                "duration_minutes = 50\n"
                'starts = ["09:00"]\n'
                'roles = ["normal"]\n',
                encoding="utf-8",
            )
            patterns = load_meeting_patterns(path)

        self.assertEqual([pattern.days for pattern in patterns], ["M", "W", "MWF"])

    def test_course_and_atomic_course_selectors_target_one_coreq_row(self):
        lecture = make_section(number="1113", time_slot="MWF 11:00am")
        lab = make_section(number="1110", time_slot="MW 12:00pm")
        item = CoreqClass((lecture, lab))
        pattern = MeetingPattern(
            "MW", 50, (datetime.time(12),),
            frozenset({"coreq_supplement"}),
            frozenset({"MATH 1110"}),
            frozenset({"MATH 1110", "MATH 1113"}),
        )
        self.assertFalse(pattern_applies(item, lecture, pattern))
        self.assertTrue(pattern_applies(item, lab, pattern))

    def test_same_selector_mechanism_supports_a_named_seminar(self):
        seminar = make_section(
            number="4971", time_slot="T 11:00am", duration=80
        )
        other = make_section(
            number="4972", time_slot="T 11:00am", duration=80
        )
        pattern = MeetingPattern(
            "T", 80, (datetime.time(11),),
            frozenset({"normal"}),
            frozenset({"MATH 4971"}),
        )
        self.assertTrue(
            pattern_applies(NormalClass((seminar,)), seminar, pattern)
        )
        self.assertFalse(pattern_applies(NormalClass((other,)), other, pattern))

    def test_production_config_gives_seminar_single_day_patterns(self):
        patterns = load_meeting_patterns(ROOT / "config" / "timeslot.toml")
        seminar_patterns = [
            pattern for pattern in patterns
            if "MATH 4971" in pattern.courses
        ]

        expected_starts = {
            "M": (8, 9, 10, 11, 12, 13, 14),
            "T": (8, 9.5, 11, 13, 14.5),
            "W": (8, 9, 10, 11, 12, 13, 14),
            "R": (8, 9.5, 11, 13, 14.5),
            "F": (8, 9, 10, 11, 12, 13, 14),
        }
        actual = {
            pattern.days: tuple(
                start.hour + start.minute / 60 for start in pattern.starts
            )
            for pattern in seminar_patterns
        }
        self.assertEqual(actual, expected_starts)
        durations = {
            pattern.days: pattern.duration_minutes
            for pattern in seminar_patterns
        }
        self.assertEqual(durations, {
            "M": 50, "T": 80, "W": 50, "R": 80, "F": 50,
        })
        self.assertTrue(all(
            pattern.roles == frozenset({"normal"})
            for pattern in seminar_patterns
        ))

    def test_production_config_grants_mw_noon_only_to_selected_atomic_row(self):
        patterns = load_meeting_patterns(ROOT / "config" / "timeslot.toml")
        noon = datetime.time(12)

        def can_use_mw_noon(item, section):
            return any(
                pattern.days == "MW"
                and pattern.duration_minutes == 50
                and noon in pattern.starts
                and pattern_applies(item, section, pattern)
                for pattern in patterns
            )

        cases = []
        for first_number, second_number in (
            ("1003", "0803"),
            ("1113", "0903"),
            ("1113", "1110"),
        ):
            first = make_section(number=first_number)
            second = make_section(
                number=second_number, time_slot="MWF 10:00am"
            )
            item = CoreqClass((first, second))
            cases.extend((
                (f"MATH {first_number}", item, first),
                (f"MATH {second_number}", item, second),
            ))

        actual = [
            (course, can_use_mw_noon(item, section))
            for course, item, section in cases
        ]
        self.assertEqual(actual, [
            ("MATH 1003", False),
            ("MATH 0803", False),
            ("MATH 1113", False),
            ("MATH 0903", False),
            ("MATH 1113", False),
            ("MATH 1110", True),
        ])


if __name__ == "__main__":
    unittest.main()
