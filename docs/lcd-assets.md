# LCD asset verification

Reference: [mriscoc 05903a80](https://github.com/mriscoc/Ender3V2S1/tree/05903a80d6e15cc91b0bc690b35e08fd440a21e9),
`display assets/stock/DWIN_SET`, `common/dwin_set.h` and ProUI `dwinui.cpp`.

- Python selects library 9 (`9.ICO`), English JPG 1 and cache 1.
- All 91 Python icon IDs have nonempty, in-bounds directory entries in stock
  `9.ICO`. Named IDs match the common header; `ICON_StockConfiguraton` is the
  Python spelling of reference `ICON_StockConfiguration` (58).
- The JPEG is stored as 480 × 272. Rotating it clockwise for direction 1 gives
  the 272 × 480 coordinate space used by the UI. It must not be rejected merely
  because its raw dimensions are landscape.
- All 50 statically specified copy regions are ordered and within that space.
  Visual inspection of the rotated stock English sheet confirms the upper menu
  label sheet and lower button sheet. Dynamic destinations remain UI-controlled.
- The checked metadata, icon sizes, region inventory and stock file SHA-256
  hashes are recorded in `lcd-assets.json`; firmware images are not bundled.

ProUI primarily draws labels as text. This Python UI still uses the stock English
bitmap label sheet, so a compatible 1_English.jpg is required in addition to the
icon library. A custom ProUI icon set alone does not establish bitmap compatibility.
DWIN_SET files apply to DWIN panels; DACAI/private and TJC packages are separate.

This verifies the repository reference assets, not the files actually installed
on a connected LCD. The installed historical asset/kernel version is unknown.
No LCD flashing was performed or is required by this change. Physical appearance,
transparent filtering and installed asset equivalence remain hardware checks.
