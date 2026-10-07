# KlipperDWIN custom LCD atlases

Place the two generated T5UIC1 JPEG atlas files in this directory with these
exact names:

- `klipperdwin_atlas_0.jpg` — current custom static icons
- `klipperdwin_atlas_1.jpg` — empty/reserved second atlas

Both files are physical-panel **480x272 baseline JPEGs**. The panel runs
`direction=1`, so `lcd_atlas.py` source rectangles are expressed in the
runtime **272x480** virtual-area coordinate system.

Current Atlas 0 layout:

| Icon ID | Symbol | Virtual area | x | y | w | h |
|---:|---|---:|---:|---:|---:|---:|
| `0x0100` | MMU home, normal | 0 | 0 | 0 | 77 | 47 |
| `0x0101` | MMU home, selected | 0 | 80 | 0 | 77 | 47 |
| `0x0102` | Folder | 0 | 160 | 0 | 20 | 18 |
| `0x0103` | MCU (`ICON_MCU`) | 0 | 192 | 0 | 20 | 20 |

The MCU chip icon uses blue/cyan shading on black to match the stock `9.ICO`
section icons. Info draws it beside every MCU section heading at `(8, y - 2)`
through `draw_atlas_icon(ICON_MCU, ...)`, including the unavailable-MCU heading.
Its atlas rectangle is in portrait coordinates; the JPEG remains 480x272.

Atlas 1 currently contains no icons and is reserved for future expansion.

The runtime driver stores Atlas 0 in Picture Flash ID 14 and Atlas 1 in Picture
Flash ID 15. Each JPEG must fit inside the T5UIC1 32 KiB SRAM transfer limit.
