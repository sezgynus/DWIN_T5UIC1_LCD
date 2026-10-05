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

    def test_numeric_matches_manufacturer_example(self):
        result = self.driver()
        result.Draw_FloatValue(True, False, False, 5, 0xFFFF, 0, 10, 2, 0, 0, 1234567890)
        self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex(
            'AA 14 85 FF FF 00 00 0A 02 00 00 00 00 49 96 02 D2 CC 33 C3 3C'))

    def test_integer_keeps_eight_byte_payload(self):
        result = self.driver()
        result.Draw_IntValue(True, True, False, 1, 0xFFFF, 0, 3, 10, 20, 205)
        self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex(
            'AA 14 A1 FF FF 00 00 03 00 00 0A 00 14 00 00 00 00 00 00 00 CD CC 33 C3 3C'))

    def test_negative_scaled_value_sets_signed_bit(self):
        result = self.driver()
        result.Draw_FloatValue(True, True, False, 1, 0xFFFF, 0, 3, 1, 10, 20, -15)
        self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex(
            'AA 14 E1 FF FF 00 00 03 01 00 0A 00 14 FF FF FF F1 CC 33 C3 3C'))

    def test_invalid_point_and_numeric_values_do_not_write_or_corrupt_buffer(self):
        result = self.driver()
        for operation in (lambda: result.DrawPoint(0, 0, 1, 0, 0),
                          lambda: result.DrawPoint(0, 1, 1, -1, 0),
                          lambda: result.Draw_IntValue(True, True, False, 1, 0, 0, 3, 0, 0, float('nan')),
                          lambda: result.Draw_FloatValue(True, True, False, 1, 0, 0, 3, 1, 0, 0, 2**32),
                          lambda: result.Draw_FloatValue(True, True, False, 1, 0, 0, 19, 1, 0, 0, 1)):
            with self.assertRaises((ValueError, OverflowError)):
                operation()
            self.assertEqual(result.DWIN_SendBuf, result.FHONE)
        self.assertFalse(result.MYSERIAL1.frames)
        result.UpdateLCD()
        self.assertEqual(result.MYSERIAL1.frames[-1], bytes.fromhex('AA 3D CC 33 C3 3C'))
