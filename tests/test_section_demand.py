import tempfile
import unittest
from pathlib import Path

import pandas as pd

from class_schedule.section_demand import (
    analyze,
    load_headcounts,
    load_schedule_rows,
    parse_seats_avail,
    to_markdown,
)


def write_cube(path: Path, rows: list[tuple[str, int, int]]) -> None:
    """Build a Cube1-shaped export: title row, header row, "Value"
    sub-header row, data rows, trailing "Total by COLUMNS" row -- same
    shape as the real export, not just a plain three-column table."""
    body = [
        [None, "Total by ROWS", None],
        ["CRN", "Course Start Date Headcount", "Final Headcount"],
        [None, "Value", "Value"],
        *[[crn, start, final] for crn, start, final in rows],
        ["Total by COLUMNS", sum(r[1] for r in rows), sum(r[2] for r in rows)],
    ]
    pd.DataFrame(body).to_excel(path, header=False, index=False)


def write_schedule(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def _row(
    subject, number, section, crn, seats_avail,
    instructor="Alice", time_slot="MWF 9:00am", duration=50, room="101",
):
    return {
        "Subject": subject, "Number": number, "Section": section,
        "CRN": crn, "Seats_Avail": seats_avail, "Instructor": instructor,
        "Time Slot": time_slot, "Duration": duration, "Room": room,
        "Building": "Corley",
    }


class ParseSeatsAvailTests(unittest.TestCase):
    def test_parses_three_numbers(self):
        result = parse_seats_avail("5 / 32 / 36")
        self.assertEqual(result.seats_available, 5.0)
        self.assertEqual(result.max_enrolled, 32.0)
        self.assertEqual(result.room_capacity, 36.0)

    def test_negative_seats_available_parses_fine(self):
        result = parse_seats_avail("-21 / 0 / 36")
        self.assertEqual(result.seats_available, -21.0)
        self.assertEqual(result.room_capacity, 36.0)

    def test_na_room_capacity_is_none(self):
        result = parse_seats_avail("-13 / 0 / na")
        self.assertIsNone(result.room_capacity)

    def test_blank_cell_is_all_none(self):
        result = parse_seats_avail("")
        self.assertEqual(result, parse_seats_avail(None))
        self.assertIsNone(result.room_capacity)

    def test_malformed_shape_is_all_none(self):
        result = parse_seats_avail("just one number")
        self.assertIsNone(result.room_capacity)


class LoadHeadcountsTests(unittest.TestCase):
    def test_parses_data_rows_and_stops_at_the_total_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cube.xlsx"
            write_cube(path, [("20450", 26, 21), ("20470", 12, 10)])
            headcounts = load_headcounts(path)
        self.assertEqual(headcounts, {"20450": (26.0, 21.0), "20470": (12.0, 10.0)})

    def test_missing_header_row_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cube.xlsx"
            pd.DataFrame([[1, 2, 3]]).to_excel(path, header=False, index=False)
            with self.assertRaises(ValueError):
                load_headcounts(path)


class LoadScheduleRowsTests(unittest.TestCase):
    def test_missing_required_column_raises_with_a_clear_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sched.csv"
            pd.DataFrame([{"Subject": "MATH"}]).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "Number"):
                load_schedule_rows(path)

    def test_number_column_keeps_leading_zeros(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sched.csv"
            write_schedule(path, [_row("MATH", "0803", "001", "20450", "-21 / 0 / 36")])
            rows = load_schedule_rows(path)
        self.assertEqual(rows.iloc[0]["Number"], "0803")


class AnalyzeTests(unittest.TestCase):
    def _run(self, schedule_rows, cube_rows):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            schedule_path = tmp_path / "sched.csv"
            cube_path = tmp_path / "cube.xlsx"
            write_schedule(schedule_path, schedule_rows)
            write_cube(cube_path, cube_rows)
            return {d.course: d for d in analyze(schedule_path, cube_path)}

    def test_concurrent_enrollment_sections_are_excluded(self):
        results = self._run(
            [
                _row("MATH", "1003", "001", "20001", "5 / 30 / 36"),
                _row("MATH", "1003", "P01", "20002", "10 / 0 / na", time_slot="TBA", duration=None, room=""),
            ],
            [("20001", 20, 18), ("20002", 5, 5)],
        )
        self.assertEqual(results["MATH 1003"].total_enrollment, 20.0)
        self.assertEqual(results["MATH 1003"].section_count, 1)

    def test_normal_section_is_the_plain_course_bucket(self):
        results = self._run(
            [_row("MATH", "1113", "001", "20003", "0 / 0 / 36")],
            [("20003", 30, 28)],
        )
        self.assertIn("MATH 1113", results)
        self.assertEqual(results["MATH 1113"].section_count, 1)

    def test_hybrid_pair_sharing_one_crn_gets_its_own_bucket(self):
        results = self._run(
            [
                _row("MATH", "1113", "F01", "20004", "12 / 30 / na", time_slot="TBA", duration=None, room=""),
                _row("MATH", "1113", "F01", "20004", "12 / 30 / 36"),
            ],
            [("20004", 12, 12)],
        )
        self.assertIn("MATH 1113 (Hybrid)", results)
        self.assertNotIn("MATH 1113", results)
        demand = results["MATH 1113 (Hybrid)"]
        self.assertEqual(demand.section_count, 1)
        self.assertEqual(demand.total_enrollment, 12.0)
        self.assertEqual(demand.total_capacity, 36.0)

    def test_coreq_pair_is_pooled_as_one_bucket_not_two(self):
        results = self._run(
            [
                _row("MATH", "0803", "TC1", "20005", "-13 / 0 / na", time_slot="TBA", duration=None, room=""),
                _row("MATH", "1003", "TC1", "20006", "-13 / 0 / na", time_slot="TBA", duration=None, room=""),
            ],
            [("20005", 22, 13), ("20006", 22, 13)],
        )
        self.assertIn("MATH 0803 / MATH 1003", results)
        self.assertNotIn("MATH 0803", results)
        self.assertNotIn("MATH 1003", results)
        demand = results["MATH 0803 / MATH 1003"]
        self.assertEqual(demand.section_count, 1)
        # Only the first course's own CRN is used -- not summed with the
        # second course's CRN, which would double the same group of students.
        self.assertEqual(demand.total_enrollment, 22.0)

    def test_honors_pair_folds_into_the_plain_course_bucket(self):
        results = self._run(
            [
                _row("MATH", "3203", "001", "20007", "5 / 25 / 30"),
                _row("MATH", "3203", "H01", "20007", "5 / 25 / 30"),
            ],
            [("20007", 25, 24)],
        )
        self.assertIn("MATH 3203", results)
        self.assertNotIn("MATH 3203 (Hybrid)", results)

    def test_online_section_uses_the_default_capacity(self):
        results = self._run(
            [_row("MATH", "1203", "TC1", "20008", "-5 / 0 / na", time_slot="TBA", duration=None, room="")],
            [("20008", 5, 4)],
        )
        demand = results["MATH 1203"]
        self.assertEqual(demand.in_person_section_count, 0)
        self.assertEqual(demand.online_section_count, 1)
        self.assertEqual(demand.avg_capacity_per_section, 30.0)

    def test_missing_headcount_crn_is_excluded_but_tracked(self):
        results = self._run(
            [_row("MATH", "2914", "003", "20009", "0 / 0 / 36")],
            [],  # no cube row for this CRN at all
        )
        demand = results["MATH 2914"]
        self.assertEqual(demand.total_enrollment, 0.0)
        self.assertEqual(demand.missing_headcount_crns, ("20009",))
        self.assertEqual(demand.section_enrollments, (None,))

    def test_needs_new_section_boundary(self):
        # 2 sections, capacity 36 each (avg 36). Projected enrollment
        # spread over 3 sections must exceed 18 to flag.
        just_under = self._run(
            [
                _row("MATH", "1113", "001", "30001", "0 / 0 / 36"),
                _row("MATH", "1113", "002", "30002", "0 / 0 / 36"),
            ],
            [("30001", 27, 27), ("30002", 26, 26)],  # total 53 -> 53/3 = 17.67 < 18
        )
        self.assertFalse(just_under["MATH 1113"].needs_new_section)

        just_over = self._run(
            [
                _row("MATH", "1113", "001", "30003", "0 / 0 / 36"),
                _row("MATH", "1113", "002", "30004", "0 / 0 / 36"),
            ],
            [("30003", 28, 28), ("30004", 27, 27)],  # total 55 -> 55/3 = 18.33 > 18
        )
        self.assertTrue(just_over["MATH 1113"].needs_new_section)


class ToMarkdownTests(unittest.TestCase):
    def test_renders_a_row_per_course_with_a_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            schedule_path = tmp_path / "sched.csv"
            cube_path = tmp_path / "cube.xlsx"
            write_schedule(schedule_path, [
                _row("MATH", "1113", "001", "40001", "0 / 0 / 36"),
            ])
            write_cube(cube_path, [("40001", 30, 28)])
            results = analyze(schedule_path, cube_path)
        markdown = to_markdown(results)
        self.assertIn("| Course | Sections |", markdown)
        self.assertIn("MATH 1113", markdown)
        self.assertIn("30", markdown)


if __name__ == "__main__":
    unittest.main()
