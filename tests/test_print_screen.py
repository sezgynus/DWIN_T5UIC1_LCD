import unittest
from unittest.mock import Mock

from test_capabilities import snapshot, display, printer


class PrintScreenTests(unittest.TestCase):
    def display(self, state):
        data = snapshot()
        data['status']['print_stats'].update(state=state, filename='part.gcode',
                                            print_duration=120, message='Heater fault')
        result = display(data)
        result.lcd.DWIN_WIDTH = 272
        result._offline = False
        result.checkkey = result.MainMenu
        result.select_print.reset()
        result.Draw_Status_Area = Mock()
        result.Draw_Print_ProgressBar = Mock()
        result.Draw_Print_ProgressElapsed = Mock()
        result.Draw_Print_ProgressRemain = Mock()
        result.Draw_Tune_Menu = Mock()
        result._show_message = Mock()
        result.Goto_MainMenu = Mock(side_effect=lambda: setattr(result, 'checkkey', result.MainMenu))
        result.Goto_PrintProcess = Mock(side_effect=lambda: setattr(result, 'checkkey', result.PrintProcess))
        return result

    def test_paused_boot_has_print_screen_and_resume_action(self):
        result = self.display('paused')
        result.HMI_StartFrame(False)
        result.Goto_PrintProcess.assert_called_once()
        self.assertTrue(result.pd.HMI_flag.pause_flag)
        result.select_print.set(1)
        result.pd.resume_job = Mock()
        result.get_encoder_state = Mock(return_value=result.ENCODER_DIFF_ENTER)
        result.HMI_Printing()
        result.pd.resume_job.assert_called_once()

    def test_complete_stays_until_confirm_and_does_not_reappear(self):
        result = self.display('printing')
        result.HMI_StartFrame(False)
        data = result.pd.subscription.snapshot.return_value
        data['status']['print_stats']['state'] = 'complete'
        data['revision'] += 1
        result.EachMomentUpdate()
        self.assertEqual(result.checkkey, result.PrintProcess)
        self.assertTrue(result.pd.HMI_flag.done_confirm_flag)
        result.EachMomentUpdate()
        self.assertEqual(result.checkkey, result.PrintProcess)
        result.get_encoder_state = Mock(return_value=result.ENCODER_DIFF_ENTER)
        result.HMI_Printing()
        self.assertEqual(result.checkkey, result.MainMenu)
        result.HMI_StartFrame(False)
        self.assertFalse(result.pd.HMI_flag.done_confirm_flag)
        self.assertEqual(result.checkkey, result.MainMenu)
        result.pd.sendGCode.assert_not_called()

    def test_complete_boot_is_confirmable(self):
        result = self.display('complete')
        result.HMI_StartFrame(False)
        self.assertTrue(result.pd.HMI_flag.done_confirm_flag)

    def test_error_message_is_retained_until_enter(self):
        result = self.display('error')
        result.HMI_StartFrame(False)
        result._show_message.assert_called_once_with('Heater fault')
        result.EachMomentUpdate()
        self.assertTrue(result._print_error_visible)
        result.get_encoder_state = Mock(return_value=result.ENCODER_DIFF_CW)
        result._dispatch_input()
        self.assertTrue(result._print_error_visible)
        result.get_encoder_state.return_value = result.ENCODER_DIFF_ENTER
        result._dispatch_input()
        result.HMI_StartFrame(False)
        self.assertFalse(result._print_error_visible)
        result._show_message.assert_called_once()

    def test_cancelled_and_standby_return_to_main(self):
        for state in ('cancelled', 'standby'):
            result = self.display(state)
            result.HMI_StartFrame(False)
            result.Goto_MainMenu.assert_called_once()
            self.assertFalse(result.pd.HMI_flag.done_confirm_flag)

    def test_new_print_clears_previous_completion_prompt(self):
        result = self.display('complete')
        result.HMI_StartFrame(False)
        result.pd.subscription.snapshot.return_value['status']['print_stats']['state'] = 'printing'
        result.EachMomentUpdate()
        self.assertFalse(result.pd.HMI_flag.done_confirm_flag)
        self.assertEqual(result.checkkey, result.PrintProcess)

    def test_external_speed_updates_tune_without_overwriting_editor(self):
        result = self.display('printing')
        result.HMI_StartFrame(False)
        result.checkkey = result.Tune
        data = result.pd.subscription.snapshot.return_value
        data['status']['gcode_move']['speed_factor'] = .75
        result.EachMomentUpdate()
        self.assertEqual(result.pd.feedrate_percentage, 75)
        result.Draw_Tune_Menu.assert_called_once()
        result.Draw_Tune_Menu.reset_mock()
        result.checkkey = result.PrintSpeed
        result.pd.HMI_ValueStruct.print_speed = 125
        data['status']['gcode_move']['speed_factor'] = .8
        result.EachMomentUpdate()
        self.assertEqual(result.pd.feedrate_percentage, 80)
        self.assertEqual(result.pd.HMI_ValueStruct.print_speed, 125)
        result.Draw_Tune_Menu.assert_not_called()

    def test_speed_submission_does_not_assume_success(self):
        result = printer(snapshot())
        result.set_feedrate(125)
        result.sendGCode.assert_called_once_with('M220 S125')
        self.assertEqual(result.feedrate_percentage, 100)
        with self.assertRaises(ValueError):
            result.set_feedrate(0)
