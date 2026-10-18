#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Brute-force the CRC-8 parameters of a meter's frames.

Usage:
    python3 tools/crc8_search.py "c0 55 02 01 00 1a" "c0 55 10 06 00 08 ..." ...

Give it complete frames (including the trailing checksum byte), ideally 4 or
more with different contents and lengths. With only 1-2 frames many false
matches are expected. It tries every polynomial, init value, with and without
reflection, with and without final XOR 0xFF, and every start offset 0-3.

Note: for polynomials whose lowest bit is 0 (such as Bosch's 0xA6) the init
value stops mattering after a few bytes, so several inits may be reported.
Any listed combination that matches *all* frames is equivalent for those frames.
"""

import sys


def make_table(poly: int, reflected: bool) -> list[int]:
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            if reflected:
                c = (c >> 1) ^ poly if c & 1 else c >> 1
            else:
                c = ((c << 1) ^ poly) & 0xFF if c & 0x80 else (c << 1) & 0xFF
        table.append(c)
    return table


def search(frames: list[bytes]):
    for reflected in (False, True):
        for poly in range(1, 256):
            table = make_table(poly, reflected)
            for start in range(4):
                for init in range(256):
                    for xor_out in (0x00, 0xFF):
                        for frame in frames:
                            crc = init
                            for byte in frame[start:-1]:
                                crc = table[crc ^ byte]
                            if (crc ^ xor_out) != frame[-1]:
                                break
                        else:
                            yield reflected, poly, init, xor_out, start


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    frames = [bytes.fromhex(arg) for arg in sys.argv[1:]]
    hits = list(search(frames))
    if not hits:
        print("No match. Check the frames, or the checksum may not be a plain CRC-8.")
        return 1
    for reflected, poly, init, xor_out, start in hits:
        print(
            f"poly=0x{poly:02X} init=0x{init:02X} xorout=0x{xor_out:02X} "
            f"reflected={reflected} covers bytes[{start}:-1]"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
