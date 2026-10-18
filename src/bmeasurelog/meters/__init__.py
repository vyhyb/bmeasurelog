# SPDX-License-Identifier: GPL-3.0-or-later
"""Registry of supported meters.

To add a meter: write a ``MeterProfile`` + ``Decoder`` in a new module here
(see README, "Adding a new distance meter") and add an instance below.
This module must stay free of Bluetooth/GTK imports so profiles remain testable.
"""

from .base import ConnectionState, Decoder, MeterProfile
from .bosch_glm import BoschAdvancedDistance50C

PROFILES: tuple[MeterProfile, ...] = (
    BoschAdvancedDistance50C(),
    # YourMeter(),
)

__all__ = ["PROFILES", "ConnectionState", "Decoder", "MeterProfile"]
