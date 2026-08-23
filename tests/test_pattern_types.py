import unittest

from class_schedule.class_model import (
    CoreqClass,
    CrossListingClass,
    FourCreditClass,
    HybridClass,
    NormalClass,
    Section,
)
from class_schedule.solver.candidates import allowed_pattern_types


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


class AllowedPatternTypesTests(unittest.TestCase):
    def test_normal_class_is_standard(self):
        section = make_section()
        item = NormalClass((section,))
        self.assertEqual(allowed_pattern_types(item, section), frozenset({"standard"}))

    def test_hybrid_class_is_standard(self):
        left = make_section(section="M01", room="101")
        right = make_section(
            section="M01", time_slot="TBA", duration=None, room=""
        )
        item = HybridClass((left, right))
        self.assertEqual(allowed_pattern_types(item, left), frozenset({"standard"}))
        self.assertEqual(allowed_pattern_types(item, right), frozenset({"standard"}))

    def test_cross_listing_honors_pair_is_standard(self):
        left = make_section(section="001", instructor="Alice", room="101")
        right = make_section(section="H01", instructor="Alice", room="101")
        item = CrossListingClass((left, right))
        self.assertEqual(allowed_pattern_types(item, left), frozenset({"standard"}))

    def test_four_credit_mwf_row_is_standard(self):
        mwf = make_section(time_slot="MWF 9:00am", duration=50)
        tr_half = make_section(time_slot="T 9:00am", duration=80)
        item = FourCreditClass((mwf, tr_half))
        self.assertEqual(allowed_pattern_types(item, mwf), frozenset({"standard"}))

    def test_four_credit_partial_row_is_four_credit_partial(self):
        mwf = make_section(time_slot="MWF 9:00am", duration=50)
        t_half = make_section(time_slot="T 9:00am", duration=80)
        item = FourCreditClass((mwf, t_half))
        self.assertEqual(
            allowed_pattern_types(item, t_half), frozenset({"four_credit_partial"})
        )

        r_half = make_section(time_slot="R 9:00am", duration=80)
        item2 = FourCreditClass((mwf, r_half))
        self.assertEqual(
            allowed_pattern_types(item2, r_half), frozenset({"four_credit_partial"})
        )

    def test_coreq_three_credit_pairs_are_standard(self):
        left = make_section(
            subject="MATH", number="1113", section="001",
            time_slot="MWF 9:00am", duration=50, room="101",
        )
        right = make_section(
            subject="MATH", number="0903", section="001",
            time_slot="MWF 9:50am", duration=50, room="101",
        )
        item = CoreqClass((left, right))
        self.assertEqual(allowed_pattern_types(item, left), frozenset({"standard"}))
        self.assertEqual(allowed_pattern_types(item, right), frozenset({"standard"}))

        left2 = make_section(
            subject="MATH", number="1003", section="001",
            time_slot="MWF 9:00am", duration=50, room="101",
        )
        right2 = make_section(
            subject="MATH", number="0803", section="001",
            time_slot="MWF 9:50am", duration=50, room="101",
        )
        item2 = CoreqClass((left2, right2))
        self.assertEqual(allowed_pattern_types(item2, left2), frozenset({"standard"}))

    def test_coreq_1113_1110_pair_is_coreq_short(self):
        left = make_section(
            subject="MATH", number="1113", section="001",
            time_slot="MWF 9:00am", duration=50, room="101",
        )
        right = make_section(
            subject="MATH", number="1110", section="001",
            time_slot="MW 9:50am", duration=50, room="101",
        )
        item = CoreqClass((left, right))
        self.assertEqual(allowed_pattern_types(item, left), frozenset({"coreq_short"}))
        self.assertEqual(allowed_pattern_types(item, right), frozenset({"coreq_short"}))


if __name__ == "__main__":
    unittest.main()
