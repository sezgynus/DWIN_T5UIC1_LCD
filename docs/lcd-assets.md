# LCD compatibility and asset inventory

KlipperDWIN targets the **272×480 DWIN T5UIC1** display layout. A matching
icon library and English bitmap sheet must already be installed on the panel.
The installer does not flash LCD firmware or install display assets.

## Required layout

- Icon library **9** (`9.ICO`).
- English JPEG **1**, copied through cache **1**.
- Display direction **1**, giving a 272×480 coordinate space.
- A compatible `1_English.jpg` bitmap sheet as well as the icon library: some
  existing labels/buttons still use frame copies rather than font rendering.

The audited English JPEG is stored as 480×272; clockwise rotation yields the
portrait coordinate space. Its raw landscape dimensions alone do not indicate
incompatibility. A replacement icon library does not establish bitmap-sheet
compatibility. DWIN, DACAI and TJC packages are not interchangeable.

## Inventory and verification

[lcd-assets.json](lcd-assets.json) records the audited stock file SHA-256 hashes,
icon dimensions and static copy regions. The inventory covers 91 icon IDs and
50 statically specified copy regions; the regression tests check that current
source constants and copy coordinates remain compatible with that inventory.
This does not identify the exact files installed on an individual panel.

Dynamic text is sanitized/transliterated for the stock ASCII fonts. Coordinates,
string payloads and numeric fields are bounded; numeric overflow draws markers
instead of silently changing the value. UART recovery redraws the screen without
replaying printer commands.

## Print-preview images

Preview images do not require a new asset pack. Moonraker thumbnails are converted
to baseline **128×128 JPEG**, preserving aspect ratio on black. The driver uploads
JPEG bytes through command **0x31** in chunks of at most **128 bytes**, then displays
them from SRAM using **0x24**.

The cache allocator manages **32 KiB (32768 bytes)** of volatile SRAM. Images are
published only after their complete upload; entries are discarded after a panel
or backend reconnection. No flash writes or installed-icon replacement occur.
Direct JPEG display and preview caching have been exercised on the user's panel;
other kernel/asset combinations still need physical verification.

## Physical checks

Verify menu icons, bitmap labels, text bounds, colors and JPEG display on the
actual panel. Passing mocked UART packet tests validates framing and routing,
not screen-side rendering or compatibility with every panel firmware.
