import contextlib
import io
import os
import unittest
from unittest.mock import patch

import run


class ConfigTests(unittest.TestCase):
    def test_environment_defaults(self):
        values = dict(MOONRAKER_URL='http://printer:7125', DWIN_SERIAL_PORT='/dev/test',
                      DWIN_ENCODER_PINS='26 19', DWIN_BUTTON_PIN='13',
                      DWIN_REQUEST_TIMEOUT='2.5', DWIN_SETTINGS_FILE='/tmp/presets.json',
                      DWIN_POWER_DEVICE='Printer', DWIN_POWER_ON_HOLD_MS='1500')
        with patch.dict(os.environ, values, clear=True):
            args = run.parse_args([])
        self.assertEqual(args.encoder_pins, (26, 19))
        self.assertEqual(args.request_timeout, 2.5)
        self.assertEqual(args.serial_port, '/dev/test')
        self.assertEqual(args.settings_file, '/tmp/presets.json')
        self.assertEqual(args.moonraker_url, 'http://printer:7125')
        self.assertEqual(args.power_device, 'Printer')
        self.assertEqual(args.power_on_hold_ms, 1500)

    def test_cli_overrides_environment(self):
        with patch.dict(os.environ, {'DWIN_ENCODER_PINS': '26 19', 'DWIN_REQUEST_TIMEOUT': '2'}, clear=True):
            args = run.parse_args(['--encoder-pins', '21', '19', '--request-timeout', '3'])
        self.assertEqual(args.encoder_pins, (21, 19))
        self.assertEqual(args.request_timeout, 3)

    def test_invalid_configuration_exits_before_hardware_import(self):
        for values in (dict(DWIN_ENCODER_PINS='21'), dict(DWIN_ENCODER_PINS='13 19'),
                       dict(DWIN_ENCODER_PINS='28 19'), dict(DWIN_REQUEST_TIMEOUT='nan'),
                       dict(DWIN_REQUEST_TIMEOUT='0'), dict(DWIN_BUTTON_PIN='invalid'),
                       dict(DWIN_POWER_ON_HOLD_MS='-1'), dict(DWIN_POWER_ON_HOLD_MS='invalid')):
            with self.subTest(values=values), patch.dict(os.environ, values, clear=True), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    run.parse_args([])
                self.assertEqual(error.exception.code, 2)
