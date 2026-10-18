# Bosch AdvancedDistance 50C

Protocol notes, reverse engineered by observation (bluetoothctl and live
measurements). Not official documentation. Driver:
[`src/bmeasurelog/meters/bosch_glm.py`](../../src/bmeasurelog/meters/bosch_glm.py).

| | |
|---|---|
| Advertised name | `AD 50C x9115` (name followed by a device-specific suffix) |
| Transport | Bluetooth Low Energy (GATT) |
| Tested by | the original author, one unit |

## GATT layout

| Item | Value |
|---|---|
| Vendor service | `0000fde8-0000-1000-8000-00805f9b34fb` (16-bit `0xFDE8`, assigned to Robert Bosch GmbH) |
| Characteristic | `02a6c0d2-0451-4000-b000-fb3210111989` (handle `0x0021`) |
| Flags | `write-without-response`, `notify` (no `read`, no `indicate`) |
| CCCD | handle `0x0023` |
| Other services | Generic Access, Generic Attribute, Device Information (standard) |

One characteristic carries everything: commands go to it with
write-without-response, and all replies and measurements come back as
notifications on it.

## Session

1. Connect, enable notifications on the characteristic.
2. Write the enable frame `C0 55 02 01 00 1A` (write-without-response).
3. Measurements and slope readings arrive as notifications when the user
   measures on the device.

It has **not** been established whether step 2 is strictly required. The
driver sends it because measurements were first observed after sending it.

## Frame format

```
C0 55 <len> | <payload: len bytes> | <crc>
```

| Field | Size | Notes |
|---|---|---|
| `C0` | 1 | Start byte |
| `55` | 1 | Constant in every observed frame; meaning unknown |
| `len` | 1 | Payload length in bytes (`0x10` for measurements) |
| payload | `len` | See below |
| `crc` | 1 | CRC-8, polynomial `0xA6`, init `0xAA`, no reflection, no final XOR, computed over every byte before it (including `C0`) |

The CRC was found by brute force (`tools/crc8_search.py`) and verified against
five captured frames of different lengths and types, including the enable
frame. Note that polynomial `0xA6` has a zero lowest bit, so the init value
only influences the first few bytes of the calculation.

### Measurement payload (16 bytes)

| Offset | Size | Type | Meaning |
|---|---|---|---|
| 0 | 2 | u16 LE | Message type (see below) |
| 2 | 2 | u16 LE | Counter, increments per reading of that type |
| 4 | 4 | float32 LE | Value |
| 8 | 8 | | Zero in all observed frames (reserved) |

| Type | Meaning | Unit of the value |
|---|---|---|
| `0x0006` | Distance | metres |
| `0x0021` | Slope (inclination) | degrees |

## Captured examples

| Frame | Decoded |
|---|---|
| `C0 55 10 06 00 08 00 E8 D9 83 40 00 00 00 00 00 00 00 00 76` | distance #8 = 4.1203 m |
| `C0 55 10 06 00 09 00 EF A7 7E 40 00 00 00 00 00 00 00 00 78` | distance #9 = 3.9790 m |
| `C0 55 10 21 00 17 00 00 D0 CC BD 00 00 00 00 00 00 00 00 30` | slope #23 = -0.1 deg (device roughly level) |
| `C0 55 10 21 00 18 00 CD CC B3 42 00 00 00 00 00 00 00 00 22` | slope #24 = 89.9 deg (device roughly vertical) |

## Other packets seen (not understood)

These do not use the `C0 55` envelope and are ignored by the driver:

- On subscribing: a 17-byte notification, `01 00 00 00 00 00 00 00 00 00 00 00 00 80 00 00 00`.
- In response to the enable frame: a 19-byte notification,
  `00 10 02 00 07 00 00 00 00 00 00 00 00 00 00 00 00 00 D8`.

## Open questions

Good first contributions for anyone with the hardware:

- What does the `55` byte mean? Is it a device or channel id?
- Which other message types exist (area, volume, indirect height, continuous
  tracking, reference edge, unit selection)? The reserved payload bytes may
  carry secondary values for those modes.
- Is the enable frame required?
- What are the two status packets above?
- Do other Bosch GLM models share this protocol? (Match on the `0xFDE8` service.)
