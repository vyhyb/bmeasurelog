# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

from bmeasurelog.readings import ReadingKind
from bmeasurelog.units import MINUS, NBSP, decimals_for, format_quantity, get_unit, round_to_step

D, S = ReadingKind.DISTANCE, ReadingKind.SLOPE


class RoundingTests(unittest.TestCase):
    def test_decimals(self):
        self.assertEqual(decimals_for(0.001), 3)
        self.assertEqual(decimals_for(0.005), 3)
        self.assertEqual(decimals_for(0.125), 3)
        self.assertEqual(decimals_for(0.0625), 4)
        self.assertEqual(decimals_for(1), 0)
        self.assertEqual(decimals_for(5), 0)
        self.assertEqual(decimals_for(10), 0)

    def test_round_to_step(self):
        self.assertAlmostEqual(round_to_step(3.97852, 0.005), 3.98)
        self.assertAlmostEqual(round_to_step(3.9724, 0.005), 3.97)
        self.assertAlmostEqual(round_to_step(3.9726, 0.005), 3.975)


class DistanceFormatTests(unittest.TestCase):
    RAW = 3.97852  # metres

    def fmt(self, unit_id, step, **kw):
        return format_quantity(self.RAW, get_unit(D, unit_id), step, **kw)

    def test_metres_full_mm(self):
        self.assertEqual(self.fmt("m", 0.001), f"3.979{NBSP}m")

    def test_metres_five_mm(self):
        self.assertEqual(self.fmt("m", 0.005), f"3.980{NBSP}m")

    def test_centimetres_five_mm(self):
        self.assertEqual(self.fmt("cm", 0.5), f"398.0{NBSP}cm")

    def test_millimetres_five_mm(self):
        self.assertEqual(self.fmt("mm", 5), f"3980{NBSP}mm")

    def test_feet_and_inches(self):
        self.assertEqual(self.fmt("ft", 0.01), f"13.05{NBSP}ft")
        self.assertEqual(self.fmt("in", 0.125), f"156.625{NBSP}in")

    def test_without_symbol(self):
        self.assertEqual(self.fmt("m", 0.005, symbol=False), "3.980")


class SlopeFormatTests(unittest.TestCase):
    def fmt(self, deg, unit_id, step, **kw):
        return format_quantity(deg, get_unit(S, unit_id), step, **kw)

    def test_degrees(self):
        self.assertEqual(self.fmt(89.9, "deg", 0.1), "89.9\u00b0")

    def test_negative_display_and_clipboard(self):
        self.assertEqual(self.fmt(-5.73, "deg", 0.1, typographic=True), f"{MINUS}5.7\u00b0")
        self.assertEqual(self.fmt(-5.73, "deg", 0.1, symbol=False), "-5.7")

    def test_no_negative_zero(self):
        self.assertEqual(self.fmt(-0.01, "deg", 0.1), "0.0\u00b0")

    def test_percent(self):
        self.assertEqual(self.fmt(45, "percent", 0.1), "100.0%")

    def test_percent_at_vertical_is_infinite(self):
        self.assertEqual(self.fmt(90, "percent", 0.1), "\u221e%")


if __name__ == "__main__":
    unittest.main()
