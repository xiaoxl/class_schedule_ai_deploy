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
from class_schedule.solver.config import (
    load_staff_count_weight,
    load_staff_credit_weight,
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
course = "MATH 2934"
room = "Corley 269"
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
section_prefix = "TC"
weight = -10
""")
        self.addCleanup(path.unlink)
        rule = load_preferences(path)["Limperis, Thomas G."].rules[0]
        self.assertEqual(rule.section_prefix, "TC")
        self.assertEqual(rule.signed_weight, 10)

    def test_parses_room_alternatives_as_one_selector(self):
        path = write_toml("""
[[instructors]]
name = "Bain, Leslie M."

[[rules]]
name = "Bain, Leslie M."
course = "STAT 2163"
room = ["Corley 103", "Corley 104", "Rothwell 221"]
weight = 10
""")
        self.addCleanup(path.unlink)
        rule = load_preferences(path)["Bain, Leslie M."].rules[0]
        self.assertEqual(
            rule.rooms, ("Corley 103", "Corley 104", "Rothwell 221")
        )
        self.assertTrue(rule.matches(
            course="STAT 2163", section="001", building="Corley", room="104",
            days="MWF", start=datetime.time(9), end=datetime.time(9, 50),
        ))
        self.assertFalse(rule.matches(
            course="STAT 2163", section="001", building="Corley", room="105",
            days="MWF", start=datetime.time(9), end=datetime.time(9, 50),
        ))

    def test_rejects_duplicate_room_alternatives(self):
        path = write_toml("""
[[instructors]]
name = "Bain, Leslie M."

[[rules]]
name = "Bain, Leslie M."
room = ["Corley 103", "Corley 103"]
weight = 10
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)

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
course = "MATH 2934"
weight = -50
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
section = "F01"
room = "Corley 269"
weight = 100
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)

    def test_zero_weight_raises(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

[[rules]]
name = "Xiao, Xinli"
room = "Corley 269"
weight = 0
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
room = "Corley 101"
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
room = "Corley 101"
weight = 25
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)


class LoadPreferencesNewFieldsTests(unittest.TestCase):
    def test_parses_global_staff_count_weight(self):
        path = write_toml("staff_count_weight = 75\n")
        self.addCleanup(path.unlink)
        self.assertEqual(load_staff_count_weight(path), 75)

    def test_staff_count_weight_defaults_to_10(self):
        path = write_toml("")
        self.addCleanup(path.unlink)
        self.assertEqual(load_staff_count_weight(path), 10)

    def test_parses_global_staff_credit_weight(self):
        path = write_toml("staff_credit_weight = 25\n")
        self.addCleanup(path.unlink)
        self.assertEqual(load_staff_credit_weight(path), 25)

    def test_staff_credit_weight_defaults_to_5(self):
        path = write_toml("")
        self.addCleanup(path.unlink)
        self.assertEqual(load_staff_credit_weight(path), 5)

    def test_parses_tc_web_rule_and_max_back_to_back(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"
max_back_to_back = 2

[[rules]]
name = "Xiao, Xinli"
section_prefix = "TC"
weight = 25
""")
        self.addCleanup(path.unlink)
        preference = load_preferences(path)["Xiao, Xinli"]
        self.assertEqual(preference.max_back_to_back, 2)
        self.assertEqual(preference.rules[0].section_prefix, "TC")
        self.assertEqual(preference.rules[0].direction, "prefer")

    def test_parses_weighted_flat_preferences(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

[[rules]]
name = "Xiao, Xinli"
time = { days = ["M", "W"], between = ["09:00", "11:00"] }
weight = 7

[[rules]]
name = "Xiao, Xinli"
room = "Rothwell"
weight = -11

[[rules]]
name = "Xiao, Xinli"
course = "MATH 2934"
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
time = "8-12"
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
time = "morning"
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
course = "MATH 2934"
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

    def test_legacy_direction_prefix_is_rejected(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

[[rules]]
name = "Xiao, Xinli"
preferred_course = "MATH 2934"
weight = 50
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)

    def test_online_selector_is_rejected_in_favor_of_tc_prefix(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"

[[rules]]
name = "Xiao, Xinli"
online = true
weight = 50
""")
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError):
            load_preferences(path)

    def test_max_back_to_back_defaults_to_off(self):
        path = write_toml("""
[[instructors]]
name = "Xiao, Xinli"
""")
        self.addCleanup(path.unlink)
        preference = load_preferences(path)["Xiao, Xinli"]
        self.assertIsNone(preference.max_back_to_back)


class TcWebRuleTests(unittest.TestCase):
    def test_negative_tc_rule_is_reported(self):
        section = make_section(instructor="Alice", section="TC1")
        schedule = Schedule([NormalClass((section,))])
        preferences = {"Alice": PreferenceRecord(
            name="Alice",
            rules=(PreferenceRule(
                section_prefix="TC", direction="dislike", weight=25,
            ),),
        )}
        total, findings = check_soft_preferences(schedule, preferences, {})
        self.assertEqual(total, 25.0)
        self.assertTrue(any(f.rule == "custom_rule" for f in findings))

    def test_positive_tc_rule_is_not_reported_as_a_violation(self):
        section = make_section(instructor="Alice", section="TC1")
        schedule = Schedule([NormalClass((section,))])
        preferences = {"Alice": PreferenceRecord(
            name="Alice",
            rules=(PreferenceRule(
                section_prefix="TC", direction="prefer", weight=25,
            ),),
        )}
        total, findings = check_soft_preferences(schedule, preferences, {})
        self.assertEqual(total, 0.0)
        self.assertFalse(any(f.rule == "custom_rule" for f in findings))

    def test_tc_selector_does_not_match_non_tc_section(self):
        section = make_section(instructor="Alice")
        rule = PreferenceRule(
            section_prefix="TC", direction="prefer", weight=25,
        )
        self.assertFalse(rule.matches(
            course="MATH 1113", section="001", building="Corley", room="101",
            days=section.days, start=section.start, end=section.end,
        ))


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
        # The join is between the 2nd and 3rd class in the run (b, c) --
        # _capped_back_to_back_findings takes (RecordReference, Section)
        # pairs specifically so it can still report which two records
        # this is, after re-sorting/re-filtering sections into a run
        # (see docs/codes.md).
        self.assertEqual(
            {(r.class_index, r.record_index, r.course_id) for r in b2b[0].references},
            {(1, 0, "MATH 1003-001"), (2, 0, "MATH 2914-001")},
        )

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

    def test_two_unrelated_runs_that_share_a_course_id_pair_are_not_deduped(self):
        # Regression: the dedup used to key on (prev.course_id,
        # last.course_id) -- two *different* physical meetings that
        # happen to share a course_id string (two distinct single-weekday
        # classes reusing the same subject/number/section, on different
        # days) would wrongly look like the same recurring join and the
        # second one would be silently dropped. Now keyed on
        # (class_index, record_index) pairs instead (see docs/codes.md).
        monday = [
            make_section(number="1001", section="A", instructor="Alice", **{"time_slot": "M 9:00am"}, duration=50),
            make_section(number="1002", section="B", instructor="Alice", **{"time_slot": "M 9:50am"}, duration=50),
            make_section(number="1003", section="C", instructor="Alice", **{"time_slot": "M 10:40am"}, duration=50),
        ]
        wednesday = [
            make_section(number="1004", section="D", instructor="Alice", **{"time_slot": "W 9:00am"}, duration=50),
            # Same course_id as Monday's 2nd/3rd classes, but genuinely
            # different meetings (different weekday, different objects).
            make_section(number="1002", section="B", instructor="Alice", **{"time_slot": "W 9:50am"}, duration=50),
            make_section(number="1003", section="C", instructor="Alice", **{"time_slot": "W 10:40am"}, duration=50),
        ]
        schedule = Schedule([NormalClass((s,)) for s in monday + wednesday])
        preferences = {"Alice": PreferenceRecord(name="Alice", allow_back_to_back=True, max_back_to_back=2)}

        total, findings = check_soft_preferences(schedule, preferences, {})

        b2b = [f for f in findings if f.rule == "back_to_back"]
        self.assertEqual(len(b2b), 2)
        self.assertEqual(
            {tuple(sorted((r.class_index, r.record_index) for r in f.references)) for f in b2b},
            {((1, 0), (2, 0)), ((4, 0), (5, 0))},
        )


class LoadGlobalRulesTests(unittest.TestCase):
    def test_parses_top_level_rules_regardless_of_instructor(self):
        path = write_toml("""
[[rules]]
course = "MATH 1113"
section = "F01"
room = "Corley 269"
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
