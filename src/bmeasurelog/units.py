# SPDX-License-Identifier: GPL-3.0-or-later
"""Display units, rounding steps and number formatting.

Readings are stored in base units (metres, degrees). This module converts them
for display. Rounding is expressed as a *step in the display unit* (for example
5 mm = 0.005 in metres, 0.5 in centimetres, 5 in millimetres), so values like
"nearest 5 mm" work and not only whole decimals. The number of decimals shown
is derived from the step.

To add a unit, append a ``Unit`` to ``DISTANCE_UNITS`` or ``SLOPE_UNITS``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from .readings import ReadingKind

NBSP = "\u00a0"
MINUS = "\u2212"
INFINITY = "\u221e"


@dataclass(frozen=True)
class Step:
    """A rounding granularity, in the unit it belongs to."""

    value: float
    label: str  # shown in settings; equal labels across units mean equal size


@dataclass(frozen=True)
class Unit:
    id: str
    kind: ReadingKind
    name: str
    symbol: str
    convert: Callable[[float], float]  # base unit -> this unit
    steps: tuple[Step, ...]
    default_step: float
    separator: str = NBSP  # between number and symbol

    def find_step(self, value: float) -> Step | None:
        for step in self.steps:
            if math.isclose(step.value, value, rel_tol=1e-9):
                return step
        return None

    def step_by_label(self, label: str) -> Step | None:
        return next((s for s in self.steps if s.label == label), None)


def _scale(factor: float) -> Callable[[float], float]:
    return lambda value: value * factor


def _deg_to_percent(degrees: float) -> float:
    """Slope as percent grade; tan() is unbounded at +-90 degrees."""
    if math.isclose(math.cos(math.radians(degrees)), 0.0, abs_tol=1e-9):
        return math.copysign(math.inf, degrees)
    return math.tan(math.radians(degrees)) * 100.0


DISTANCE_UNITS: tuple[Unit, ...] = (
    Unit(
        "m", ReadingKind.DISTANCE, "Metres", "m", _scale(1.0),
        (Step(0.001, "1 mm"), Step(0.005, "5 mm"), Step(0.01, "1 cm"),
         Step(0.05, "5 cm"), Step(0.1, "10 cm")),
        default_step=0.001,
    ),
    Unit(
        "cm", ReadingKind.DISTANCE, "Centimetres", "cm", _scale(100.0),
        (Step(0.1, "1 mm"), Step(0.5, "5 mm"), Step(1, "1 cm"),
         Step(5, "5 cm"), Step(10, "10 cm")),
        default_step=0.1,
    ),
    Unit(
        "mm", ReadingKind.DISTANCE, "Millimetres", "mm", _scale(1000.0),
        (Step(1, "1 mm"), Step(5, "5 mm"), Step(10, "1 cm"), Step(50, "5 cm")),
        default_step=1,
    ),
    Unit(
        "in", ReadingKind.DISTANCE, "Inches", "in", _scale(1 / 0.0254),
        (Step(0.01, "0.01 in"), Step(0.1, "0.1 in"), Step(0.0625, "1/16 in"),
         Step(0.125, "1/8 in"), Step(0.25, "1/4 in"), Step(0.5, "1/2 in"),
         Step(1, "1 in")),
        default_step=0.1,
    ),
    Unit(
        "ft", ReadingKind.DISTANCE, "Feet", "ft", _scale(1 / 0.3048),
        (Step(0.001, "0.001 ft"), Step(0.01, "0.01 ft"), Step(0.1, "0.1 ft")),
        default_step=0.01,
    ),
)

SLOPE_UNITS: tuple[Unit, ...] = (
    Unit(
        "deg", ReadingKind.SLOPE, "Degrees", "\u00b0", _scale(1.0),
        (Step(0.01, "0.01\u00b0"), Step(0.1, "0.1\u00b0"), Step(0.5, "0.5\u00b0"),
         Step(1, "1\u00b0")),
        default_step=0.1, separator="",
    ),
    Unit(
        "percent", ReadingKind.SLOPE, "Percent grade", "%", _deg_to_percent,
        (Step(0.1, "0.1 %"), Step(0.5, "0.5 %"), Step(1, "1 %")),
        default_step=0.1, separator="",
    ),
)

UNITS: dict[ReadingKind, tuple[Unit, ...]] = {
    ReadingKind.DISTANCE: DISTANCE_UNITS,
    ReadingKind.SLOPE: SLOPE_UNITS,
}


def get_unit(kind: ReadingKind, unit_id: str) -> Unit:
    """Look up a unit by id; unknown ids fall back to the first unit of the kind."""
    units = UNITS[kind]
    return next((u for u in units if u.id == unit_id), units[0])


def decimals_for(step: float) -> int:
    """Decimals needed to show multiples of ``step`` exactly (0.125 -> 3, 5 -> 0)."""
    exponent = Decimal(repr(step)).normalize().as_tuple().exponent
    return max(0, -exponent)


def round_to_step(value: float, step: float) -> float:
    """Round half up to the nearest multiple of ``step``."""
    return math.floor(value / step + 0.5) * step


def format_quantity(
    value: float,
    unit: Unit,
    step: float,
    *,
    symbol: bool = True,
    typographic: bool = False,
) -> str:
    """Convert a base-unit value and format it.

    ``symbol``: append the unit symbol. ``typographic``: use a real minus sign
    (for display); leave False for text that will be pasted into other apps.
    """
    converted = unit.convert(value)
    if not math.isfinite(converted):
        text = INFINITY
        if converted < 0:
            text = (MINUS if typographic else "-") + text
    else:
        rounded = round_to_step(converted, step)
        if rounded == 0:
            rounded = 0.0  # avoid "-0.0"
        text = f"{rounded:.{decimals_for(step)}f}"
        if typographic:
            text = text.replace("-", MINUS)
    return text + unit.separator + unit.symbol if symbol else text
