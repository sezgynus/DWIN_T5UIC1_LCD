import unittest
from test_uart import Driver, Port


class PacketTests(unittest.TestCase):
    def driver(self):
        result = Driver.__new__(Driver)
        result.MYSERIAL1 = Port()
        result.DWIN_SendBuf = result.FHONE
        result._closed = False
        return result

    def test_point_matches_manufacturer_layout(self):
        result = self.driver()
        result.DrawPoint(0xF800, 4, 4, 8, 8)
        self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex('AA 02 F8 00 04 04 00 08 00 08 CC 33 C3 3C'))
        result.Draw_Point(4, 4, 8, 8, color=0xF800)
        self.assertEqual(result.MYSERIAL1.frames[-1], result.MYSERIAL1.frames[-2])

    def test_numeric_uses_proui_text_and_scaled_rounding(self):
        result = self.driver()
        result.Draw_FloatValue(True, False, False, 1, 0xFFFF, 0, 3, 1, 10, 20, -15.5)
        self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex(
            'AA 11 41 FF FF 00 00 00 02 00 14') + b'  -1.6' + bytes.fromhex('CC 33 C3 3C'))
        result.Draw_FloatValue(True, False, False, 1, 0xFFFF, 0, 3, 1, 10, 20, 15.5)
        self.assertEqual(result.MYSERIAL1.frames[-1][11:-4], b'   1.6')

    def test_integer_is_padded_text(self):
        result = self.driver()
        result.Draw_IntValue(True, True, False, 1, 0xFFFF, 0, 3, 10, 20, 5)
        self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex(
            'AA 11 41 FF FF 00 00 00 0A 00 14') + b'  5' + bytes.fromhex('CC 33 C3 3C'))

    def test_signed_wrapper_emits_one_complete_field(self):
        result = self.driver()
        result.Draw_Signed_Float(2, 0, 2, 2, 30, 20, -125)
        self.assertEqual(result.MYSERIAL1.frames[-1][11:-4], b' -1.25')
        self.assertEqual(len(result.MYSERIAL1.frames), 1)

    def test_invalid_point_and_numeric_values_do_not_write_or_corrupt_buffer(self):
        result = self.driver()
        for operation in (lambda: result.DrawPoint(0, 0, 1, 0, 0),
                          lambda: result.DrawPoint(0, 1, 1, -1, 0),
                          lambda: result.Draw_IntValue(True, True, False, 1, 0, 0, 3, 0, 0, float('nan')),
                          lambda: result.Draw_FloatValue(True, True, False, 1, 0, 0, 19, 1, 0, 0, 1)):
            with self.assertRaises((ValueError, OverflowError)):
                operation()
            self.assertEqual(result.DWIN_SendBuf, result.FHONE)
        self.assertFalse(result.MYSERIAL1.frames)
        result.UpdateLCD()
        self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex('AA 3D CC 33 C3 3C'))

    def test_icon_and_copy_flags_follow_proui_transparency(self):
        result = self.driver()
        result.ICON_Show(9, 1, 10, 20)
        self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex('AA 23 00 0A 00 14 29 01 CC 33 C3 3C'))
        result.ICON_Show(9, 1, 10, 20, background=True, enhanced=False)
        self.assertEqual(result.MYSERIAL1.frames[-1][6], 0x89)
        result.Frame_AreaCopy(1, 0, 0, 10, 20, 30, 40)
        self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex('AA 27 21 00 00 00 00 00 0A 00 14 00 1E 00 28 CC 33 C3 3C'))
        result.Frame_AreaCopy(1, 0, 0, 10, 20, 30, 40, background=True, restore=True)
        self.assertEqual(result.MYSERIAL1.frames[-1][2], 0xE1)
        with self.assertRaises(ValueError):
            result.ICON_Show(32, 0, 0, 0)

    def test_animation_control_uses_29_and_word_mask(self):
        result = self.driver()
        result.ICON_AnimationControl(0x8001)
        self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex('AA 29 80 01 CC 33 C3 3C'))
        for value in (-1, 65536):
            with self.assertRaises(ValueError):
                result.ICON_AnimationControl(value)
        self.assertEqual(len(result.MYSERIAL1.frames), 1)

    def test_backlight_preserves_full_byte_range(self):
        result = self.driver()
        for value in (0, 1, 31, 255):
            result.Backlight_SetLuminance(value)
            self.assertEqual(result.MYSERIAL1.frames[-1], bytes((0xAA, 0x30, value, 0xCC, 0x33, 0xC3, 0x3C)))

    def test_startup_wakes_then_handshakes_and_sets_direction_without_jpg(self):
        from unittest.mock import patch
        from test_uart import serial_module
        port = Port([b'\xAA\x00OK'])
        with patch.object(serial_module, 'Serial', return_value=port, create=True), \
                patch.object(Driver.__init__.__globals__['time'], 'sleep') as sleep:
            result = Driver('/dev/fake')
        self.assertEqual(sleep.call_args_list[0].args, (0.750,))
        self.assertEqual(port.frames, [bytes.fromhex(frame) for frame in (
            'AA 00 CC 33 C3 3C', 'AA 34 5A A5 01 CC 33 C3 3C', 'AA 3D CC 33 C3 3C')])
        result.close()

    def test_update_only_flushes_pending_draws_and_failed_flush_stays_dirty(self):
        result = self.driver()
        result.UpdateLCD()
        result.UpdateLCD()
        self.assertEqual(len(result.MYSERIAL1.frames), 1)
        result.Frame_Clear(0)
        result.Draw_Line(0xFFFF, 0, 0, 10, 10)
        result.UpdateLCD()
        result.UpdateLCD()
        self.assertEqual([frame[1] for frame in result.MYSERIAL1.frames], [0x3D, 1, 3, 0x3D])
        result.Frame_Clear(0)
        result.MYSERIAL1.short = True
        with self.assertRaises(IOError):
            result.UpdateLCD()
        self.assertTrue(result._needs_update)

    def test_text_transliterates_turkish_and_bounds_visible_field(self):
        result = self.driver()
        result.Draw_String(False, True, 1, 0xFFFF, 0, 0, 0, 'İşık ölçümü: ğüşçöı😀\n')
        self.assertEqual(result.MYSERIAL1.frames[-1][11:-4], b'Isik olcumu: guscoi??')
        result.Draw_String(False, True, 0, 0, 0, 0, 0, 'x' * 10000)
        self.assertEqual(len(result.MYSERIAL1.frames[-1][11:-4]), 45)
        result.Draw_String(False, True, 1, 0, 0, 256, 0, 'abcd')
        self.assertEqual(result.MYSERIAL1.frames[-1][11:-4], b'ab')
        count = len(result.MYSERIAL1.frames)
        result.Draw_String(False, True, 1, 0, 0, 272, 0, 'abcd')
        self.assertEqual(len(result.MYSERIAL1.frames), count)
        with self.assertRaises(ValueError):
            result.Draw_String(False, True, 10, 0, 0, 0, 0, 'bad')
        self.assertEqual(result.DWIN_SendBuf, result.FHONE)

    def test_common_command_frames_match_pinned_marlin_source(self):
        cases = (
            (lambda d: d.Frame_Clear(0x1234), 'AA 01 12 34 CC 33 C3 3C'),
            (lambda d: d.Draw_Line(0x1234, 1, 2, 3, 4), 'AA 03 12 34 00 01 00 02 00 03 00 04 CC 33 C3 3C'),
            (lambda d: d.Draw_Rectangle(1, 0x1234, 1, 2, 3, 4), 'AA 05 01 12 34 00 01 00 02 00 03 00 04 CC 33 C3 3C'),
            (lambda d: d.Frame_AreaMove(1, 2, 10, 0x1234, 1, 2, 3, 4), 'AA 09 82 00 0A 12 34 00 01 00 02 00 03 00 04 CC 33 C3 3C'),
            (lambda d: d.JPG_ShowAndCache(1), 'AA 22 00 01 CC 33 C3 3C'),
            (lambda d: d.JPG_CacheTo1(1), 'AA 25 01 01 CC 33 C3 3C'),
            (lambda d: d.QR_Code(2, 10, 20, 'abc'), 'AA 21 00 0A 00 14 02 61 62 63 CC 33 C3 3C'),
            (lambda d: d.ICON_Animation(1, True, 9, 1, 2, 10, 20, 5), 'AA 28 00 0A 00 14 C1 09 01 02 05 CC 33 C3 3C'),
        )
        for operation, expected in cases:
            with self.subTest(frame=expected):
                result = self.driver()
                operation(result)
                self.assertEqual(result.MYSERIAL1.frames, [bytes.fromhex(expected)])

    def test_decimal_field_roundtrip_uses_same_position_and_width(self):
        result = self.driver()
        for value, expected in ((-125, b' -1.25'), (125, b'  1.25'), (0, b'  0.00'), (9999, b' 99.99')):
            result.Draw_Signed_Float(1, 0, 2, 2, 100, 20, value)
            frame = result.MYSERIAL1.frames[-1]
            self.assertEqual(frame[7:11], bytes.fromhex('00 5C 00 14'))
            self.assertEqual(frame[11:-4], expected)
        result.Draw_Signed_Float(1, 0, 2, 2, 100, 20, 9999.5)
        self.assertEqual(result.MYSERIAL1.frames[-1][11:-4], b'######')
        self.assertEqual(len(result.MYSERIAL1.frames), 5)

    def test_invalid_packet_fields_never_poison_following_command(self):
        operations = (
            lambda d: d.Draw_Line(65536, 0, 0, 1, 1),
            lambda d: d.Draw_Rectangle(3, 0, 0, 0, 1, 1),
            lambda d: d.Draw_Rectangle(1, 0, 0, 0, -1, 1),
            lambda d: d.Frame_AreaMove(1, 4, 1, 0, 0, 0, 1, 1),
            lambda d: d.Frame_SetDir(4),
            lambda d: d.Frame_Clear(65536),
            lambda d: d.ICON_Show(9, 256, 0, 0),
            lambda d: d.ICON_Show(9, 1, -1, 0),
            lambda d: d.JPG_ShowAndCache(256),
            lambda d: d.JPG_CacheToN(1, 256),
            lambda d: d.Frame_AreaCopy(1, 0, 0, 1, 1, 65536, 0),
            lambda d: d.ICON_Animation(16, True, 9, 1, 2, 0, 0, 1),
            lambda d: d.ICON_Animation(1, True, 9, 1, 2, 0, 0, 256),
            lambda d: d.QR_Code(0, 0, 0, 'abc'),
            lambda d: d.QR_Code(1, 0, 0, 'x' * 95),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                result = self.driver()
                with self.assertRaises((ValueError, OverflowError)):
                    operation(result)
                self.assertEqual(result.DWIN_SendBuf, result.FHONE)
                self.assertFalse(result.MYSERIAL1.frames)
                result.Frame_Clear(0)
                self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex('AA 01 00 00 CC 33 C3 3C'))

    def test_qr_utf8_limit_counts_bytes_and_preserves_valid_payload(self):
        result = self.driver()
        result.QR_Code(1, 0, 0, 'ü' * 47)
        self.assertEqual(result.MYSERIAL1.frames[-1][7:-4], ('ü' * 47).encode())
        with self.assertRaises(ValueError):
            result.QR_Code(1, 0, 0, 'ü' * 48)
        self.assertEqual(len(result.MYSERIAL1.frames), 1)
