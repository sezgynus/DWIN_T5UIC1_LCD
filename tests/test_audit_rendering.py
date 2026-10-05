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
