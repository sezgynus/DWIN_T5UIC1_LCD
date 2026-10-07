import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import lcd_atlas
from test_t5uic1_driver import driver
from t5uic1_driver import T5UIC1Display


JPEG_A = b"\xFF\xD8atlas-a\xFF\xD9"
JPEG_B = b"\xFF\xD8atlas-b\xFF\xD9"


def configured_driver(directory, data_a=JPEG_A, data_b=JPEG_B):
    root = Path(directory)
    path_a = root / "a.jpg"
    path_b = root / "b.jpg"
    path_a.write_bytes(data_a)
    path_b.write_bytes(data_b)

    lcd = driver()
    lcd._atlas_specs, lcd._atlas_icons = lcd._build_atlas_config(
        {
            0: (path_a, 14),
            1: (path_b, 15),
        },
        {
            0x100: (0, 10, 20, 5, 6),
            0x101: (1, 30, 40, 7, 8),
        },
    )
    lcd._virtual_area_pictures = {}
    lcd._atlas_synced = True
    return lcd, path_a, path_b


class AtlasDriverTests(unittest.TestCase):
    def test_manifest_coordinates_match_current_custom_static_icons(self):
        self.assertEqual(lcd_atlas.ICON_MMU_HOME_NORMAL, 0x0100)
        self.assertEqual(lcd_atlas.ICON_MMU_HOME_SELECTED, 0x0101)
        self.assertEqual(lcd_atlas.ICON_FOLDER, 0x0102)
        self.assertEqual(
            lcd_atlas.ICON_COORDINATES,
            {
                0x0100: (0, 0, 0, 77, 47),
                0x0101: (0, 80, 0, 77, 47),
                0x0102: (0, 160, 0, 20, 18),
            },
        )
        self.assertEqual(
            lcd_atlas.ATLAS_FILES,
            {
                0: ("assets/klipperdwin_atlas_0.jpg", 14),
                1: ("assets/klipperdwin_atlas_1.jpg", 15),
            },
        )

    def test_coordinate_table_is_validated_once_at_driver_boundary(self):
        with self.assertRaises(ValueError):
            T5UIC1Display._build_atlas_config(
                {0: ("a.jpg", 14), 1: ("b.jpg", 14)}, {}
            )
        with self.assertRaises(ValueError):
            T5UIC1Display._build_atlas_config(
                {0: ("a.jpg", 14)}, {1: (0, 270, 0, 3, 3)}
            )
        with self.assertRaises(ValueError):
            T5UIC1Display._build_atlas_config(
                {0: ("a.jpg", 14)}, {1: (1, 0, 0, 1, 1)}
            )

    def test_draw_atlas_icon_resolves_area_and_source_rectangle(self):
        with tempfile.TemporaryDirectory() as tmp:
            lcd, _, _ = configured_driver(tmp)
            lcd._virtual_area_pictures[1] = 15
            lcd.draw_atlas_icon(0x101, 100, 120)

        self.assertEqual(len(lcd.serial.frames), 1)
        self.assertEqual(
            lcd.serial.frames[0],
            bytes.fromhex(
                "AA 27 21 "
                "00 1E 00 28 00 24 00 2F "
                "00 64 00 78 "
                "CC 33 C3 3C"
            ),
        )

    def test_draw_atlas_icon_lazily_restores_overwritten_virtual_area(self):
        with tempfile.TemporaryDirectory() as tmp:
            lcd, _, _ = configured_driver(tmp)
            lcd.cache_jpeg(3)
            self.assertEqual(lcd._virtual_area_pictures[1], 3)
            lcd.serial.frames.clear()

            lcd.draw_atlas_icon(0x101, 0, 0)

        self.assertEqual([frame[1] for frame in lcd.serial.frames], [0x25, 0x27])
        self.assertEqual(lcd.serial.frames[0],
                         bytes.fromhex("AA 25 01 0F CC 33 C3 3C"))
        self.assertEqual(lcd._virtual_area_pictures[1], 15)

    def test_area_zero_is_loaded_from_reserved_picture_before_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            lcd, _, _ = configured_driver(tmp)
            lcd.draw_atlas_icon(0x100, 50, 60)

        self.assertEqual([frame[1] for frame in lcd.serial.frames], [0x22, 0x27])
        self.assertEqual(lcd.serial.frames[0],
                         bytes.fromhex("AA 22 00 0E CC 33 C3 3C"))
        self.assertEqual(lcd._virtual_area_pictures[0], 14)

    def test_unknown_icon_and_destination_overflow_fail_without_uart(self):
        with tempfile.TemporaryDirectory() as tmp:
            lcd, _, _ = configured_driver(tmp)
            with self.assertRaises(ValueError):
                lcd.draw_atlas_icon(0x999, 0, 0)
            with self.assertRaises(ValueError):
                lcd.draw_atlas_icon(0x101, 270, 0)
        self.assertFalse(lcd.serial.frames)

    def test_sync_uploads_changed_atlases_then_commits_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            lcd, _, _ = configured_driver(tmp)
            lcd.read_flash = Mock(return_value=b"\xFF" * lcd.ATLAS_METADATA_SIZE)
            order = []
            lcd.write_sram = Mock(
                side_effect=lambda address, data: order.append(("sram", data))
            )
            lcd.store_sram_as_picture = Mock(
                side_effect=lambda picture_id: order.append(("picture", picture_id))
            )
            lcd.write_flash = Mock(
                side_effect=lambda address, data, **kwargs:
                    order.append(("metadata", address, data))
            )

            changed = lcd.sync_atlases()

        self.assertTrue(changed)
        self.assertEqual(
            [item[0] for item in order],
            ["sram", "picture", "sram", "picture", "metadata"],
        )
        self.assertEqual(order[1], ("picture", 14))
        self.assertEqual(order[3], ("picture", 15))
        metadata = order[-1][2]
        parsed = lcd._unpack_atlas_metadata(metadata)
        self.assertEqual(parsed[0][0:2], (14, len(JPEG_A)))
        self.assertEqual(parsed[1][0:2], (15, len(JPEG_B)))
        self.assertEqual(len(parsed[0][2]), lcd.ATLAS_DIGEST_SIZE)

    def test_matching_persistent_versions_skip_picture_flash_rewrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            lcd, _, _ = configured_driver(tmp)
            _, desired = lcd._atlas_payloads()
            metadata = lcd._pack_atlas_metadata(desired)
            lcd.read_flash = Mock(return_value=metadata)
            lcd.write_sram = Mock()
            lcd.store_sram_as_picture = Mock()
            lcd.write_flash = Mock()

            changed = lcd.sync_atlases()

        self.assertFalse(changed)
        lcd.write_sram.assert_not_called()
        lcd.store_sram_as_picture.assert_not_called()
        lcd.write_flash.assert_not_called()

    def test_only_the_changed_atlas_is_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            lcd, path_a, _ = configured_driver(tmp)
            _, old_entries = lcd._atlas_payloads()
            old_metadata = lcd._pack_atlas_metadata(old_entries)
            path_a.write_bytes(b"\xFF\xD8atlas-a-v2\xFF\xD9")

            lcd.read_flash = Mock(return_value=old_metadata)
            lcd.write_sram = Mock()
            lcd.store_sram_as_picture = Mock()
            lcd.write_flash = Mock()

            changed = lcd.sync_atlases()

        self.assertTrue(changed)
        lcd.store_sram_as_picture.assert_called_once_with(14)
        lcd.write_flash.assert_called_once()

    def test_metadata_is_not_advanced_when_picture_update_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            lcd, _, _ = configured_driver(tmp)
            lcd.read_flash = Mock(return_value=b"\xFF" * lcd.ATLAS_METADATA_SIZE)
            lcd.write_sram = Mock()
            lcd.store_sram_as_picture = Mock(side_effect=RuntimeError("write failed"))
            lcd.write_flash = Mock()

            with self.assertRaises(RuntimeError):
                lcd.sync_atlases()

        lcd.write_flash.assert_not_called()

    def test_invalid_or_oversized_atlas_is_rejected_before_flash_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            lcd, path_a, _ = configured_driver(tmp)
            lcd.read_flash = Mock()

            path_a.write_bytes(b"not-a-jpeg")
            with self.assertRaises(ValueError):
                lcd.sync_atlases()
            lcd.read_flash.assert_not_called()

            path_a.write_bytes(
                b"\xFF\xD8" + b"x" * T5UIC1Display.SRAM_SIZE + b"\xFF\xD9"
            )
            with self.assertRaises(ValueError):
                lcd.sync_atlases()
            lcd.read_flash.assert_not_called()

    def test_empty_coordinate_table_keeps_existing_startup_traffic_unchanged(self):
        lcd = driver()
        lcd._atlas_specs, lcd._atlas_icons = lcd._build_atlas_config(
            {0: ("missing-a.jpg", 14), 1: ("missing-b.jpg", 15)}, {}
        )
        lcd._atlas_synced = False
        lcd.read_flash = Mock()

        self.assertFalse(lcd.sync_atlases())
        self.assertTrue(lcd._atlas_synced)
        lcd.read_flash.assert_not_called()

    def test_sync_logs_upload_progress_and_persistent_metadata_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            lcd, _, _ = configured_driver(tmp)
            lcd.read_flash = Mock(return_value=b"\xFF" * lcd.ATLAS_METADATA_SIZE)
            lcd.write_sram = Mock()
            lcd.store_sram_as_picture = Mock()
            lcd.write_flash = Mock()

            with self.assertLogs(level="INFO") as captured:
                self.assertTrue(lcd.sync_atlases())

        output = "\n".join(captured.output)
        self.assertIn("Atlas sync: reading metadata @ 0x3FC0", output)
        self.assertIn("Atlas 0: changed -> upload required", output)
        self.assertIn("Atlas 0: SRAM upload complete", output)
        self.assertIn("Atlas 0: Picture Flash 14 write complete", output)
        self.assertIn("Atlas 1: Picture Flash 15 write complete", output)
        self.assertIn("Atlas metadata: Data Flash update complete", output)
        self.assertIn("Atlas sync complete: updated virtual area(s) 0,1", output)

    def test_sync_logs_unchanged_atlases_and_virtual_area_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            lcd, _, _ = configured_driver(tmp)
            _, desired = lcd._atlas_payloads()
            lcd.read_flash = Mock(return_value=lcd._pack_atlas_metadata(desired))
            lcd.write_sram = Mock()
            lcd.store_sram_as_picture = Mock()
            lcd.write_flash = Mock()

            with self.assertLogs(level="INFO") as captured:
                self.assertFalse(lcd.sync_atlases())
                lcd._virtual_area_pictures.clear()
                lcd._load_atlas_area(1)

        output = "\n".join(captured.output)
        self.assertIn("Atlas 0: unchanged -> skip", output)
        self.assertIn("Atlas 1: unchanged -> skip", output)
        self.assertIn("Atlas metadata: unchanged", output)
        self.assertIn("Atlas sync complete: no atlas uploads required", output)
        self.assertIn(
            "Atlas 1: loading Picture Flash 15 into virtual area 1", output
        )
        lcd.write_sram.assert_not_called()
        lcd.store_sram_as_picture.assert_not_called()
        lcd.write_flash.assert_not_called()

    def test_startup_can_defer_sync_until_binary_atlases_are_present(self):
        lcd = driver()
        lcd._atlas_specs, lcd._atlas_icons = lcd._build_atlas_config(
            {0: ("missing-a.jpg", 14), 1: ("missing-b.jpg", 15)},
            {0x100: (0, 0, 0, 10, 10)},
        )
        lcd._atlas_synced = False
        lcd.read_flash = Mock()

        self.assertFalse(lcd.sync_atlases(allow_missing=True))
        self.assertFalse(lcd._atlas_synced)
        lcd.read_flash.assert_not_called()
        with self.assertRaises(OSError):
            lcd.sync_atlases()

    def test_draw_is_strict_if_manifest_exists_but_jpeg_is_missing(self):
        lcd = driver()
        lcd._atlas_specs, lcd._atlas_icons = lcd._build_atlas_config(
            {0: ("missing-a.jpg", 14)},
            {0x100: (0, 0, 0, 10, 10)},
        )
        lcd._atlas_synced = False
        with self.assertRaises(OSError):
            lcd.draw_atlas_icon(0x100, 0, 0)
        self.assertFalse(lcd.serial.frames)


if __name__ == "__main__":
    unittest.main()
