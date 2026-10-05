import unittest
from concurrent.futures import Future
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
                self.assertTrue(script[0].startswith('SAVE_GCODE_STATE NAME=_DWIN_JOG_'))
                self.assertEqual(script[-1], 'RESTORE_GCODE_STATE NAME=' + script[0].split('NAME=')[1] + ' MOVE=0')
                self.assertEqual(result.sendGCode.call_args.kwargs['cleanup'], script[-1])
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

    def test_live_jog_applies_accelerated_relative_move_without_confirm_duplicate(self):
        result = display(snapshot())
        result._live_jog = True
        result._live_jog_future = None
        result._live_jog_pending = None
        result._encoder_move_value = 50
        result.pd.HMI_ValueStruct.Move_X_scale = 0
        result.get_encoder_state = Mock(return_value=result.ENCODER_DIFF_CW)
        result.HMI_Move_X()
        self.assertIn('G1 X5 F5000', result.pd.sendGCode.call_args.args[0])
        result.pd.sendGCode.reset_mock()
        result.get_encoder_state.return_value = result.ENCODER_DIFF_ENTER
        result.HMI_Move_X()
        result.pd.sendGCode.assert_not_called()

    def test_live_jog_coalesces_input_while_move_is_in_flight(self):
        result = display(snapshot())
        result._live_jog_future = None
        result._live_jog_pending = None
        result._loop = Mock()
        first = Future()
        second = Future()
        result.pd.moveRelative = Mock(side_effect=[first, second])
        result._queue_live_jog('X', 1.0, 5000)
        result._queue_live_jog('X', 2.0, 5000)
        result._queue_live_jog('X', 3.0, 5000)
        self.assertEqual(result.pd.moveRelative.call_count, 1)
        first.set_result(None)
        result._flush_live_jog()
        self.assertEqual(result.pd.moveRelative.call_args_list[1].args, ('X', 5.0, 5000))

    def test_live_jog_toggle_is_last_move_menu_item(self):
        result = display(snapshot())
        result._live_jog = False
        result._live_jog_future = None
        result._live_jog_pending = None
        result.select_axis.set(5)
        result.get_encoder_state = Mock(return_value=result.ENCODER_DIFF_ENTER)
        result.Draw_Move_Menu = Mock()
        result.HMI_AxisMove()
        self.assertTrue(result._live_jog)
        result.Draw_Move_Menu.assert_called()

    def test_live_jog_queues_only_distance_remaining_to_axis_limit(self):
        result = display(snapshot())
        result._live_jog = True
        result._live_jog_future = None
        result._live_jog_pending = None
        result._encoder_move_value = 50
        result.pd.HMI_ValueStruct.Move_X_scale = result.pd.X_MAX_POS * result.MINUNITMULT - 10
        result.get_encoder_state = Mock(return_value=result.ENCODER_DIFF_CW)
        result.HMI_Move_X()
        self.assertIn('G1 X1 F5000', result.pd.sendGCode.call_args.args[0])
        self.assertEqual(result.pd.HMI_ValueStruct.Move_X_scale,
                         result.pd.X_MAX_POS * result.MINUNITMULT)
