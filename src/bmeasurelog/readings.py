# SPDX-License-Identifier: GPL-3.0-or-later
"""Data types shared by meter drivers and the UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ReadingKind(str, Enum):
    """What a reading measures. Add members here to support new quantities."""

    DISTANCE = "distance"
    SLOPE = "slope"

    @property
    def label(self) -> str:
        return self.value.capitalize()


@dataclass(frozen=True)
class Reading:
    """One measurement, always stored in SI-style base units.

    ``value`` is in **metres** for DISTANCE and **degrees** for SLOPE.
    Unit conversion and rounding happen only when displaying (see ``units``).
    """

    kind: ReadingKind
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
