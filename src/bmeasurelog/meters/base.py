# SPDX-License-Identifier: GPL-3.0-or-later
"""The interface every distance meter implements.

A meter driver is two small, I/O-free classes:

* ``MeterProfile``: static facts about the device (how to recognise it, which
  GATT characteristic to use, which bytes to send after connecting).
* ``Decoder``: turns raw notification bytes into ``Reading`` objects.

Neither touches Bluetooth or GTK, so both are trivially unit-testable with
captured frames. The generic BLE transport lives in ``ble.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import ClassVar, Sequence

from ..readings import Reading


class ConnectionState(Enum):
    SEARCHING = "searching"
    CONNECTED = "connected"
    LOST = "lost"


class Decoder(ABC):
    """Stateful per-connection decoder. A new instance is created per session."""

    @abstractmethod
    def feed(self, data: bytes) -> list[Reading]:
        """Process one notification payload.

        Return the readings it contains (usually zero or one). Return an empty
        list for status/ack packets, corrupt frames and duplicates. Never raise
        on malformed input.
        """


class MeterProfile(ABC):
    """Static description of one meter model (or family)."""

    #: Stable machine-readable id, e.g. "bosch-advanced-distance-50c".
    id: ClassVar[str]
    #: Human-readable name shown in the window title.
    name: ClassVar[str]
    #: GATT characteristic that sends measurements (notify/indicate).
    notify_uuid: ClassVar[str]
    #: Characteristic for commands; defaults to ``notify_uuid``.
    write_uuid: ClassVar[str | None] = None
    #: True if commands need a write *with* response (GATT flag ``write``),
    #: False for ``write-without-response``.
    write_with_response: ClassVar[bool] = False

    @property
    def command_uuid(self) -> str:
        return self.write_uuid or self.notify_uuid

    @abstractmethod
    def matches(self, local_name: str | None, service_uuids: Sequence[str]) -> bool:
        """Return True if an advertisement belongs to this meter model."""

    def handshake(self) -> list[bytes]:
        """Frames to write, in order, right after subscribing to notifications."""
        return []

    @abstractmethod
    def new_decoder(self) -> Decoder:
        """Create a fresh decoder for a new connection."""
