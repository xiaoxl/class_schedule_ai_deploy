import unittest

from class_schedule import record_utils


class TextEmptyValuesTests(unittest.TestCase):
    def test_unassigned_is_treated_as_empty(self):
        # ATU's "Course Schedule Report" export uses "Unassigned" as its
        # own placeholder for "no room/building" -- see the comment above
        # record_utils._EMPTY_VALUES.
        self.assertEqual(record_utils.text("Unassigned"), "")
        self.assertEqual(record_utils.text("unassigned"), "")

    def test_real_room_value_is_kept(self):
        self.assertEqual(record_utils.text("269"), "269")


class SplitTimeRangeTests(unittest.TestCase):
    def test_splits_a_valid_range(self):
        self.assertEqual(
            record_utils.split_time_range("09:30 am-10:50 am"),
            ("09:30 am", "10:50 am"),
        )

    def test_tba_returns_blank_pair(self):
        self.assertEqual(record_utils.split_time_range("TBA"), ("", ""))

    def test_blank_returns_blank_pair(self):
        self.assertEqual(record_utils.split_time_range(""), ("", ""))


class NormalizeColumnsMeetingReportTests(unittest.TestCase):
    def test_meeting_underscore_days_renamed_to_days(self):
        result = record_utils.normalize_columns({"Meeting_Days": "TR"})
        self.assertEqual(result["Days"], "TR")

    def test_meeting_times_split_into_start_and_end(self):
        result = record_utils.normalize_columns(
            {"Meeting_Times": "09:30 am-10:50 am"}
        )
        self.assertEqual(result["Start"], "09:30 am")
        self.assertEqual(result["End"], "10:50 am")
        self.assertNotIn("Meeting_Times", result)

    def test_tba_meeting_times_becomes_blank_start_and_end(self):
        result = record_utils.normalize_columns({"Meeting_Times": "TBA"})
        self.assertEqual(result["Start"], "")
        self.assertEqual(result["End"], "")

    def test_existing_start_column_is_not_overridden(self):
        result = record_utils.normalize_columns(
            {"Start": "08:00 am", "Meeting_Times": "09:30 am-10:50 am"}
        )
        self.assertEqual(result["Start"], "08:00 am")

    def test_existing_time_slot_column_is_not_overridden(self):
        result = record_utils.normalize_columns(
            {"Time Slot": "MWF 8:00am", "Meeting_Times": "09:30 am-10:50 am"}
        )
        self.assertNotIn("Start", result)
        self.assertEqual(result["Time Slot"], "MWF 8:00am")


if __name__ == "__main__":
    unittest.main()
