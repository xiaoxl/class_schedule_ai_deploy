import tempfile
import tomllib
import unittest
from pathlib import Path

import pandas as pd

from class_schedule.config_inference import infer_configuration_from_template
from class_schedule.solver import SolverConfig


class ConfigurationInferenceTests(unittest.TestCase):
    def _template(self, root: Path) -> Path:
        path = root / "source.csv"
        rows = [
            self._row("MATH", "0803", "001", "Foundations", 3, "MWF 8:00am", 50),
            self._row("MATH", "1003", "001", "College Math", 3, "MWF 9:00am", 50),
            self._row("MATH", "1113", "F01", "College Algebra", 3, "MWF 10:00am", 50),
            self._row("MATH", "1113", "F01", "College Algebra", 3, "ONLINE", None, room=""),
            self._row("MATH", "1914", "001", "Precalculus", 4, "MWF 9:00am", 50),
            self._row("MATH", "1914", "001", "Precalculus", 4, "T 9:30am", 80),
            self._row("MATH", "5173", "TC1", "Biostatistics", 3, "TR 11:00am", 80, cross="BIO"),
            self._row("STAT", "4173", "TC1", "Biostatistics", 3, "TR 11:00am", 80, cross="BIO"),
        ]
        pd.DataFrame(rows).to_csv(path, index=False)
        return path

    @staticmethod
    def _row(subject, number, section, title, credits, slot, duration, *, room="101", cross=""):
        return {
            "Subject": subject, "Number": number, "Section": section,
            "Title": title, "Credits": credits, "Instructor": "Teacher, Alice",
            "Time Slot": slot, "Duration": duration,
            "Building": "Corley" if room else "", "Room": room,
            "Cross-List": cross,
        }

    def test_infers_complete_valid_package_with_explicit_coreqs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package_name = "推断(1)"
            inferred = infer_configuration_from_template(
                self._template(root), package=package_name,
            )
            locations = {
                "catalogs.toml": Path("basicinfo/catalogs.toml"),
                "locations.toml": Path("basicinfo/locations.toml"),
                "timeslot.toml": Path("basicinfo/timeslot.toml"),
                "persons.toml": Path("basicinfo/persons.toml"),
                "courses.toml": Path("courses.toml"),
                "preferences.toml": Path("preferences.toml"),
                "constraints.toml": Path("constraints.toml"),
            }
            package = root / "config" / package_name
            for name, relative in locations.items():
                target = package / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(inferred.files[name])

            config = SolverConfig.load(root / "config", package=package_name)
            courses = tomllib.loads(inferred.files["courses.toml"].decode())
            kinds = [item["kind"] for item in courses["relationships"]]
            preferences = tomllib.loads(
                inferred.files["preferences.toml"].decode()
            )

            self.assertEqual(inferred.course_count, 6)
            self.assertEqual(inferred.section_count, 6)
            self.assertCountEqual(
                kinds, ["hybrid", "four_credit", "cross_listing", "coreq"],
            )
            cross_listing = next(
                item for item in courses["relationships"]
                if item["kind"] == "cross_listing"
            )
            # The template's MATH 5173/STAT 4173 rows already shared an
            # Fully shared means no fields are allowed to diverge.
            self.assertEqual(cross_listing["unsynced"], [])
            self.assertEqual(
                set(config.persons["Teacher, Alice"].courses),
                {
                    "MATH 0803", "MATH 1003", "MATH 1113", "MATH 1914",
                    "MATH 5173", "STAT 4173",
                },
            )
            self.assertTrue(preferences["instructors"][0]["allow_overload"])
            self.assertTrue(preferences["instructors"][0]["allow_back_to_back"])
            self.assertEqual(config.persons["Teacher, Alice"].max_load, 16)
            self.assertEqual(
                tomllib.loads(inferred.files["constraints.toml"].decode()), {}
            )

    def test_infers_unsynced_fields_when_the_template_pair_diverges(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "source.csv"
            pd.DataFrame([
                self._row(
                    "MATH", "5173", "TC1", "Biostatistics", 3,
                    "TR 11:00am", 80, room="101", cross="BIO",
                ),
                self._row(
                    "STAT", "4173", "TC1", "Biostatistics", 3,
                    "TR 11:00am", 80, room="205", cross="BIO",
                ),
            ]).to_csv(path, index=False)

            inferred = infer_configuration_from_template(path, package="TEST")
            courses = tomllib.loads(inferred.files["courses.toml"].decode())
            cross_listing = next(
                item for item in courses["relationships"]
                if item["kind"] == "cross_listing"
            )
            self.assertEqual(cross_listing["unsynced"], ["room"])

    def test_rejects_a_template_without_physical_times(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "online.csv"
            pd.DataFrame([self._row(
                "MATH", "1113", "TC1", "College Algebra", 3,
                "ONLINE", None, room="",
            )]).to_csv(path, index=False)

            with self.assertRaisesRegex(ValueError, "no physical meeting times"):
                infer_configuration_from_template(path, package="TEST")

    def test_coreq_inference_rejects_an_ambiguous_whitelist_match(self):
        # Regression: the coreq whitelist pairs "MATH 1113" with both
        # "MATH 0903" and "MATH 1110" -- if a template's section number is
        # shared by all three, "MATH 1113" matches two different
        # candidates, and inference used to silently pick whichever one
        # the scan reached first instead of flagging the ambiguity (see
        # docs/codes.md).
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.csv"
            pd.DataFrame([
                self._row("MATH", "0903", "003", "Corequisite Support", 1, "MWF 8:00am", 50),
                self._row("MATH", "1110", "003", "College Algebra Lab", 2, "MW 2:00pm", 50),
                self._row("MATH", "1113", "003", "College Algebra", 3, "MWF 1:00pm", 50),
            ]).to_csv(path, index=False)

            with self.assertRaisesRegex(ValueError, "Ambiguous coreq inference"):
                infer_configuration_from_template(path, package="TEST")

    def test_cross_list_marker_infers_all_members_and_unsynced_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.csv"
            pd.DataFrame([
                self._row("MATH", "3003", "001", "Shared", 3, "MWF 9:00am", 50, cross="X"),
                self._row("STAT", "4004", "001", "Shared", 4, "MWF 9:00am", 50, cross="X"),
                {**self._row("CS", "2002", "001", "Shared", 2, "MWF 9:00am", 50, cross="X"), "Room": "205"},
            ]).to_csv(path, index=False)
            inferred = infer_configuration_from_template(path, package="TEST")
        courses = tomllib.loads(inferred.files["courses.toml"].decode())
        relationship = courses["relationships"][0]
        self.assertEqual(relationship["kind"], "cross_listing")
        self.assertEqual(len(relationship["members"]), 3)
        self.assertEqual(relationship["unsynced"], ["room"])
        self.assertNotIn("id", relationship)


if __name__ == "__main__":
    unittest.main()
