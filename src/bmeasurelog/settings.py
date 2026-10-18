# SPDX-License-Identifier: GPL-3.0-or-later
"""User settings: validated, persisted as JSON, observable.

Stored at ``$XDG_CONFIG_HOME/bmeasurelog/settings.json`` (``~/.config/...`` by
default). Free of GTK imports so it can be unit-tested.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Callable

from .readings import Reading, ReadingKind
from .units import Unit, format_quantity, get_unit

log = logging.getLogger(__name__)


@dataclass
class Options:
    distance_unit: str = "m"
    distance_step: float = 0.001  # in the distance unit
    slope_unit: str = "deg"
    slope_step: float = 0.1  # in the slope unit
    auto_copy: bool = True
    copy_with_unit: bool = False


def default_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "bmeasurelog" / "settings.json"


class Settings:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_path()
        self.options = Options()
        self._listeners: list[Callable[[], None]] = []
        self._load()

    # ---------------------------------------------------------- observers
    def connect(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def disconnect(self, callback: Callable[[], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    # ------------------------------------------------------------ queries
    def unit_for(self, kind: ReadingKind) -> Unit:
        return get_unit(kind, getattr(self.options, f"{kind.value}_unit"))

    def step_for(self, kind: ReadingKind) -> float:
        return getattr(self.options, f"{kind.value}_step")

    def format(self, reading: Reading, *, symbol: bool = True, typographic: bool = True) -> str:
        return format_quantity(
            reading.value,
            self.unit_for(reading.kind),
            self.step_for(reading.kind),
            symbol=symbol,
            typographic=typographic,
        )

    def clipboard_text(self, reading: Reading) -> str:
        """Text to copy: ASCII minus, unit symbol only if the user wants it."""
        return self.format(reading, symbol=self.options.copy_with_unit, typographic=False)

    # ------------------------------------------------------------ changes
    def update(self, **changes) -> bool:
        """Apply changes, persist, and notify listeners. Returns True if anything changed.

        Changing a unit without also giving a step keeps the same physical
        rounding when the new unit offers it (5 mm stays 5 mm from m to cm).
        """
        old = self.options
        new = replace(old)
        for key, value in changes.items():
            if not hasattr(new, key):
                raise AttributeError(f"Unknown setting: {key}")
            setattr(new, key, value)

        for kind in ReadingKind:
            unit_key, step_key = f"{kind.value}_unit", f"{kind.value}_step"
            if unit_key in changes and step_key not in changes:
                old_step = get_unit(kind, getattr(old, unit_key)).find_step(getattr(old, step_key))
                new_unit = get_unit(kind, getattr(new, unit_key))
                carried = new_unit.step_by_label(old_step.label) if old_step else None
                setattr(new, step_key, carried.value if carried else new_unit.default_step)

        self._sanitize(new)
        if new == old:
            return False
        self.options = new
        self._save()
        for callback in list(self._listeners):
            callback()
        return True

    # -------------------------------------------------------- persistence
    @staticmethod
    def _sanitize(options: Options) -> None:
        for kind in ReadingKind:
            unit = get_unit(kind, getattr(options, f"{kind.value}_unit"))
            setattr(options, f"{kind.value}_unit", unit.id)
            step = unit.find_step(getattr(options, f"{kind.value}_step"))
            setattr(options, f"{kind.value}_step", step.value if step else unit.default_step)

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            log.warning("Ignoring unreadable settings %s: %s", self.path, exc)
            return
        if not isinstance(data, dict):
            return
        defaults = Options()
        for field in fields(Options):
            if field.name not in data:
                continue
            value, expected = data[field.name], type(getattr(defaults, field.name))
            if expected is float and isinstance(value, int) and not isinstance(value, bool):
                value = float(value)
            if isinstance(value, expected):
                setattr(self.options, field.name, value)
        self._sanitize(self.options)

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(asdict(self.options), indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            log.warning("Could not save settings to %s: %s", self.path, exc)
