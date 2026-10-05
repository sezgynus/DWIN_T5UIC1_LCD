import unittest
from test_capabilities import display, snapshot
from test_uart import Driver, Port


class AuditRenderingTests(unittest.TestCase):
    def screen(self):
        result = display(snapshot())
        result.lcd = Driver.__new__(Driver)
        result.lcd.MYSERIAL1 = Port()
        result.lcd.DWIN_SendBuf = result.lcd.FHONE
        result.lcd._closed = False
        return result

    def test_complete_progress_has_three_digits_before_percent_sign(self):
        result = self.screen()
        result.Draw_Print_ProgressBar(100)
        text = [f for f in result.lcd.MYSERIAL1.frames if f[1] == 0x11]
        self.assertEqual(text[0][11:-4], b'100')
        self.assertEqual(int.from_bytes(text[0][7:9], 'big'), 109)
        self.assertEqual(text[1][11:-4], b'%')
        self.assertEqual(int.from_bytes(text[1][7:9], 'big'), 133)

    def test_print_time_formats_completed_minutes_and_long_prints(self):
        result = self.screen()
        for seconds, expected in ((0, b'00:00'), (3599, b'00:59'), (3600, b'01:00'),
                                  (359999, b'99:59'), (360000, b'100:00')):
            result.pd.duration = lambda: seconds
            result.Draw_Print_ProgressElapsed()
            self.assertEqual(result.lcd.MYSERIAL1.frames[-1][11:-4], expected)

    def test_near_zero_negative_does_not_leave_minus_sign(self):
        result = self.screen()
        result.lcd.Draw_Signed_Float(1, 0, 2, 2, 100, 20, -.1)
        self.assertEqual(result.lcd.MYSERIAL1.frames[-1][11:-4], b'  0.00')

    def test_thermal_editor_draw_is_flushed_by_input_owner(self):
        from ui_events import InputEvent
        from unittest.mock import Mock
        result = self.screen()
        result._closed = False
        result._encoder_event = result.ENCODER_DIFF_NO
        result._dispatch_input = lambda: result.lcd.Draw_IntValue(True, True, 0, 1, 0xFFFF, 0, 3, 216, 50, 205)
        result._process_input(InputEvent('press', 1, 1))
        self.assertEqual([frame[1] for frame in result.lcd.MYSERIAL1.frames], [0x11, 0x3D])

    def test_info_long_version_and_unicode_fields_have_visible_coordinates(self):
        result = self.screen()
        result.pd.SHORT_BUILD_VERSION = 'v' * 100
        result.pd.MACHINE_SIZE = 'Ölçüm' * 20
        result.pd.CORP_WEBSITE_E = 'https://' + 'x' * 100
        result.Draw_Info_Menu()
        frames = [frame for frame in result.lcd.MYSERIAL1.frames if frame[1] == 0x11]
        self.assertEqual(len(frames), 3)
        for frame in frames:
            self.assertEqual(int.from_bytes(frame[7:9], 'big'), 0)
            self.assertEqual(len(frame[11:-4]), 34)

    def test_large_printer_values_show_overflow_without_changing_target(self):
        result = self.screen()
        result.pd.feedrate_percentage = 1000
        result.pd.thermalManager['temp_hotend'][0]['target'] = 1200
        result.Draw_Status_Area(False)
        self.assertTrue(any(frame[11:-4] == b'###' for frame in result.lcd.MYSERIAL1.frames if frame[1] == 0x11))
        self.assertEqual(result.pd.feedrate_percentage, 1000)
        self.assertEqual(result.pd.thermalManager['temp_hotend'][0]['target'], 1200)
        result.lcd.Draw_Signed_Float(1, 0, 3, 1, 216, 50, 1234567890)
        self.assertEqual(result.lcd.MYSERIAL1.frames[-1][11:-4], b'######')
        result.lcd.Draw_Signed_Float(1, 0, 3, 1, 216, 50, 5)
        self.assertEqual(result.lcd.MYSERIAL1.frames[-1][11:-4], b'   0.5')

    def test_negative_integer_sign_transition_clears_entire_field(self):
        result = self.screen()
        for value, expected in ((-5, b' -5'), (5, b'  5'), (-999, b'###')):
            result.lcd.Draw_IntValue(True, True, 0, 1, 0xFFFF, 0, 3, 33, 50, value)
            self.assertEqual(result.lcd.MYSERIAL1.frames[-1][11:-4], expected)

    def test_motion_value_is_complete_scientific_text_with_fixed_padding(self):
        result = self.screen()
        result.checkkey = result.Motion
        result.pd.motion_settings = lambda: (('max_accel', 'ACCEL', 'Accel', 10, 1234567890123),)
        result.Draw_Motion_Menu()
        frames = [frame for frame in result.lcd.MYSERIAL1.frames if frame[1] == 0x11]
        self.assertEqual(frames[-1][11:-4], b' 1.23e+12')
        self.assertEqual(int.from_bytes(frames[-1][7:9], 'big'), 168)
        self.assertLessEqual(168 + 9 * result.MENU_CHR_W, 240)

    def test_extreme_finite_numbers_render_marker_without_decimal_overflow(self):
        result = self.screen()
        for value in (1e300, -1e300, 10**100):
            result.lcd.Draw_IntValue(True, True, 0, 1, 0xFFFF, 0, 3, 33, 50, value)
            self.assertEqual(result.lcd.MYSERIAL1.frames[-1][11:-4], b'###')

    def test_move_menu_and_editor_use_same_command_coordinates(self):
        data = snapshot()
        data['status']['toolhead']['position'] = [91, 92, 93, 94]
        data['status']['gcode_move']['position'] = [-1.5, 12.3, 2.5, -4.5]
        result = self.screen()
        result.pd.subscription.snapshot.return_value = data
        result.pd.update_variable()
        result.Draw_Move_Menu()
        frames = [f for f in result.lcd.MYSERIAL1.frames if f[1] == 0x11]
        self.assertEqual([f[11:-4].strip() for f in frames],
                         [b'-1.5', b'12.3', b'2.5', b'-4.5'])
        result.select_axis.set(1)
        result.get_encoder_state = lambda: result.ENCODER_DIFF_ENTER
        result.HMI_AxisMove()
        self.assertEqual(result.pd.HMI_ValueStruct.Move_X_scale, -15)
        frames = [f for f in result.lcd.MYSERIAL1.frames if f[1] == 0x11]
        self.assertEqual(frames[-1][11:-4].strip(), b'-1.5')
        result.pd.sendGCode.assert_not_called()

    def test_move_menu_without_hotend_draws_only_xyz(self):
        result = display(snapshot(hotend=False))
        result.Draw_Move_Menu()
        self.assertEqual(result.lcd.Draw_FloatValue.call_count, 3)
        result.lcd.Draw_Signed_Float.assert_not_called()
