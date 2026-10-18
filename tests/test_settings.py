# SPDX-License-Identifier: GPL-3.0-or-later
import json
import tempfile
import unittest
from pathlib import Path

from bmeasurelog.readings import Reading, ReadingKind
from bmeasurelog.settings import Settings
from bmeasurelog.units import NBSP


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "sub" / "settings.json"

    def test_defaults(self):
        s = Settings(self.path)
        self.assertEqual(s.format(Reading(ReadingKind.DISTANCE, 3.97852)), f"3.979{NBSP}m")
        self.assertTrue(s.options.auto_copy)

    def test_persists_and_reloads(self):
        s = Settings(self.path)
        s.update(distance_unit="cm", copy_with_unit=True)
        again = Settings(self.path)
        self.assertEqual(again.options.distance_unit, "cm")
        self.assertTrue(again.options.copy_with_unit)

    def test_unit_change_keeps_physical_rounding(self):
        s = Settings(self.path)
        s.update(distance_step=0.005)  # 5 mm in metres
        s.update(distance_unit="cm")
        self.assertEqual(s.options.distance_step, 0.5)  # still 5 mm
        s.update(distance_unit="mm")
        self.assertEqual(s.options.distance_step, 5)

    def test_unit_change_without_equivalent_uses_default(self):
        s = Settings(self.path)
        s.update(distance_unit="in")
        self.assertEqual(s.options.distance_step, 0.1)

    def test_invalid_values_are_repaired(self):
        s = Settings(self.path)
        s.update(distance_unit="parsec", slope_step=123.0)
        self.assertEqual(s.options.distance_unit, "m")
        self.assertEqual(s.options.slope_step, 0.1)

    def test_corrupt_file_ignored(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json")
        self.assertEqual(Settings(self.path).options.distance_unit, "m")

    def test_wrong_types_ignored(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"auto_copy": "yes", "distance_unit": 7}))
        s = Settings(self.path)
        self.assertTrue(s.options.auto_copy)
        self.assertEqual(s.options.distance_unit, "m")

    def test_listeners_notified_only_on_change(self):
        s = Settings(self.path)
        calls = []
        s.connect(lambda: calls.append(1))
        s.update(auto_copy=True)  # unchanged
        s.update(auto_copy=False)
        self.assertEqual(len(calls), 1)

    def test_unknown_key_raises(self):
        with self.assertRaises(AttributeError):
            Settings(self.path).update(nope=1)

    def test_clipboard_text(self):
        s = Settings(self.path)
        slope = Reading(ReadingKind.SLOPE, -5.73)
        self.assertEqual(s.clipboard_text(slope), "-5.7")
        s.update(copy_with_unit=True)
        self.assertEqual(s.clipboard_text(slope), "-5.7\u00b0")
        self.assertEqual(s.format(slope), "\u22125.7\u00b0")


if __name__ == "__main__":
    unittest.main()
