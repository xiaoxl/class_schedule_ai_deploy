import datetime
import tempfile
import unittest
from pathlib import Path

from class_schedule.class_model import NormalClass, Section
from class_schedule.schedule_model import (
    PreferenceRecord,
    PreferenceRule,
    Schedule,
    TimeWindow,
    check_soft_preferences,
    load_global_rules,
    load_preferences,
)


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


def write_toml(text: str) -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".toml", delete=False, encoding="utf-8"
    )
    handle.write(text)
    handle.close()
    return Path(handle.name)


class PreferenceRuleMatchesTests(unittest.TestCase):
    def test_no_fields_set_matches_anything(self):
        rule = PreferenceRule()
        self.assertTrue(rule.matches(
            course="MATH 1113", section="001", building="Corley", room="101",
            days="MWF", start=datetime.time(9, 0), end=datetime.time(9, 50),
        ))

    def test_course_must_match(self):
        rule = PreferenceRule(course="MATH 1113")
        self.assertFalse(rule.matches(
            course="STAT 2103", section="001", building="Corley", room="101",
            days="MWF", start=datetime.time(9, 0), end=datetime.time(9, 50),
        ))

    def test_room_matches_building_or_full_string(self):
        rule = PreferenceRule(room="Corley 269")
        self.assertTrue(rule.matches(
            course="MATH 1113", section="001", building="Corley", room="269",
            days="MWF", start=datetime.time(9, 0), end=datetime.time(9, 50),
        ))
        self.assertFalse(rule.matches(
            course="MATH 1113", section="001", building="Corley", room="101",
            days="MWF", start=datetime.time(9, 0), end=datetime.time(9, 50),
        ))

    def test_time_window_must_overlap(self):
        rule = PreferenceRule(
            time=TimeWindow(days=frozenset("TR"), start=datetime.time(8, 0), end=datetime.time(9, 30))
        )
        self.assertTrue(rule.matches(
            course="MATH 1113", section="001", building="Corley", room="101",
            days="TR", start=datetime.time(8, 30), end=datetime.time(9, 45),
        ))
        self.assertFalse(rule.matches(
            course="MATH 1113", section="001", building="Corley", room="101",
            days="MWF", start=datetime.time(8, 30), end=datetime.time(9, 20),
        ))

    def test_signed_weight_prefer_is_negative(self):
        self.assertEqual(PreferenceRule(direction="prefer", weight=100).signed_weight, -100)

    def test_signed_weight_dislike_is_positive(self):
        self.assertEqual(PreferenceRule(direction="dislike", weight=100).signed_weight, 100)


class LoadPreferencesRulesTests(unittest.TestCase):
    def test_parses_instructor_scoped_rules(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"
allow_overload = false

  [[instructors.rules]]
  room = "Corley 269"
  direction = "prefer"
  weight = 100
""")
        self.addCleanup(path.unlink)
        preferences = load_preferences(path)
        rules = preferences["Xiao, Xinli"].rules
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].room, "Corley 269")
        self.assertEqual(rules[0].direction, "prefer")
        self.assertEqual(rules[0].weight, 100)

    def test_instructor_without_rules_gets_empty_tuple(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"
allow_overload = false
""")
        self.addCleanup(path.unlink)
        preferences = load_preferences(path)
        self.assertEqual(preferences["Xiao, Xinli"].rules, ())

    def test_section_without_course_raises(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

  [[instructors.rules]]
  section = "F01"
  room = "Corley 269"
  direction = "prefer"
  weight = 100
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)

    def test_invalid_direction_raises(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

  [[instructors.rules]]
  room = "Corley 269"
  direction = "sideways"
  weight = 100
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)


class LoadGlobalRulesTests(unittest.TestCase):
    def test_parses_top_level_rules_regardless_of_instructor(self):
        path = write_toml("""
[[rules]]
course = "MATH 1113"
section = "F01"
room = "Corley 269"
direction = "prefer"
weight = 100

[[instructors]]
name = "Xiao, Xinli"
""")
        self.addCleanup(path.unlink)
        rules = load_global_rules(path)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].course, "MATH 1113")
        self.assertEqual(rules[0].section, "F01")

    def test_no_top_level_rules_is_empty_tuple(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"
""")
        self.addCleanup(path.unlink)
        self.assertEqual(load_global_rules(path), ())


class CheckSoftPreferencesRuleFindingsTests(unittest.TestCase):
    def test_matching_dislike_rule_produces_a_finding(self):
        section = make_section(instructor="Alice", room="101", building="Corley")
        schedule = Schedule([NormalClass((section,))])
        preferences = {"Alice": PreferenceRecord(
            name="Alice",
            rules=(PreferenceRule(room="Corley 101", direction="dislike", weight=10),),
        )}
        total, findings = check_soft_preferences(schedule, preferences, {})
        self.assertEqual(total, 10)
        self.assertTrue(any(f.rule == "custom_rule" for f in findings))

    def test_matching_prefer_rule_produces_no_finding(self):
        section = make_section(instructor="Alice", room="101", building="Corley")
        schedule = Schedule([NormalClass((section,))])
        preferences = {"Alice": PreferenceRecord(
            name="Alice",
            rules=(PreferenceRule(room="Corley 101", direction="prefer", weight=10),),
        )}
        total, findings = check_soft_preferences(schedule, preferences, {})
        self.assertEqual(total, 0.0)
        self.assertFalse(any(f.rule == "custom_rule" for f in findings))

    def test_global_rule_applies_even_without_a_preference_record(self):
        section = make_section(
            subject="MATH", number="1113", section="F01",
            instructor="Bob", room="101", building="Corley",
        )
        schedule = Schedule([NormalClass((section,))])
        global_rules = (
            PreferenceRule(
                course="MATH 1113", section="F01", room="Corley 269",
                direction="dislike", weight=100,
            ),
        )
        # "Bob" has no preferences.toml entry at all -- the global rule
        # must still apply (it's the whole point of not scoping it to an
        # instructor).
        total, findings = check_soft_preferences(schedule, {}, {}, global_rules)
        self.assertEqual(total, 0.0)  # room is 101, not 269 -- rule doesn't match this schedule
        self.assertEqual(findings, [])

        section_in_disliked_room = make_section(
            subject="MATH", number="1113", section="F01",
            instructor="Bob", room="269", building="Corley",
        )
        schedule2 = Schedule([NormalClass((section_in_disliked_room,))])
        total2, findings2 = check_soft_preferences(schedule2, {}, {}, global_rules)
        self.assertEqual(total2, 100)
        self.assertTrue(any(f.rule == "custom_rule" for f in findings2))


if __name__ == "__main__":
    unittest.main()
