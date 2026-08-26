import tempfile
import unittest
from pathlib import Path

from class_schedule.cli import CONFIG_ROOT, build_parser
from class_schedule.template_workspace import require_unique_template


class InitialCommandTests(unittest.TestCase):
    def test_initial_accepts_only_a_configuration_name(self):
        args = build_parser().parse_args(["initial", "27S"])

        self.assertEqual(CONFIG_ROOT, Path("config"))
        self.assertEqual(args.config_name, "27S")
        self.assertFalse(hasattr(args, "input"))
        self.assertFalse(hasattr(args, "config"))
        self.assertFalse(hasattr(args, "package"))

    def test_commands_use_one_configuration_name(self):
        parser = build_parser()
        self.assertEqual(
            parser.parse_args(["solve", "27F"]).config_name, "27F",
        )
        imported = parser.parse_args(["import-template", "27F", "source.xlsx"])
        self.assertEqual((imported.config_name, imported.input), ("27F", "source.xlsx"))

    def test_finds_the_only_table_anywhere_inside_the_package(self):
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / "27S"
            template = package / "template" / "arbitrary name.xlsx"
            template.parent.mkdir(parents=True)
            template.write_bytes(b"table")

            self.assertEqual(require_unique_template(package), template)

    def test_rejects_a_package_without_a_table(self):
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / "27S"
            package.mkdir()

            with self.assertRaisesRegex(FileNotFoundError, "no CSV/XLSX"):
                require_unique_template(package)

    def test_rejects_multiple_tables_and_lists_them(self):
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / "27S"
            (package / "template").mkdir(parents=True)
            (package / "first.csv").write_text("a\n1\n", encoding="utf-8")
            (package / "template" / "second.xlsx").write_bytes(b"table")

            with self.assertRaisesRegex(
                ValueError, "first.csv.*template/second.xlsx",
            ):
                require_unique_template(package)


if __name__ == "__main__":
    unittest.main()
