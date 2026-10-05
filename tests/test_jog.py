import unittest
from unittest.mock import Mock

from test_capabilities import snapshot, printer, display


class JogTests(unittest.TestCase):
    def test_all_modal_combinations_restore_state_without_origin_reset(self):
        for coordinates in (False, True):
            for extrusion in (False, True):
                data = snapshot()
                data['status']['gcode_move'].update(absolute_coordinates=coordinates,
                    absolute_extrude=extrusion, position=[100, 0, 0, 800])
                result = printer(data)
                result.moveAbsolute('X', 110, 5000)
                script = result.sendGCode.call_args.args[0].splitlines()
                self.assertEqual(script[0], 'SAVE_GCODE_STATE NAME=_DWIN_JOG')
                self.assertEqual(script[-1], 'RESTORE_GCODE_STATE NAME=_DWIN_JOG MOVE=0')
                self.assertIn('G1 X10 F5000', script)
                self.assertIn('M83', script)
                self.assertIn('M220 S100', script)
                self.assertIn('M221 S100', script)
                self.assertFalse(any(line.startswith('G92') for line in script))

    def test_extrusion_uses_displacement_from_command_space(self):
        data = snapshot()
        data['status']['gcode_move']['position'][3] = 800
        result = printer(data)
        result.moveAbsolute('E', 805, 300)
        self.assertIn('G1 E5 F300', result.sendGCode.call_args.args[0])
        self.assertEqual(result.state.status['gcode_move']['position'][3], 800)

    def test_relative_move_checks_destination_and_homing(self):
        result = printer(snapshot())
        result.moveRelative('X', -10, 5000)
        result.sendGCode.reset_mock()
        with self.assertRaises(ValueError):
            result.moveRelative('X', -10.1, 5000)
        data = snapshot()
        data['status']['toolhead']['homed_axes'] = 'yz'
        result = printer(data)
        with self.assertRaises(ValueError):
            result.moveAbsolute('X', 1, 5000)
        result.sendGCode.assert_not_called()

    def test_printing_and_paused_jobs_reject_jog(self):
        for state in ('printing', 'paused', 'pausing'):
            data = snapshot()
            data['status']['print_stats']['state'] = state
            result = printer(data)
            with self.assertRaises(ValueError):
                result.moveRelative('X', 1, 5000)
            result.sendGCode.assert_not_called()

    def test_cold_and_excessive_extrusion_rejected_at_confirmation(self):
        for cold, distance in ((True, 1), (False, 36), (False, -36)):
            data = snapshot()
            data['status']['extruder']['can_extrude'] = not cold
            result = printer(data)
            with self.assertRaises(ValueError):
                result.moveRelative('E', distance, 300)
            result.sendGCode.assert_not_called()

    def test_invalid_axis_numbers_and_speed_do_not_submit(self):
        result = printer(snapshot())
        for axis, amount, speed in (('X\nG28', 1, 300), ('X', float('nan'), 300),
                                    ('X', 1, float('inf')), ('X', 1, 0)):
            with self.assertRaises(ValueError):
                result.moveRelative(axis, amount, speed)
        result.sendGCode.assert_not_called()

    def test_z_feed_is_limited_by_printer_configuration(self):
        data = snapshot()
        data['settings']['printer']['max_z_velocity'] = 5
        result = printer(data)
        result.moveRelative('Z', 1, 600)
        self.assertIn('G1 Z1 F300', result.sendGCode.call_args.args[0])

    def test_ui_rotation_keeps_authoritative_position_until_confirmed(self):
        result = display(snapshot())
        result.pd.HMI_ValueStruct.Move_X_scale = 0
        result.get_encoder_state = Mock(return_value=result.ENCODER_DIFF_CW)
        result.HMI_Move_X()
        self.assertEqual(result.pd.current_position.x, 0)
        result.pd.sendGCode.assert_not_called()
        result.get_encoder_state.return_value = result.ENCODER_DIFF_ENTER
        result.HMI_Move_X()
        self.assertIn('G1 X0.1 F5000', result.pd.sendGCode.call_args.args[0])
        self.assertEqual(result.pd.current_position.x, 0)
