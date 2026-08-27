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

    def test_infers_complete_valid_package_without_coreqs(self):
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
            self.assertCountEqual(kinds, ["hybrid", "four_credit", "cross_listing"])
            self.assertNotIn("coreq", kinds)
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


if __name__ == "__main__":
    unittest.main()
