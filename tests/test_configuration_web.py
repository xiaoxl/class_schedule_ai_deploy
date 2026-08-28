import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

from class_schedule import webapp
from class_schedule.reconciliation import reconcile_records
from class_schedule.schedule_model import evaluate_schedule
from class_schedule.schedule_run import _verified_initial
from class_schedule.solver import SolverConfig


class ConfigurationFileManagementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.config_root = Path(self.temporary.name) / "config"
        source = Path(__file__).parents[1] / "config" / "27S"
        shutil.copytree(source, self.config_root / "27S")
        shutil.rmtree(self.config_root / "27S" / "template", ignore_errors=True)
        self.config_patch = patch.object(webapp, "CONFIG_DIR", self.config_root)
        self.trash_patch = patch.object(
            webapp, "CONFIG_TRASH", Path(self.temporary.name) / "trash",
        )
        self.work_patch = patch.object(
            webapp, "WORK_ROOT", Path(self.temporary.name) / "work",
        )
        self.config_patch.start()
        self.trash_patch.start()
        self.work_patch.start()

    def tearDown(self):
        self.work_patch.stop()
        self.trash_patch.stop()
        self.config_patch.stop()
        self.temporary.cleanup()

    def test_lists_exactly_the_seven_editable_files(self):
        payload = webapp._configuration_file_payload("27S")

        self.assertEqual(
            {item["name"] for item in payload["files"]},
            set(webapp.CONFIG_FILES),
        )
        self.assertEqual(len(payload["files"]), 7)
        self.assertTrue(all(
            datetime.fromisoformat(item["updated_at"]).tzinfo is not None
            for item in payload["files"] if item["present"]
        ))

    def test_valid_replacement_is_saved_and_refreshes_version(self):
        before = webapp._configuration_file_payload("27S")
        original = next(
            item["content"] for item in before["files"]
            if item["name"] == "constraints.toml"
        )

        after = webapp._replace_configuration_file(
            "27S", "constraints.toml", (original + "\n# web edit\n").encode(),
        )

        self.assertNotEqual(after["config_version"], before["config_version"])
        self.assertTrue(
            (self.config_root / "27S" / "constraints.toml")
            .read_text(encoding="utf-8").endswith("# web edit\n")
        )

    def test_invalid_replacement_does_not_modify_current_file(self):
        target = self.config_root / "27S" / "constraints.toml"
        original = target.read_bytes()

        with self.assertRaises(HTTPException) as context:
            webapp._replace_configuration_file(
                "27S", "constraints.toml", b"this is not = valid toml [[[",
            )

        self.assertEqual(context.exception.status_code, 422)
        self.assertEqual(target.read_bytes(), original)

    def test_batch_replacement_restores_required_folder_structure(self):
        locations = self.config_root / "27S" / "basicinfo" / "locations.toml"
        preferences = self.config_root / "27S" / "preferences.toml"
        new_locations = locations.read_bytes() + b"\n# folder locations edit\n"
        new_preferences = preferences.read_bytes() + b"\n# folder preferences edit\n"

        webapp._replace_configuration_files("27S", {
            "locations.toml": new_locations,
            "preferences.toml": new_preferences,
        })

        self.assertEqual(locations.read_bytes(), new_locations)
        self.assertEqual(preferences.read_bytes(), new_preferences)

    def test_invalid_file_rolls_back_entire_batch_before_writing(self):
        locations = self.config_root / "27S" / "basicinfo" / "locations.toml"
        constraints = self.config_root / "27S" / "constraints.toml"
        original_locations = locations.read_bytes()
        original_constraints = constraints.read_bytes()

        with self.assertRaises(HTTPException):
            webapp._replace_configuration_files("27S", {
                "locations.toml": original_locations + b"\n# should not save\n",
                "constraints.toml": b"invalid = [[[",
            })

        self.assertEqual(locations.read_bytes(), original_locations)
        self.assertEqual(constraints.read_bytes(), original_constraints)

    def test_unknown_filename_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            webapp._replace_configuration_file(
                "27S", "../persons.toml", b"[[persons]]\n",
            )

        self.assertEqual(context.exception.status_code, 400)

    def _new_package_files(self, name: str) -> dict[str, bytes]:
        source = self.config_root / "27S"
        replacements = {}
        for filename, relative in webapp.CONFIG_FILES.items():
            content = (source / relative).read_text(encoding="utf-8")
            content = content.replace(
                "# Configuration package: 27S",
                f"# Configuration package: {name}",
                1,
            )
            replacements[filename] = content.encode("utf-8")
        return replacements

    def test_complete_folder_creates_package_named_by_header_comment(self):
        payload = webapp._upsert_configuration_package(
            self._new_package_files("27F"),
        )

        self.assertEqual(payload["package_id"], "27F")
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(
            (self.config_root / "27F" / "basicinfo" / "locations.toml").is_file()
        )
        self.assertTrue((self.config_root / "27F" / "constraints.toml").is_file())

    def test_partial_upload_creates_draft_package(self):
        replacements = self._new_package_files("27F")
        locations = replacements["locations.toml"]

        payload = webapp._upsert_configuration_package({
            "locations.toml": locations,
        })

        self.assertEqual(payload["status"], "draft")
        self.assertIn("courses.toml", payload["missing"])
        self.assertTrue(
            (self.config_root / "27F" / "basicinfo" / "locations.toml").is_file()
        )

    def test_later_upload_overwrites_an_existing_file(self):
        original = self._new_package_files("27F")["constraints.toml"]
        webapp._upsert_configuration_package({"constraints.toml": original})

        replacement = original + b"\n# later upload\n"
        webapp._upsert_configuration_package({"constraints.toml": replacement})

        self.assertEqual(
            (self.config_root / "27F" / "constraints.toml").read_bytes(),
            replacement,
        )

    def test_new_package_rejects_disagreeing_header_comments(self):
        replacements = self._new_package_files("27F")
        replacements["constraints.toml"] = replacements["constraints.toml"].replace(
            b"Configuration package: 27F", b"Configuration package: OTHER",
        )

        with self.assertRaises(HTTPException) as context:
            webapp._upsert_configuration_package(replacements)

        self.assertEqual(context.exception.status_code, 400)
        self.assertFalse((self.config_root / "27F").exists())

    def test_missing_term_file_can_be_generated_from_minimal_template(self):
        replacements = self._new_package_files("27F")
        replacements.pop("constraints.toml")
        webapp._upsert_configuration_package(replacements)

        payload = webapp._generate_configuration_template(
            "27F", "constraints.toml",
        )

        self.assertEqual(payload["status"], "ready")
        generated = (self.config_root / "27F" / "constraints.toml").read_text()
        self.assertIn("Configuration package: 27F", generated)

    def test_delete_file_moves_it_to_trash_and_makes_package_draft(self):
        payload = webapp._delete_configuration_file("27S", "locations.toml")

        self.assertEqual(payload["status"], "draft")
        self.assertFalse(
            (self.config_root / "27S" / "basicinfo" / "locations.toml").exists()
        )
        self.assertTrue(any(webapp.CONFIG_TRASH.rglob("locations.toml")))

    def test_delete_package_moves_it_to_trash(self):
        webapp._delete_configuration_package("27S")

        self.assertFalse((self.config_root / "27S").exists())
        self.assertTrue(any(webapp.CONFIG_TRASH.glob("27S-*")))

    def _production_schedule(self):
        config = SolverConfig.load(self.config_root, package="27S")
        source = (
            Path(__file__).parents[1] / "inputs" / "27S"
            / "Course Schedule Report_20260820_175924.csv"
        )
        records = pd.read_csv(source, dtype=str).to_dict(orient="records")
        schedule, _ = reconcile_records(records, config)
        return schedule, config

    def _source_template(self) -> Path:
        return (
            Path(__file__).parents[1] / "inputs" / "27S"
            / "Course Schedule Report_20260820_175924.csv"
        )

    def test_template_inference_fills_only_missing_configuration_files(self):
        draft = self.config_root / "DRAFT"
        (draft / "basicinfo").mkdir(parents=True)
        catalogs = self.config_root / "27S" / "basicinfo" / "catalogs.toml"
        shutil.copy2(catalogs, draft / "basicinfo" / "catalogs.toml")
        source = self._source_template()
        inferred = webapp._infer_uploaded_template(
            source.name, source.read_bytes(), package="DRAFT",
        )
        incoming = {"locations.toml": inferred.files["locations.toml"]}

        missing = webapp._missing_inferred_files(
            "DRAFT", inferred.files, incoming,
        )

        self.assertNotIn("catalogs.toml", missing)
        self.assertNotIn("locations.toml", missing)
        self.assertEqual(set(missing), set(webapp.CONFIG_FILES) - {
            "catalogs.toml", "locations.toml",
        })

    def test_full_template_inference_creates_next_independent_package(self):
        (self.config_root / "推断(1)").mkdir()
        source = self._source_template()
        package = webapp._next_inferred_package_name()
        inferred = webapp._infer_uploaded_template(
            source.name, source.read_bytes(), package=package,
        )

        webapp._apply_configuration_transaction({package: {
            "replacements": inferred.files,
            "rebuild": True,
        }})

        self.assertEqual(package, "推断(2)")
        self.assertEqual(
            SolverConfig.load(self.config_root, package=package).package_id,
            package,
        )
        self.assertIsNone(webapp.find_template(self.config_root / package))
        self.assertTrue(
            (webapp.WORK_ROOT / package / "initial" / "initial.csv").is_file()
        )
        summary = webapp.template_summary(
            self.config_root / package, webapp.WORK_ROOT,
        )
        self.assertEqual(summary["work_views"]["source"], "generated_default")

    def test_generated_chinese_package_name_is_valid_upload_metadata(self):
        content = b"# Configuration package: \xe6\x8e\xa8\xe6\x96\xad(1)\n"

        self.assertEqual(
            webapp._package_name_from_comments({"constraints.toml": content}),
            "推断(1)",
        )

    def test_web_analysis_uses_authoritative_evaluation_loads(self):
        schedule, config = self._production_schedule()

        payload = webapp._analysis_payload(schedule, config)
        evaluation = evaluate_schedule(
            schedule, config.preferences, config.persons, config.global_rules,
            config.meeting_patterns, config.constraint_rules,
            config.workload_policy, config.back_to_back_policy,
        )

        by_name = {row["name"]: row for row in payload["instructor_loads"]}
        self.assertEqual(by_name["new_instructor"]["hours"],
                         evaluation.loads["new_instructor"])
        self.assertEqual(
            by_name["new_instructor"]["target"],
            config.new_instructor_policy.contract_load,
        )
        self.assertEqual(payload["atomic_classes"], len(schedule))

    def test_all_three_web_exports_use_schedule_excel_builders(self):
        schedule, _ = self._production_schedule()

        for method in (
            "to_raw_excel", "to_instructor_excel", "to_room_excel",
        ):
            with self.subTest(method=method):
                content = webapp._excel_bytes(schedule, method)
                self.assertTrue(content.startswith(b"PK"))

    def test_template_without_courses_still_refreshes_work_views(self):
        package = self.config_root / "DRAFT"
        package.mkdir()
        content = (
            "Subject,Number,Section,Credits,Time Slot,Duration,Building,Room,Instructor\n"
            "MATH,1003,001,3,MWF 8:00am,50,Corley,101,Alice\n"
        ).encode()
        webapp.install_template(package, "arbitrary-name.csv", content)

        summary = webapp._rebuild_package_work_views("DRAFT")

        self.assertEqual(summary["work_views"]["source"], "template_only")
        self.assertFalse(summary["work_views"]["differences"]["available"])
        self.assertIsNotNone(summary["uploaded_at"])
        self.assertIsNotNone(datetime.fromisoformat(summary["uploaded_at"]).tzinfo)
        self.assertTrue(
            (webapp.WORK_ROOT / "DRAFT" / "initial" / "initial.csv").is_file()
        )

    def test_template_only_groups_marked_cross_lists_but_not_unmarked_pairs(self):
        package = self.config_root / "DRAFT"
        package.mkdir()
        header = (
            "Subject,Number,Section,Credits,Time Slot,Duration,Building,Room,"
            "Instructor,Cross-List\n"
        )
        content = (header
            + "MATH,1113,001,3,MWF 8:00am,50,Corley,101,Alice,XL1\n"
            + "STAT,2103,001,3,MWF 8:00am,50,Corley,101,Alice,XL1\n"
            + "MATH,1003,003,3,MWF 10:00am,50,Corley,103,Carol,\n"
            + "MATH,0803,003,3,TR 10:00am,80,Corley,104,Carol,\n"
            + "MATH,5173,004,3,MWF 1:00pm,50,Corley,105,Dan,\n"
            + "STAT,4173,004,3,MWF 1:00pm,50,Corley,105,Dan,\n"
            + "MATH,1914,002,4,MWF 9:00am,50,Corley,102,Bob,\n"
            + "MATH,1914,002,4,T 9:00am,50,Corley,102,Bob,\n"
        ).encode()
        webapp.install_template(package, "unconfigured.csv", content)

        webapp._rebuild_package_work_views("DRAFT")
        records = pd.read_csv(
            webapp.WORK_ROOT / "DRAFT" / "initial" / "initial.csv", dtype=str,
        ).to_dict(orient="records")
        schedule = webapp.Schedule.from_records(
            records, infer_legacy_relationships=False,
            infer_marked_cross_lists=True,
        )

        self.assertEqual(len(schedule.classes), 6)
        self.assertEqual(len(schedule.get("MATH 1914-002").sections), 2)
        self.assertEqual(len(schedule.get("MATH 1113-001").sections), 2)
        self.assertIs(
            schedule.get("MATH 1113-001"), schedule.get("STAT 2103-001"),
        )
        self.assertEqual(len(schedule.get("MATH 1003-003").sections), 1)
        self.assertEqual(len(schedule.get("MATH 0803-003").sections), 1)
        self.assertEqual(len(schedule.get("MATH 5173-004").sections), 1)
        self.assertEqual(len(schedule.get("STAT 4173-004").sections), 1)

    def test_draft_courses_do_not_clean_template_rows(self):
        package = self.config_root / "DRAFT"
        package.mkdir()
        (package / "courses.toml").write_text(
            "# Configuration package: DRAFT\n"
            "[[courses]]\nsubject='MATH'\nnumber='1003'\nsections=['001']\n",
            encoding="utf-8",
        )
        content = (
            "Subject,Number,Section,Credits,Time Slot,Duration,Building,Room,Instructor\n"
            "MATH,1003,001,3,MWF 8:00am,50,Corley,101,Alice\n"
            "MATH,9999,EXTRA,3,TR 9:30am,80,Corley,102,Bob\n"
        ).encode()
        webapp.install_template(package, "draft.csv", content)

        webapp._rebuild_package_work_views("DRAFT")
        output = pd.read_csv(
            webapp.WORK_ROOT / "DRAFT" / "initial" / "initial.csv", dtype=str,
        )

        self.assertEqual(set(output["Number"]), {"1003", "9999"})

    def test_ready_package_courses_clean_template_rows(self):
        package = self.config_root / "27S"
        source = (
            Path(__file__).parents[1] / "inputs" / "27S"
            / "Course Schedule Report_20260820_175924.csv"
        )
        dataframe = pd.read_csv(source, dtype=str)
        extra = dataframe.iloc[[0]].copy()
        extra["Subject"], extra["Number"], extra["Section"] = "MATH", "9999", "EXTRA"
        content = pd.concat([dataframe, extra], ignore_index=True).to_csv(index=False).encode()
        webapp.install_template(package, "ready.csv", content)

        summary = webapp._rebuild_package_work_views("27S")
        output = pd.read_csv(
            webapp.WORK_ROOT / "27S" / "initial" / "initial.csv", dtype=str,
        )

        self.assertEqual(summary["work_views"]["source"], "template_and_courses")
        self.assertNotIn("9999", set(output["Number"]))
        self.assertIn(
            "MATH 9999 EXTRA",
            summary["work_views"]["differences"]["removed"],
        )
        tc_rows = output[
            output["Section"].str.upper().eq("TC1")
            & output["Number"].isin(["0903", "1113"])
        ]
        self.assertEqual(set(tc_rows["Time Slot"]), {"ONLINE"})

    def test_courses_without_template_generate_default_work_views(self):
        summary = webapp._rebuild_package_work_views("27S")

        self.assertEqual(summary["work_views"]["source"], "generated_default")
        self.assertTrue(summary["work_views"]["differences"]["available"])
        self.assertTrue(summary["work_views"]["differences"]["added"])
        self.assertTrue(
            (webapp.WORK_ROOT / "27S" / "initial" / "initial_instructor.xlsx").is_file()
        )

    def test_generated_default_avoids_basic_instructor_and_room_conflicts(self):
        webapp._rebuild_package_work_views("27S")
        config = SolverConfig.load(self.config_root, package="27S")
        records = pd.read_csv(
            webapp.WORK_ROOT / "27S" / "initial" / "initial.csv",
            dtype=str,
        ).to_dict(orient="records")
        schedule = webapp.Schedule.from_records(
            records, persons=config.persons,
            relationships=tuple(config.courses.relationships),
            catalogs=tuple(config.catalogs.courses),
        )

        basic_conflicts = [
            item for item in evaluate_schedule(
                schedule, config.preferences, config.persons,
            ).hard_violations
            if item.rule in {"instructor_conflict", "room_conflict"}
        ]
        self.assertEqual(basic_conflicts, [])

    def test_rebuilt_manifest_is_accepted_by_solver_provenance_check(self):
        webapp._rebuild_package_work_views("27S")
        initial = webapp.WORK_ROOT / "27S" / "initial" / "initial.csv"

        reconciliation, manifest = _verified_initial(initial)

        self.assertEqual(reconciliation.name, "reconciliation.toml")
        self.assertEqual(manifest["configuration"]["package_id"], "27S")
        self.assertEqual(manifest["initial"]["path"], "initial.csv")
        self.assertIsInstance(manifest["files"], dict)

    def test_schedule_workspace_loads_directly_from_selected_configuration(self):
        webapp._rebuild_package_work_views("27S")
        config = SolverConfig.load(self.config_root, package="27S")

        source, schedule = webapp._load_workspace_schedule("27S", config)

        self.assertEqual(source, "initial.csv")
        self.assertGreater(len(schedule), 0)

    def test_configuration_summary_only_opens_verified_working_view_tab(self):
        self.assertFalse(webapp._configuration_summary("27S")["working_view_ready"])

        webapp._rebuild_package_work_views("27S")
        self.assertTrue(webapp._configuration_summary("27S")["working_view_ready"])

        initial = webapp.WORK_ROOT / "27S" / "initial" / "initial.csv"
        initial.write_bytes(initial.read_bytes() + b"\n")
        self.assertFalse(webapp._configuration_summary("27S")["working_view_ready"])

    def test_schedule_workspace_rejects_missing_working_view(self):
        config = SolverConfig.load(self.config_root, package="27S")

        with self.assertRaises(HTTPException) as context:
            webapp._load_workspace_schedule("27S", config)

        self.assertEqual(context.exception.status_code, 409)

    def test_schedule_api_and_ui_no_longer_accept_a_schedule_upload(self):
        routes = {
            (route.path, frozenset(route.methods or ()))
            for route in webapp.create_app().routes
            if hasattr(route, "methods")
        }
        html = (webapp.PACKAGE_WEB / "index.html").read_text(encoding="utf-8")

        self.assertIn(("/api/schedule", frozenset({"GET"})), routes)
        self.assertIn((
            "/api/configuration-packages/{package}/infer-from-template",
            frozenset({"POST"}),
        ), routes)
        self.assertNotIn('id="scheduleFile"', html)
        self.assertNotIn('id="emptyFile"', html)
        self.assertIn('id="workspaceNav"', html)
        self.assertIn('class="workspace-tab active" data-workspace="configuration"', html)
        self.assertNotIn('data-workspace="schedule">Schedule</button>', html)
        script = (webapp.PACKAGE_WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="configurationTemplateInfer"', script)
        self.assertIn('item.working_view_ready', script)
        self.assertIn('schedule-package-tab', script)
        self.assertIn('await loadPackages(managedPackage())', script)
        self.assertIn('data-instructor=', script)
        self.assertIn('event.target.closest(".load-row-button")', script)
        self.assertIn('function recordClock(minute)', script)
        # moveSection no longer computes Time Slot/Duration locally -- it
        # posts to POST /api/edit and waits for the server's answer (see
        # docs/codes.md's "linking rules moved ... behind POST /api/edit").
        self.assertIn('submitEdit(classIndex,recordIndex,"time",{days:newDays,start})', script)
        self.assertIn("expected_course_ids:item.course_ids", script)
        self.assertIn('expected_time_slot:row["Time Slot"]', script)

    def test_replacing_template_keeps_only_the_latest_original_filename(self):
        package = self.config_root / "27S"
        first = (
            Path(__file__).parents[1] / "inputs" / "27S"
            / "Course Schedule Report_20260820_175924.csv"
        ).read_bytes()
        webapp.install_template(package, "first.csv", first)
        webapp.install_template(package, "later.csv", first)

        self.assertEqual(webapp.find_template(package).name, "later.csv")
        self.assertEqual(len(list((package / "template").iterdir())), 1)

    def test_failed_template_rebuild_commits_nothing(self):
        package = self.config_root / "27S"
        webapp._rebuild_package_work_views("27S")
        initial = webapp.WORK_ROOT / "27S" / "initial" / "initial.csv"
        original_view = initial.read_bytes()
        partial_relationship = (
            "Subject,Number,Section,Credits,Time Slot,Duration,Building,Room,Instructor\n"
            "MATH,0803,001,3,MWF 8:00am,50,Corley,101,new_instructor\n"
        ).encode()

        with self.assertRaises(HTTPException) as context:
            webapp._apply_configuration_transaction({"27S": {
                "template": ("partial.csv", partial_relationship),
                "rebuild": True,
            }})

        self.assertEqual(context.exception.status_code, 422)
        self.assertIsNone(webapp.find_template(package))
        self.assertEqual(initial.read_bytes(), original_view)



if __name__ == "__main__":
    unittest.main()
