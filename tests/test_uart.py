import unittest
from unittest.mock import patch

from test_regressions import ui

Driver = ui.T5UIC1_LCD
serial_module = Driver.__init__.__globals__['serial']


class Port:
    def __init__(self, chunks=()):
        self.chunks = list(chunks)
        self.frames = []
        self.closed = 0
        self.short = False

    @property
    def in_waiting(self):
        return len(self.chunks[0]) if self.chunks else 0

    def read(self, size=1):
        if not self.chunks:
            return b''
        chunk = self.chunks.pop(0)
        value, remaining = chunk[:size], chunk[size:]
        if remaining:
            self.chunks.insert(0, remaining)
        return value

    def write(self, frame):
        self.frames.append(bytes(frame))
        return len(frame) - 1 if self.short else len(frame)

    def close(self):
        self.closed += 1


class UARTTests(unittest.TestCase):
    def open(self, port, **kwargs):
        with patch.object(serial_module, 'Serial', return_value=port, create=True):
            return Driver('/dev/fake', **kwargs)

    def test_first_handshake_frame_and_fragmented_ack_with_noise(self):
        port = Port([b'noise\xAA', b'\x00', b'O', b'K'])
        result = self.open(port)
        self.assertEqual(port.frames[0], b'\xAA\x00\xCC\x33\xC3\x3C')
        self.assertTrue(all(frame.startswith(b'\xAA') and frame.endswith(b'\xCC\x33\xC3\x3C')
                            for frame in port.frames))
        result.close()
        result.close()
        self.assertEqual(port.closed, 1)

    def test_no_screen_has_bounded_retries_and_closes_port(self):
        port = Port()
        with self.assertRaises(TimeoutError):
            self.open(port, handshake_timeout=.005, handshake_attempts=2)
        self.assertEqual(len(port.frames), 2)
        self.assertEqual(port.closed, 1)

    def test_three_byte_ack_is_incomplete_and_noise_is_bounded(self):
        result = Driver.__new__(Driver)
        result._receive_buffer = bytearray()
        self.assertFalse(result._consume_handshake(b'\xAA\x00O'))
        self.assertTrue(result._consume_handshake(b'K'))
        self.assertFalse(result._consume_handshake(b'x' * 10000))
        self.assertLessEqual(len(result._receive_buffer), 3)

    def test_short_write_is_not_retried_and_constructor_closes(self):
        port = Port()
        port.short = True
        with self.assertRaises(IOError):
            self.open(port)
        self.assertEqual(len(port.frames), 1)
        self.assertEqual(port.closed, 1)

    def test_serial_read_and_backlight_validation_do_not_corrupt_next_frame(self):
        port = Port([b'\xAA\x00OK'])
        result = self.open(port)
        port.chunks = [b'abc']
        self.assertEqual(result.Read(2), b'ab')
        self.assertEqual(result.Read(), b'c')
        with self.assertRaises(ValueError):
            result.Backlight_SetLuminance(256)
        result.Backlight_SetLuminance(0)
        self.assertEqual(port.frames[-1], b'\xAA\x30\x00\xCC\x33\xC3\x3C')
        result.close()
        with self.assertRaises(RuntimeError):
            result.UpdateLCD()

    def test_instance_buffers_are_independent(self):
        first = self.open(Port([b'\xAA\x00OK']))
        second = self.open(Port([b'\xAA\x00OK']))
        first.Byte(0x30)
        second.UpdateLCD()
        self.assertEqual(second.MYSERIAL1.frames[-1], b'\xAA\x3D\xCC\x33\xC3\x3C')
        first.close()
        second.close()
