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

    def test_section_prefix_matches_across_courses_case_insensitively(self):
        rule = PreferenceRule(section_prefix="tc")
        self.assertTrue(rule.matches(
            course="MATH 2703", section="TC1", building="", room="",
            days=None, start=None, end=None,
        ))
        self.assertFalse(rule.matches(
            course="STAT 2163", section="001", building="", room="",
            days=None, start=None, end=None,
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
    def test_parses_flat_named_prefer_rule(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"
allow_overload = false

[[rules]]
name = "Xiao, Xinli"
preferred_course = "MATH 2934"
preferred_room = "Corley 269"
weight = 100
""")
        self.addCleanup(path.unlink)
        preferences = load_preferences(path)
        rules = preferences["Xiao, Xinli"].rules
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].course, "MATH 2934")
        self.assertEqual(rules[0].room, "Corley 269")
        self.assertEqual(rules[0].direction, "prefer")
        self.assertEqual(rules[0].weight, 100)

    def test_parses_cross_course_section_prefix_rule(self):
        path = write_toml("""
[[instructors]]
name = "Limperis, Thomas G."

[[rules]]
name = "Limperis, Thomas G."
disliked_section_prefix = "TC"
weight = 10
""")
        self.addCleanup(path.unlink)
        rule = load_preferences(path)["Limperis, Thomas G."].rules[0]
        self.assertEqual(rule.section_prefix, "TC")
        self.assertEqual(rule.signed_weight, 10)

    def test_instructor_without_rules_gets_empty_tuple(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"
allow_overload = false
""")
        self.addCleanup(path.unlink)
        preferences = load_preferences(path)
        self.assertEqual(preferences["Xiao, Xinli"].rules, ())

    def test_single_selector_is_a_valid_flat_rule(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

[[rules]]
name = "Xiao, Xinli"
disliked_course = "MATH 2934"
weight = 50
""")
        self.addCleanup(path.unlink)
        rule = load_preferences(path)["Xiao, Xinli"].rules[0]
        self.assertEqual(rule.course, "MATH 2934")
        self.assertEqual(rule.signed_weight, 50)

    def test_section_without_course_raises(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

[[rules]]
name = "Xiao, Xinli"
preferred_section = "F01"
preferred_room = "Corley 269"
weight = 100
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)

    def test_setting_both_directions_raises(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

[[rules]]
name = "Xiao, Xinli"
preferred_room = "Corley 269"
disliked_room = "Rothwell"
weight = 100
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)

    def test_rule_name_not_a_comment_controls_scope(self):
        path = write_toml("""
# This deliberately says Alice, but comments have no semantic effect.
[[instructors]]
name = "Alice"

[[instructors]]
name = "Bob"

[[rules]]
name = "Bob"
preferred_room = "Corley 101"
weight = 25
""")
        self.addCleanup(path.unlink)
        preferences = load_preferences(path)
        self.assertEqual(preferences["Alice"].rules, ())
        self.assertEqual(preferences["Bob"].rules[0].room, "Corley 101")

    def test_named_rule_requires_a_matching_profile(self):
        path = write_toml("""
[[rules]]
name = "Nobody"
preferred_room = "Corley 101"
weight = 25
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)


class LoadPreferencesNewFieldsTests(unittest.TestCase):
    def test_parses_prefers_online_and_max_back_to_back(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"
prefers_online = { weight = 25 }
max_back_to_back = 2
""")
        self.addCleanup(path.unlink)
        preference = load_preferences(path)["Xiao, Xinli"]
        self.assertEqual(preference.preferred_online_weight, 25)
        self.assertEqual(preference.max_back_to_back, 2)

    def test_parses_weighted_flat_preferences(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

[[rules]]
name = "Xiao, Xinli"
preferred_time = { days = ["M", "W"], between = ["09:00", "11:00"] }
weight = 7

[[rules]]
name = "Xiao, Xinli"
disliked_room = "Rothwell"
weight = 11

[[rules]]
name = "Xiao, Xinli"
preferred_course = "MATH 2934"
weight = 13
""")
        self.addCleanup(path.unlink)
        preference = load_preferences(path)["Xiao, Xinli"]
        self.assertEqual([rule.weight for rule in preference.rules], [7, 11, 13])
        self.assertEqual(
            [rule.direction for rule in preference.rules],
            ["prefer", "dislike", "prefer"],
        )

    def test_parses_all_weekday_time_shorthand(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

[[rules]]
name = "Xiao, Xinli"
preferred_time = "8-12"
weight = 50
""")
        self.addCleanup(path.unlink)
        rule = load_preferences(path)["Xiao, Xinli"].rules[0]
        self.assertEqual(rule.time.days, frozenset("MTWRF"))
        self.assertEqual(rule.time.start, datetime.time(8, 0))
        self.assertEqual(rule.time.end, datetime.time(12, 0))

    def test_rejects_invalid_time_shorthand(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

[[rules]]
name = "Xiao, Xinli"
preferred_time = "morning"
weight = 50
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)

    def test_flat_rule_requires_weight(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

[[rules]]
name = "Xiao, Xinli"
disliked_course = "MATH 2934"
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)

    def test_legacy_named_lists_are_rejected(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"
disliked_courses = [{ course = "MATH 2934", weight = 50 }]
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)

    def test_both_default_to_off(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"
""")
        self.addCleanup(path.unlink)
        preference = load_preferences(path)["Xiao, Xinli"]
        self.assertIsNone(preference.preferred_online_weight)
        self.assertIsNone(preference.max_back_to_back)


class PrefersOnlineTests(unittest.TestCase):
    def test_in_person_section_is_penalized(self):
        section = make_section(instructor="Alice")
        schedule = Schedule([NormalClass((section,))])
        preferences = {
            "Alice": PreferenceRecord(name="Alice", preferred_online_weight=25)
        }
        total, findings = check_soft_preferences(schedule, preferences, {})
        self.assertEqual(total, 25.0)
        self.assertTrue(any(f.rule == "online_preference" for f in findings))

    def test_online_section_is_not_penalized(self):
        section = make_section(instructor="Alice", **{"time_slot": "TBA", "duration": None})
        schedule = Schedule([NormalClass((section,))])
        preferences = {
            "Alice": PreferenceRecord(name="Alice", preferred_online_weight=25)
        }
        total, findings = check_soft_preferences(schedule, preferences, {})
        self.assertEqual(total, 0.0)
        self.assertFalse(any(f.rule == "online_preference" for f in findings))

    def test_default_false_is_never_penalized(self):
        section = make_section(instructor="Alice")
        schedule = Schedule([NormalClass((section,))])
        preferences = {"Alice": PreferenceRecord(name="Alice")}
        total, findings = check_soft_preferences(schedule, preferences, {})
        self.assertFalse(any(f.rule == "online_preference" for f in findings))


class MaxBackToBackTests(unittest.TestCase):
    def test_run_of_exactly_cap_is_unflagged(self):
        # Two back-to-back 50-minute classes, 9:00-9:50 and 9:50-10:40.
        a = make_section(number="1113", section="001", instructor="Alice", **{"time_slot": "MWF 9:00am"}, duration=50)
        b = make_section(number="1003", section="001", instructor="Alice", **{"time_slot": "MWF 9:50am"}, duration=50)
        schedule = Schedule([NormalClass((a,)), NormalClass((b,))])
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_back_to_back=True, max_back_to_back=2)}
        total, findings = check_soft_preferences(schedule, preferences, {})
        self.assertEqual([f for f in findings if f.rule == "back_to_back"], [])

    def test_third_in_a_row_is_flagged_once(self):
        a = make_section(number="1113", section="001", instructor="Alice", **{"time_slot": "MWF 9:00am"}, duration=50)
        b = make_section(number="1003", section="001", instructor="Alice", **{"time_slot": "MWF 9:50am"}, duration=50)
        c = make_section(number="2914", section="001", instructor="Alice", **{"time_slot": "MWF 10:40am"}, duration=50)
        schedule = Schedule([NormalClass((a,)), NormalClass((b,)), NormalClass((c,))])
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_back_to_back=True, max_back_to_back=2)}
        total, findings = check_soft_preferences(schedule, preferences, {})
        b2b = [f for f in findings if f.rule == "back_to_back"]
        self.assertEqual(len(b2b), 1)

    def test_fourth_in_a_row_is_flagged_twice(self):
        a = make_section(number="1113", section="001", instructor="Alice", **{"time_slot": "MWF 9:00am"}, duration=50)
        b = make_section(number="1003", section="001", instructor="Alice", **{"time_slot": "MWF 9:50am"}, duration=50)
        c = make_section(number="2914", section="001", instructor="Alice", **{"time_slot": "MWF 10:40am"}, duration=50)
        d = make_section(number="2924", section="001", instructor="Alice", **{"time_slot": "MWF 11:30am"}, duration=50)
        schedule = Schedule([NormalClass((a,)), NormalClass((b,)), NormalClass((c,)), NormalClass((d,))])
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_back_to_back=True, max_back_to_back=2)}
        total, findings = check_soft_preferences(schedule, preferences, {})
        b2b = [f for f in findings if f.rule == "back_to_back"]
        self.assertEqual(len(b2b), 2)

    def test_allow_back_to_back_false_ignores_the_cap(self):
        # A cap can't loosen allow_back_to_back=False -- every pair is
        # still flagged, even a run that would be within the cap.
        a = make_section(number="1113", section="001", instructor="Alice", **{"time_slot": "MWF 9:00am"}, duration=50)
        b = make_section(number="1003", section="001", instructor="Alice", **{"time_slot": "MWF 9:50am"}, duration=50)
        schedule = Schedule([NormalClass((a,)), NormalClass((b,))])
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_back_to_back=False, max_back_to_back=2)}
        total, findings = check_soft_preferences(schedule, preferences, {})
        self.assertEqual(len([f for f in findings if f.rule == "back_to_back"]), 1)

    def test_gap_between_classes_does_not_chain(self):
        a = make_section(number="1113", section="001", instructor="Alice", **{"time_slot": "MWF 9:00am"}, duration=50)
        b = make_section(number="1003", section="001", instructor="Alice", **{"time_slot": "MWF 11:00am"}, duration=50)
        c = make_section(number="2914", section="001", instructor="Alice", **{"time_slot": "MWF 11:50am"}, duration=50)
        schedule = Schedule([NormalClass((a,)), NormalClass((b,)), NormalClass((c,))])
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_back_to_back=True, max_back_to_back=2)}
        total, findings = check_soft_preferences(schedule, preferences, {})
        # a is isolated (gap before b); b, c form a run of 2 -- still within cap.
        self.assertEqual([f for f in findings if f.rule == "back_to_back"], [])


class LoadGlobalRulesTests(unittest.TestCase):
    def test_parses_top_level_rules_regardless_of_instructor(self):
        path = write_toml("""
[[rules]]
preferred_course = "MATH 1113"
preferred_section = "F01"
preferred_room = "Corley 269"
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
    def test_named_dislikes_report_each_configured_weight(self):
        section = make_section(instructor="Alice", room="101", building="Corley")
        schedule = Schedule([NormalClass((section,))])
        preferences = {"Alice": PreferenceRecord(
            name="Alice",
            rules=(
                PreferenceRule(time=TimeWindow(
                    frozenset("MWF"), datetime.time(8), datetime.time(10),
                ), direction="dislike", weight=7),
                PreferenceRule(room="Corley", direction="dislike", weight=11),
                PreferenceRule(course="MATH 1113", direction="dislike", weight=13),
            ),
        )}
        total, findings = check_soft_preferences(schedule, preferences, {})
        self.assertEqual(total, 31)
        self.assertEqual([finding.rule for finding in findings], ["custom_rule"] * 3)
        self.assertEqual(sorted(finding.penalty for finding in findings), [7, 11, 13])

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
