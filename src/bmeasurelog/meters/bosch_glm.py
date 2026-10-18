# SPDX-License-Identifier: GPL-3.0-or-later
"""Bosch AdvancedDistance 50C ("AD 50C") driver.

Protocol reverse engineered from observation; see
``docs/protocols/bosch-advanced-distance-50c.md`` for the full write-up.

Frame layout (all frames on one GATT characteristic)::

    C0 55 <len> | <payload: len bytes> | <crc8>

    payload = <type u16 LE> <counter u16 LE> <float32 LE> <reserved...>

    crc8: polynomial 0xA6, init 0xAA, over every byte before the CRC.

Message types seen so far: 0x0006 distance (metres), 0x0021 slope (degrees).
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import Sequence

from ..readings import Reading, ReadingKind
from .base import Decoder, MeterProfile

log = logging.getLogger(__name__)

SERVICE_UUID = "0000fde8-0000-1000-8000-00805f9b34fb"  # 16-bit 0xFDE8, Robert Bosch GmbH
CHARACTERISTIC_UUID = "02a6c0d2-0451-4000-b000-fb3210111989"
NAME_PREFIX = "AD 50C"

START_BYTE = 0xC0
DEVICE_BYTE = 0x55  # constant in every observed frame; meaning unknown
CRC_POLY = 0xA6
CRC_INIT = 0xAA

MSG_DISTANCE = 0x0006
MSG_SLOPE = 0x0021
_KIND_BY_TYPE = {
    MSG_DISTANCE: ReadingKind.DISTANCE,
    MSG_SLOPE: ReadingKind.SLOPE,
}

_MIN_PAYLOAD = 8  # type (2) + counter (2) + float32 (4)


def crc8(data: bytes) -> int:
    """CRC-8, poly 0xA6, init 0xAA, no reflection, no final XOR."""
    crc = CRC_INIT
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ CRC_POLY) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def encode_frame(payload: bytes) -> bytes:
    """Wrap a payload in the C0 55 <len> ... <crc> envelope."""
    body = bytes([START_BYTE, DEVICE_BYTE, len(payload)]) + payload
    return body + bytes([crc8(body)])


#: Written to the characteristic after subscribing. Measurements arrived after
#: this was sent; whether it is strictly required has not been established.
ENABLE_FRAME = encode_frame(b"\x01\x00")  # == C0 55 02 01 00 1A


@dataclass(frozen=True)
class Frame:
    msg_type: int
    counter: int
    value: float


def parse_frame(data: bytes) -> Frame | None:
    """Parse and validate one measurement frame; ``None`` if it isn't one."""
    if len(data) < 4 + _MIN_PAYLOAD:
        return None
    if data[0] != START_BYTE or data[1] != DEVICE_BYTE:
        return None
    if len(data) != 4 + data[2]:
        return None
    if crc8(data[:-1]) != data[-1]:
        log.debug("CRC mismatch: %s", data.hex(" "))
        return None
    msg_type, counter, value = struct.unpack_from("<HHf", data, 3)
    return Frame(msg_type, counter, value)


class BoschDecoder(Decoder):
    def __init__(self) -> None:
        self._last_counter: dict[int, int] = {}

    def feed(self, data: bytes) -> list[Reading]:
        frame = parse_frame(data)
        if frame is None:
            return []
        kind = _KIND_BY_TYPE.get(frame.msg_type)
        if kind is None:
            log.debug("Unknown message type 0x%04x", frame.msg_type)
            return []
        if self._last_counter.get(frame.msg_type) == frame.counter:
            return []  # duplicate notification
        self._last_counter[frame.msg_type] = frame.counter
        if frame.value != frame.value or abs(frame.value) == float("inf"):
            return []  # NaN / infinity
        if kind is ReadingKind.DISTANCE and frame.value < 0:
            return []
        return [Reading(kind, frame.value)]


class BoschAdvancedDistance50C(MeterProfile):
    id = "bosch-advanced-distance-50c"
    name = "Bosch AdvancedDistance 50C"
    notify_uuid = CHARACTERISTIC_UUID
    write_with_response = False  # GATT flags: write-without-response, notify

    def matches(self, local_name: str | None, service_uuids: Sequence[str]) -> bool:
        if (local_name or "").startswith(NAME_PREFIX):
            return True
        return SERVICE_UUID in (u.lower() for u in service_uuids)

    def handshake(self) -> list[bytes]:
        return [ENABLE_FRAME]

    def new_decoder(self) -> Decoder:
        return BoschDecoder()
