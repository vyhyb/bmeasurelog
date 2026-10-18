# SPDX-License-Identifier: GPL-3.0-or-later
"""Generic BLE transport shared by every meter profile.

Runs an asyncio loop in a background thread: scan for any registered meter,
connect, subscribe, send the profile's handshake, decode notifications, and
reconnect forever. Callbacks are invoked **on the BLE thread**; the UI is
responsible for hopping to its own main loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable, Sequence

from bleak import BleakClient, BleakScanner

from ..readings import Reading
from .base import ConnectionState, MeterProfile

log = logging.getLogger(__name__)

StateCallback = Callable[[ConnectionState, "str | None"], None]
ReadingCallback = Callable[[Reading], None]


class BleConnection(threading.Thread):
    SCAN_TIMEOUT = 8.0  # seconds per scan attempt
    RETRY_DELAY = 2.0  # seconds between sessions

    def __init__(
        self,
        profiles: Sequence[MeterProfile],
        on_state: StateCallback,
        on_reading: ReadingCallback,
    ) -> None:
        super().__init__(daemon=True, name="ble")
        self._profiles = profiles
        self._on_state = on_state
        self._on_reading = on_reading
        self._found: dict[str, MeterProfile] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self._wake = asyncio.Event()

    # -- thread-safe controls (call from any thread)
    def reconnect(self) -> None:
        """Skip the retry delay and scan again now."""
        if self._loop:
            self._loop.call_soon_threadsafe(self._wake.set)

    def stop(self) -> None:
        """Disconnect cleanly and end the thread."""
        if self._loop and self._task:
            self._loop.call_soon_threadsafe(self._task.cancel)
            self.join(timeout=3)

    # -- BLE thread
    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._task = self._loop.create_task(self._main())
        try:
            self._loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            pass
        finally:
            self._loop.close()

    def _match(self, device, adv) -> bool:
        name = adv.local_name or device.name
        for profile in self._profiles:
            if profile.matches(name, adv.service_uuids or []):
                self._found[device.address] = profile
                return True
        return False

    async def _main(self) -> None:
        while True:
            self._wake.clear()
            self._on_state(ConnectionState.SEARCHING, None)
            try:
                device = await BleakScanner.find_device_by_filter(
                    self._match, timeout=self.SCAN_TIMEOUT
                )
                if device:
                    await self._session(device, self._found[device.address])
                    self._on_state(ConnectionState.LOST, None)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # BlueZ errors, adapter off, ...
                log.warning("BLE error: %r", exc, exc_info=log.isEnabledFor(logging.DEBUG))
                self._on_state(ConnectionState.LOST, None)
            try:
                await asyncio.wait_for(self._wake.wait(), self.RETRY_DELAY)
            except asyncio.TimeoutError:
                pass

    async def _session(self, device, profile: MeterProfile) -> None:
        loop = asyncio.get_running_loop()
        gone = asyncio.Event()
        decoder = profile.new_decoder()

        def on_notify(_char, data: bytearray) -> None:
            log.debug("rx %s", bytes(data).hex(" "))
            try:
                for reading in decoder.feed(bytes(data)):
                    self._on_reading(reading)
            except Exception:
                log.exception("Decoder failed on %s", bytes(data).hex(" "))

        async with BleakClient(
            device,
            disconnected_callback=lambda _c: loop.call_soon_threadsafe(gone.set),
        ) as client:
            await client.start_notify(profile.notify_uuid, on_notify)
            for frame in profile.handshake():
                log.debug("tx %s", frame.hex(" "))
                await client.write_gatt_char(
                    profile.command_uuid, frame, response=profile.write_with_response
                )
            self._on_state(ConnectionState.CONNECTED, profile.name)
            await gone.wait()
