import tempfile
import unittest
from pathlib import Path

import pandas as pd

from class_schedule.schedule_run import next_version, run_term


class VersionTests(unittest.TestCase):
    def test_next_version_ignores_unrelated_entries(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "ver1").mkdir()
            (root / "ver4").mkdir()
            (root / "version9").mkdir()
            self.assertEqual(next_version(root), "ver5")


class RunTermTests(unittest.TestCase):
    def test_writes_atomic_csv_report_and_attempt_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = root / "starting.csv"
            pd.DataFrame([{
                "Subject": "MATH",
                "Number": "1113",
                "Section": "001",
                "Instructor": "Bain",
                "Time Slot": "MWF 9:00am",
                "Duration": 50,
                "Room": "101",
                "Building": "Corley",
            }]).to_csv(input_path, index=False)

            bundle = run_term(
                "TEST",
                input_path=input_path,
                output_root=root / "out",
                config_dir="config",
                attempts=1,
                time_limit_seconds=5,
            )

            self.assertEqual(bundle.version, "ver1")
            self.assertTrue(bundle.schedule_path.exists())
            self.assertTrue(bundle.report_path.exists())
            self.assertTrue(bundle.attempts_path.exists())
            report = bundle.report_path.read_text(encoding="utf-8")
            self.assertIn("Configuration version", report)
            self.assertIn("## Attempt comparison", report)
            self.assertIn("## Remaining soft findings", report)
            written = pd.read_csv(bundle.schedule_path, dtype=str)
            self.assertNotEqual(written.loc[0, "Instructor"], "Bain")

    def test_refuses_to_overwrite_an_existing_version(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            destination = root / "out" / "TEST" / "ver2"
            destination.mkdir(parents=True)
            with self.assertRaises(FileExistsError):
                run_term(
                    "TEST",
                    input_path=root / "missing.csv",
                    output_root=root / "out",
                    version="ver2",
                    attempts=1,
                )


if __name__ == "__main__":
    unittest.main()
