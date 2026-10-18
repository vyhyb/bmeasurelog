# <Manufacturer Model>

Copy this file to `docs/protocols/<manufacturer>-<model>.md` and fill it in
while you reverse engineer your meter. Delete sections that don't apply. Mark
anything you have not verified as **unconfirmed**.

| | |
|---|---|
| Advertised name | |
| Firmware / hardware revision | (read from the Device Information service) |
| Transport | BLE (GATT) / other |
| Tested by | |

## GATT layout

| Item | Value |
|---|---|
| Vendor service UUID | |
| Characteristic UUID(s) | |
| Flags (`attribute-info`) | |
| Which characteristic is for commands / measurements | |

## Session

1. (Connect, subscribe, which bytes to write, in which order.)

## Frame format

(Start byte, length, payload fields, checksum algorithm and how you found it.)

## Captured examples

| Frame (hex) | What you did on the device | Decoded |
|---|---|---|
| | e.g. measured 1.000 m on a tape | |

## Other packets seen (not understood)

## Open questions
