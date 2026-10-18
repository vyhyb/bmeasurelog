# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

from bmeasurelog.meters import PROFILES
from bmeasurelog.meters.bosch_glm import (
    ENABLE_FRAME,
    BoschAdvancedDistance50C,
    BoschDecoder,
    crc8,
    encode_frame,
    parse_frame,
)
from bmeasurelog.readings import ReadingKind

# Real frames captured from an AdvancedDistance 50C.
DIST_A = bytes.fromhex("c0 55 10 06 00 08 00 e8 d9 83 40 00 00 00 00 00 00 00 00 76")
DIST_B = bytes.fromhex("c0 55 10 06 00 09 00 ef a7 7e 40 00 00 00 00 00 00 00 00 78")
SLOPE_A = bytes.fromhex("c0 55 10 21 00 17 00 00 d0 cc bd 00 00 00 00 00 00 00 00 30")
SLOPE_B = bytes.fromhex("c0 55 10 21 00 18 00 cd cc b3 42 00 00 00 00 00 00 00 00 22")
STATUS = bytes.fromhex("00 10 02 00 07 00 00 00 00 00 00 00 00 00 00 00 00 00 d8")


class CrcTests(unittest.TestCase):
    def test_all_captured_frames_have_valid_crc(self):
        for frame in (ENABLE_FRAME, DIST_A, DIST_B, SLOPE_A, SLOPE_B):
            self.assertEqual(crc8(frame[:-1]), frame[-1], frame.hex(" "))

    def test_enable_frame_matches_capture(self):
        self.assertEqual(ENABLE_FRAME, bytes.fromhex("c0 55 02 01 00 1a"))

    def test_encode_roundtrip_layout(self):
        frame = encode_frame(b"\x01\x02\x03")
        self.assertEqual(frame[:3], bytes([0xC0, 0x55, 3]))
        self.assertEqual(frame[3:6], b"\x01\x02\x03")
        self.assertEqual(crc8(frame[:-1]), frame[-1])


class ParseTests(unittest.TestCase):
    def test_distance(self):
        frame = parse_frame(DIST_A)
        self.assertEqual((frame.msg_type, frame.counter), (0x0006, 8))
        self.assertAlmostEqual(frame.value, 4.12035, places=4)

    def test_slope(self):
        frame = parse_frame(SLOPE_B)
        self.assertEqual((frame.msg_type, frame.counter), (0x0021, 24))
        self.assertAlmostEqual(frame.value, 89.9, places=3)

    def test_rejects_bad_crc(self):
        self.assertIsNone(parse_frame(DIST_A[:-1] + b"\x00"))

    def test_rejects_wrong_length_and_garbage(self):
        self.assertIsNone(parse_frame(DIST_A[:-1]))
        self.assertIsNone(parse_frame(STATUS))
        self.assertIsNone(parse_frame(b""))


class DecoderTests(unittest.TestCase):
    def test_distance_and_slope_kinds(self):
        d = BoschDecoder()
        (dist,) = d.feed(DIST_B)
        (slope,) = d.feed(SLOPE_A)
        self.assertEqual(dist.kind, ReadingKind.DISTANCE)
        self.assertAlmostEqual(dist.value, 3.979, places=3)
        self.assertEqual(slope.kind, ReadingKind.SLOPE)
        self.assertAlmostEqual(slope.value, -0.1, places=3)

    def test_duplicates_dropped_per_type(self):
        d = BoschDecoder()
        self.assertEqual(len(d.feed(DIST_A)), 1)
        self.assertEqual(d.feed(DIST_A), [])
        self.assertEqual(len(d.feed(DIST_B)), 1)

    def test_status_and_corrupt_ignored(self):
        d = BoschDecoder()
        self.assertEqual(d.feed(STATUS), [])
        self.assertEqual(d.feed(DIST_A[:-1] + b"\x00"), [])

    def test_unknown_message_type_ignored(self):
        payload = bytes.fromhex("99 00 01 00") + DIST_A[7:11] + bytes(8)
        self.assertEqual(BoschDecoder().feed(encode_frame(payload)), [])


class ProfileTests(unittest.TestCase):
    def test_matching(self):
        p = BoschAdvancedDistance50C()
        self.assertTrue(p.matches("AD 50C x9115", []))
        self.assertTrue(p.matches(None, ["0000FDE8-0000-1000-8000-00805f9b34fb"]))
        self.assertFalse(p.matches("Some Headphones", ["0000180f-0000-1000-8000-00805f9b34fb"]))

    def test_registered(self):
        self.assertTrue(any(isinstance(p, BoschAdvancedDistance50C) for p in PROFILES))

    def test_registry_ids_unique(self):
        ids = [p.id for p in PROFILES]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
