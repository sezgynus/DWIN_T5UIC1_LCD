"""Host-side custom icon-atlas manifest for KlipperDWIN.

The UI must not depend on atlas coordinates or virtual-area selection. Add or
move custom static icons only by updating ICON_COORDINATES and the corresponding
JPEG file. Stock icons already present in 9.ICO do not belong here.

T5UIC1 JPEG files are stored at the physical 480x272 panel resolution, while
source rectangles below use the runtime portrait virtual-area coordinate space
(272x480) after direction=1 is applied.
"""

# virtual_area: (repo-relative JPEG path, reserved Picture Flash ID)
ATLAS_FILES = {
    0: ("assets/klipperdwin_atlas_0.jpg", 14),
    1: ("assets/klipperdwin_atlas_1.jpg", 15),
}

# icon_id: (virtual_area, source_x, source_y, width, height)
#
# The table is intentionally empty until the production atlas artwork is
# finalized. Populating it activates automatic atlas synchronization.
ICON_COORDINATES = {}
