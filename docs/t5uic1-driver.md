# T5UIC1 driver reference

KlipperDWIN uses `t5uic1_driver.py` as the hardware/protocol abstraction for the
DWIN T5UIC1 serial-command display used by the Ender 3 V2 panel.

The driver follows the T5UIC1 v2.3 instruction set. The UI layer must not build
raw UART packets or depend on opcode layout; it calls the driver API instead.
The existing UI rendering policy is intentionally preserved during this driver
migration. New hardware-assisted rendering features can be adopted separately
after physical-panel validation.

## Wire format

Normal commands use:

```text
AA CMD DATA... CC 33 C3 3C
```

The command/data field is bounded before transmission. Multi-byte integer fields
are encoded big-endian. The stock KlipperDWIN panel configuration uses the
non-CRC frame format. Inbound `0xFF` CRC-error reports are still parsed so a
panel configured with CRC checking can expose that condition.

## Instruction coverage

| Opcode | T5UIC1 function | Driver API |
|---:|---|---|
| `0x00` | Handshake | `handshake()` |
| `0x01` | Clear screen | `clear()` |
| `0x02` | Point / point list | `draw_point()`, `draw_points()` |
| `0x03` | Line / polyline | `draw_line()`, `draw_polyline()` |
| `0x05` | Rectangle / fill / XOR | `draw_rectangle()` |
| `0x08` | Two-color bitmap fill | `draw_bitmap()` |
| `0x09` | Move display area | `move_area()` |
| `0x11` | Text | `draw_text()`, `draw_text_bytes()` |
| `0x14` | Native numeric variable | `draw_number()` |
| `0x21` | QR code | `draw_qr()` |
| `0x22` | Show JPEG / cache to area 0 | `show_jpeg()` |
| `0x23` | Icon library | `show_icon()` |
| `0x24` | JPEG icon from SRAM | `show_sram_jpeg()` |
| `0x25` | JPEG to virtual area 1 | `cache_jpeg()` |
| `0x26` | Copy virtual area 1 | `copy_cache1()` |
| `0x27` | Copy virtual area 0/1 | `copy_cache()` |
| `0x28` | Configure icon animation | `configure_animation()` |
| `0x29` | Animation enable mask | `set_animation_mask()` |
| `0x2A` | EAN-13 barcode | `draw_ean13()` |
| `0x30` | Backlight | `set_backlight()` |
| `0x31` | SRAM/Data Flash write | `write_memory()`, `write_sram()`, `write_flash()` |
| `0x32` | SRAM/Data Flash read | `read_memory()`, `read_sram()`, `read_flash()` |
| `0x33` | SRAM to picture Flash | `store_sram_as_picture()` |
| `0x34` | Display orientation | `set_orientation()` |
| `0x38` | Extended UART baud rate | `set_aux_baud_divisor()`, `set_aux_baudrate()` |
| `0x39` | Extended UART transmit | `aux_write()` |
| `0x3A` | Extended UART receive upload | `poll_aux_data()` |
| `0xFF` | CRC error report (inbound) | `poll_crc_error()` |

KlipperDWIN also retains the proven `0x3D` display-update command through
`update()` for compatibility with the Creality/mriscoc T5UIC1 implementation.

## Memory

The driver exposes the two T5UIC1 data-memory regions independently:

| Region | Selector | Size | Persistence |
|---|---:|---:|---|
| SRAM | `0x5A` | 32 KiB | Volatile |
| Data Flash | `0xA5` | 16 KiB | Non-volatile |

`read_memory()` automatically chunks reads to the protocol's `0xF0` byte
maximum. Writes are chunked into bounded UART packets. Flash writes wait for the
panel acknowledgement instead of assuming completion.

Picture Flash is separate from the 16 KiB Data Flash. `store_sram_as_picture()`
uses opcode `0x33` to copy the panel's 32 KiB SRAM image data into picture slot
`0x00..0x0F`.

## Rendering compatibility

The phase-1 driver migration deliberately does **not** change the current UI
render strategy. Compatibility helpers such as `draw_integer_text()`,
`draw_scaled_float_text()` and `draw_signed_scaled_float_text()` continue to
render the same `0x11` text packets used before the migration.

The native `0x14` implementation is available separately as `draw_number()`.
It supports the normal font selectors and the T5UIC1 special numeric selectors
`0x0A..0x0F`. Switching existing UI fields to native numeric rendering belongs
to the later physical-panel optimization phase.

Likewise, hardware animation, QR/EAN-13, virtual-area operations, persistent Data
Flash, picture Flash and the extended UART are exposed by the driver without
changing current UI behavior.

## Validation boundary

Automated tests validate packet bytes, payload/address bounds, response parsing,
partial UART reads, acknowledgements, retries and compatibility rendering. They
cannot prove rendering behavior on every T5UIC1 kernel revision. New rendering
paths should be enabled in the UI only after physical-panel validation.
