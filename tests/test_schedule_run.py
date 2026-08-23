import tempfile
import unittest
import json
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from class_schedule.schedule_run import (
    create_override_template,
    infer_parent_version,
    install_version_override_template,
    latest_version,
    next_version,
    publish_final,
    run_term,
    version_schedule_path,
)
from class_schedule.schedule_io import read_schedule


class VersionTests(unittest.TestCase):
    def test_next_version_ignores_unrelated_entries(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "ver1").mkdir()
            (root / "ver4").mkdir()
            (root / "version9").mkdir()
            (root / "ver4_validation").mkdir()
            (root / "final").mkdir()
            self.assertEqual(latest_version(root), "ver4")
            self.assertEqual(next_version(root), "ver5")

    def test_infers_parent_only_from_an_exact_version_directory(self):
        root = Path("out") / "27S"
        self.assertEqual(
            infer_parent_version(root / "ver7" / "27S_ver7.csv", root), "ver7"
        )
        self.assertIsNone(
            infer_parent_version(root / "ver7_archive" / "27S_ver7.csv", root)
        )

    def test_resolves_only_a_canonical_published_schedule(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "27S" / "ver3" / "27S_ver3.csv"
            path.parent.mkdir(parents=True)
            path.write_text("Subject,Number,Section\n", encoding="utf-8")
            self.assertEqual(
                version_schedule_path("27S", "ver3", output_root=root), path
            )
            with self.assertRaises(ValueError):
                version_schedule_path("27S", "3", output_root=root)


class RunTermTests(unittest.TestCase):
    @staticmethod
    def _write_source(
        path: Path,
        *,
        time_slot: str = "MWF 9:00am",
        room: str = "101",
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{
            "Subject": "MATH",
            "Number": "1113",
            "Section": "001",
            "Instructor": "Bain, Leslie M.",
            "Time Slot": time_slot,
            "Duration": 50,
            "Room": room,
            "Building": "Corley",
        }]).to_csv(path, index=False)

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
            self.assertTrue(bundle.instructor_path.exists())
            self.assertTrue(bundle.room_path.exists())
            self.assertTrue(bundle.report_path.exists())
            self.assertTrue(bundle.attempts_path.exists())
            self.assertTrue(bundle.changes_path.exists())
            self.assertTrue(bundle.baseline_path.exists())
            self.assertTrue(bundle.manifest_path.exists())
            self.assertTrue(bundle.overrides_path.exists())
            self.assertTrue(bundle.applied_overrides_path.exists())
            manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 3)
            self.assertEqual(manifest["change_baseline"]["path"], str(input_path))
            self.assertEqual(manifest["change_baseline"]["snapshot"], "baseline.csv")
            self.assertIn("baseline.csv", manifest["files"])
            self.assertIn("TEST_ver1_instructor.xlsx", manifest["files"])
            self.assertIn("TEST_ver1_room.xlsx", manifest["files"])
            self.assertIn("applied_overrides.toml", manifest["files"])
            self.assertNotIn("overrides.toml", manifest["files"])
            self.assertTrue(manifest["override_workspace"]["mutable"])
            self.assertIn("source_version = \"ver1\"", bundle.overrides_path.read_text())
            written = pd.read_csv(bundle.schedule_path, dtype=str)
            instructor = written.loc[0, "Instructor"]
            room = f'{written.loc[0, "Building"]} {written.loc[0, "Room"]}'
            workbook = load_workbook(bundle.instructor_path, read_only=True)
            try:
                self.assertIn(instructor, workbook.sheetnames)
            finally:
                workbook.close()
            workbook = load_workbook(bundle.room_path, read_only=True)
            try:
                self.assertIn(room, workbook.sheetnames)
            finally:
                workbook.close()
            report = bundle.report_path.read_text(encoding="utf-8")
            self.assertIn("Configuration version", report)
            self.assertIn("## Attempt comparison", report)
            self.assertIn("## Remaining soft findings", report)
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

    def test_generates_a_parseable_template_bound_to_the_source_version(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "out" / "TEST" / "ver3" / "TEST_ver3.csv"
            self._write_source(source)
            destination = root / "revision.toml"
            written = create_override_template(
                "TEST", "ver3", output_path=destination,
                output_root=root / "out", config_dir="config",
            )
            text = written.read_text(encoding="utf-8")
            self.assertIn('term = "TEST"', text)
            self.assertIn('source_version = "ver3"', text)
            self.assertIn("MATH 1113-001 | record=0", text)

    def test_embedded_override_refreshes_final_without_creating_a_version(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output_root = root / "out"
            source = output_root / "TEST" / "ver3" / "TEST_ver3.csv"
            self._write_source(source, time_slot="MWF 10:00am")
            self._write_source(output_root / "TEST" / "starting.csv")
            self._write_source(source.parent / "baseline.csv")
            overrides = source.parent / "overrides.toml"
            overrides.write_text(
                'term = "TEST"\nsource_version = "ver3"\n\n'
                '[[edits]]\ncourse_id = "MATH 1113-001"\n'
                'instructor = "Bain, Leslie M."\n'
                'time_slot = "MWF 9:00am"\nroom = "102"\nbuilding = "Corley"\n\n'
                '[[locks]]\ncourse_id = "MATH 1113-001"\n'
                'fields = ["instructor", "time", "room", "building"]\n',
                encoding="utf-8",
            )

            bundle = publish_final(
                "TEST", "ver3",
                output_root=output_root, config_dir="config",
                attempts=1, time_limit_seconds=5,
            )

            self.assertEqual(bundle.version, "final")
            revised = read_schedule(bundle.schedule_path)
            self.assertEqual(
                revised.get("MATH 1113-001").sections[0].time_slot,
                "MWF 9:00am",
            )
            self.assertEqual(
                revised.get("MATH 1113-001").sections[0].room, "102"
            )
            cumulative = pd.read_csv(bundle.changes_path, dtype=str)
            self.assertNotIn("time", set(cumulative["Field"]))
            self.assertEqual(list(cumulative["Field"]), ["room"])
            manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["parent"], "ver3")
            self.assertEqual(manifest["input"]["path"], str(source))
            self.assertFalse(manifest["override_workspace"]["mutable"])
            self.assertIn("overrides.toml", manifest["files"])
            self.assertIn("applied_overrides.toml", manifest["files"])
            self.assertEqual(bundle.schedule_path.name, "TEST_final.csv")

            overrides.write_text(
                overrides.read_text(encoding="utf-8").replace(
                    'room = "102"', 'room = "103"'
                ),
                encoding="utf-8",
            )
            refreshed = publish_final(
                "TEST", "ver3",
                output_root=output_root, config_dir="config",
                attempts=1, time_limit_seconds=5,
            )
            schedule = read_schedule(refreshed.schedule_path)
            self.assertEqual(
                schedule.get("MATH 1113-001").sections[0].room,
                "103",
            )
            self.assertFalse((output_root / "TEST" / "ver4").exists())

    def test_final_rejects_an_untouched_override_template(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output_root = root / "out"
            source = output_root / "TEST" / "ver3" / "TEST_ver3.csv"
            self._write_source(source)
            (source.parent / "overrides.toml").write_text(
                'term = "TEST"\nsource_version = "ver3"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "No manual edits or locks"):
                publish_final(
                    "TEST", "ver3", output_root=output_root,
                    config_dir="config", attempts=1, time_limit_seconds=5,
                )
            self.assertFalse((output_root / "TEST" / "final").exists())

    def test_installs_an_embedded_workspace_and_preserves_the_old_override(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "out" / "TEST" / "ver3" / "TEST_ver3.csv"
            self._write_source(source)
            old = source.parent / "overrides.toml"
            old.write_text("# old applied input\n", encoding="utf-8")
            workspace = install_version_override_template(
                "TEST", "ver3", output_root=root / "out", config_dir="config"
            )
            self.assertIn('source_version = "ver3"', workspace.read_text())
            self.assertEqual(
                (source.parent / "applied_overrides.toml").read_text(),
                "# old applied input\n",
            )


if __name__ == "__main__":
    unittest.main()
