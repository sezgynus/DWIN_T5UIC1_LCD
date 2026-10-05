import unittest
from test_capabilities import snapshot, printer


class PreheatFanTests(unittest.TestCase):
    def test_profile_applies_installed_heaters_and_fan_in_one_submission(self):
        result = printer(snapshot())
        result.material_preset[0].fan_speed = 50
        returned = result.preheat('PLA')
        result.sendGCode.assert_called_once_with(
            'SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=60\n'
            'SET_HEATER_TEMPERATURE HEATER=extruder TARGET=200\nM106 S127.5')
        self.assertIs(returned, result.sendGCode.return_value)

    def test_invalid_fan_prevents_partial_heating(self):
        for value in (-1, 101, float('nan'), float('inf')):
            result = printer(snapshot())
            result.material_preset[0].fan_speed = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                result.preheat('PLA')
            result.sendGCode.assert_not_called()

    def test_no_part_fan_does_not_send_m106(self):
        result = printer(snapshot(fan=False))
        result.preheat('ABS')
        self.assertNotIn('M106', result.sendGCode.call_args.args[0])

    def test_bed_only_printer_applies_bed_and_available_fan(self):
        result = printer(snapshot(hotend=False))
        result.material_preset[0].fan_speed = 0
        result.preheat('PLA')
        result.sendGCode.assert_called_once_with(
            'SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=60\nM106 S0')

    def test_active_extruder_and_unknown_profile(self):
        result = printer(snapshot(multiple=True))
        result.preheat('PLA')
        self.assertIn('HEATER=extruder1 TARGET=200', result.sendGCode.call_args.args[0])
        result.sendGCode.reset_mock()
        with self.assertRaises(ValueError):
            result.preheat('unknown')
        result.sendGCode.assert_not_called()
