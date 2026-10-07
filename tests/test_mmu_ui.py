from concurrent.futures import Future
import unittest
from unittest.mock import Mock

from test_capabilities import display
from test_mmu_control import mmu_snapshot


class MMUUITests(unittest.TestCase):
    def make(self, **changes):
        data = mmu_snapshot(**changes)
        view = display(data)
        view.lcd.DWIN_WIDTH = 272
        view.lcd.DWIN_HEIGHT = 480
        view.lcd.Line_Color = 0x3A6A
        view.get_encoder_state = Mock(return_value=view.ENCODER_DIFF_NO)
        view.pd.subscription.responses_since.return_value = (0, ())
        view.pd.subscription.request.return_value = Future()
        view.Enter_MMU_Menu()
        return view, data

    def press(self, view, selection):
        view._mmu_selection = selection
        view.get_encoder_state.return_value = view.ENCODER_DIFF_ENTER
        view._dispatch_input()

    def strings(self, view):
        return [c.args[-1] for c in view.lcd.Draw_String.call_args_list]

    def edit_map(self, v):
        self.press(v, 3)
        self.press(v, 1)
        v.get_encoder_state.return_value = v.ENCODER_DIFF_CW
        v.HMI_MMU_Menu()
        self.press(v, 1)

    def test_map_edit_accept_only_changes_draft_cancel_discards(self):
        v, _ = self.make()
        self.edit_map(v)
        self.assertEqual(v._mmu_map_draft, [1, 1, 2, 3])
        v.pd.subscription.request.assert_not_called()
        self.press(v, len(v._mmu_items(v.pd.mmu_session.state)))
        self.assertEqual(v._mmu_page, 'home')
        self.press(v, 3)
        self.assertEqual(v._mmu_map_draft, [0, 1, 2, 3])

    def test_map_save_cancel_keeps_draft_then_confirm_sends_one_bulk_command(self):
        v, _ = self.make()
        self.edit_map(v)
        self.press(v, 5)
        self.assertEqual(v._mmu_page, 'confirm')
        self.assertEqual(v._mmu_selection, 1)
        self.assertIn('T0 > G2', self.strings(v))
        self.press(v, 1)
        self.assertEqual(v._mmu_map_draft, [1, 1, 2, 3])
        self.press(v, 5)
        self.press(v, 2)
        self.assertEqual(v._mmu_page, 'status')
        self.assertEqual(v.pd.subscription.request.call_args.args,
                         ('printer.gcode.script', {'script': 'MMU_TTG_MAP MAP=1,1,2,3'}))
        self.assertEqual(v.pd.subscription.request.call_count, 1)

    def test_map_external_change_and_printing_lock_save(self):
        for change in ('map', 'print'):
            v, data = self.make()
            self.edit_map(v)
            if change == 'map': data['status']['mmu']['ttg_map'] = [3]*4
            else: data['status']['print_stats']['state'] = 'printing'
            self.press(v, 5)
            self.assertEqual(v._mmu_page, 'map')
            v.pd.subscription.request.assert_not_called()

    def test_map_scroll_and_gate_edit_bounds(self):
        v, _ = self.make(num_gates=12, ttg_map=list(range(12)), gate_status=[1]*12,
                         gate_color_rgb=[[1, 0, 0]]*12)
        self.press(v, 3)
        self.press(v, 12)
        for _ in range(3):
            v.get_encoder_state.return_value = v.ENCODER_DIFF_CW
            v.HMI_MMU_Menu()
        self.assertEqual(v._mmu_map_draft[11], 11)
        self.assertIn('[G12]', self.strings(v))
        self.press(v, 12)
        self.press(v, 1)
        v.get_encoder_state.return_value = v.ENCODER_DIFF_CCW
        v.HMI_MMU_Menu()
        self.assertEqual(v._mmu_map_draft[0], 0)

    def test_home_uses_full_canvas_but_keeps_original_dashboard_untouched(self):
        v, _ = self.make()
        self.assertIn((1, 0x0000, 0, 0, 271, 479), [c.args for c in v.lcd.Draw_Rectangle.call_args_list])
        self.assertIn('T2 > G3  LOADED', self.strings(v))
        v.lcd.reset_mock()
        v.Draw_Status_Area(True)
        v.lcd.assert_not_called()
        v.lcd.Draw_Rectangle.assert_not_called()
        v.lcd.Draw_String.assert_not_called()
        v.Draw_MMU_Menu()
        v.lcd.Draw_Rectangle.assert_not_called()
        v.lcd.Draw_String.assert_not_called()

    def test_browse_gates_and_open_details_never_moves(self):
        v, _ = self.make()
        self.press(v, 1)
        self.assertEqual(v._mmu_page, 'gates')
        self.press(v, 3)
        self.assertEqual(v._mmu_page, 'gate')
        self.assertEqual(v._mmu_gate, 2)
        v.pd.sendGCode.assert_not_called()
        v.pd.subscription.request.assert_not_called()
        self.assertIn('Unload', self.strings(v))

    def test_confirmation_defaults_to_cancel_and_cancel_does_not_send(self):
        v, _ = self.make()
        self.press(v, 2)
        self.assertEqual(v._mmu_page, 'confirm')
        self.assertEqual(v._mmu_selection, 1)
        self.assertEqual(v._mmu_confirmation.script, 'MMU_UNLOAD')
        self.press(v, 1)
        self.assertEqual(v._mmu_page, 'home')
        v.pd.subscription.request.assert_not_called()

    def test_only_explicit_confirm_submits_once_then_live_status(self):
        v, _ = self.make()
        self.press(v, 2)
        self.press(v, 2)
        self.assertEqual(v._mmu_page, 'status')
        v.pd.subscription.request.assert_called_once()
        self.assertEqual(v.pd.subscription.request.call_args.args,
                         ('printer.gcode.script', {'script': 'MMU_UNLOAD'}))
        self.press(v, 0)
        self.press(v, 2)
        self.assertEqual(v.pd.subscription.request.call_count, 1)

    def test_external_target_change_closes_confirm_and_never_dispatches(self):
        v, data = self.make()
        self.press(v, 2)
        data['status']['mmu']['gate'] = 1
        self.press(v, 2)
        self.assertEqual(v._mmu_page, 'confirm')
        self.assertIn('Unavailable', v._mmu_notice)
        v.pd.subscription.request.assert_not_called()

    def test_disabled_action_is_visible_but_not_executable(self):
        v, _ = self.make(enabled=False)
        self.assertIn('MMU DISABLED', self.strings(v))
        self.press(v, 2)
        self.assertEqual(v._mmu_page, 'home')
        v.pd.subscription.request.assert_not_called()

    def test_scroll_all_gates_and_operation_rows(self):
        count = 12
        v, _ = self.make(num_gates=count, gate_status=[1]*count,
                         gate_color_rgb=[[1,0,0]]*count, ttg_map=list(range(count)))
        self.press(v, 1)
        v._mmu_selection = 12
        v.Draw_MMU_Menu()
        self.assertIn('G12 --', self.strings(v))
        self.press(v, 12)
        self.assertEqual(v._mmu_gate, 11)
        v._mmu_selection = 8
        v.Draw_MMU_Menu()
        self.assertIn('Filament details', self.strings(v))
        self.press(v, 8)
        self.assertEqual(v._mmu_page, 'filament')

    def test_multiple_tools_are_not_misrepresented_on_spool(self):
        v, _ = self.make(ttg_map=[2,2,2,3])
        self.assertIn('T*', self.strings(v))
        self.assertIn('--', self.strings(v))

    def test_live_progress_sensors_unknown_and_absent_are_distinct(self):
        v, data = self.make(bowden_progress=68, action='Loading')
        self.press(v, 6)
        strings = self.strings(v)
        self.assertIn('Bowden: 68%', strings)
        self.assertIn('mmu_shared_exit: UNKNOWN/OFF', strings)
        self.assertIn('extruder: CLEAR', strings)
        self.assertIn('toolhead: TRIGGERED', strings)
        data['status']['mmu']['sensors'].pop('toolhead')
        data['status']['mmu']['bowden_progress'] = -1
        v.Draw_MMU_Menu()
        self.assertIn('toolhead: ABSENT', self.strings(v))
        self.assertIn('Stage: Loading', self.strings(v))

    def test_focus_change_does_not_erase_full_canvas_or_spools(self):
        v, _ = self.make()
        v.lcd.reset_mock()
        v.get_encoder_state.return_value = v.ENCODER_DIFF_CW
        v.HMI_MMU_Menu()
        self.assertTrue(v.lcd.Draw_Rectangle.called)
        for c in v.lcd.Draw_Rectangle.call_args_list:
            self.assertGreaterEqual(c.args[3], 5)
            self.assertNotEqual(c.args[2:], (0,0,271,479))
        self.assertNotIn('78%', self.strings(v))

    def test_back_restores_bottom_dashboard_and_home_cursor(self):
        v, _ = self.make()
        v.select_page.set(4)
        v.Draw_Status_Area = Mock()
        self.press(v, 0)
        self.assertEqual(v.checkkey, v.MainMenu)
        self.assertEqual(v.select_page.now, 4)
        v.Draw_Status_Area.assert_called_once_with(False)

    def test_disconnect_in_operation_keeps_error_and_does_not_replay(self):
        v, data = self.make()
        self.press(v, 2)
        self.press(v, 2)
        data['state'] = 'disconnected'
        v.pd.connection_error = 'offline'
        v._poll_mmu()
        self.assertEqual(v.pd.mmu_session.phase, 'error')
        self.assertIn('OFFLINE', self.strings(v))
        self.assertEqual(v.pd.subscription.request.call_count, 1)
        self.press(v, 1)
        self.assertEqual(v.pd.mmu_session.phase, 'idle')

    def test_recovery_manual_editor_is_draft_until_apply_and_confirm(self):
        v, _ = self.make(print_state='pause_locked', filament='Unknown', filament_pos=-1)
        v._mmu_open('recover')
        self.press(v, 2)
        self.assertEqual(v._mmu_page, 'manual')
        self.press(v, 1)
        v.get_encoder_state.return_value = v.ENCODER_DIFF_CW
        v.HMI_MMU_Menu()
        self.assertEqual(v._mmu_manual['tool'], 3)
        self.press(v, 1)
        self.press(v, 4)
        self.assertEqual(v._mmu_page, 'confirm')
        self.assertEqual(v._mmu_confirmation.script, 'MMU_RECOVER TOOL=3 GATE=2 LOADED=0')
        v.pd.subscription.request.assert_not_called()

    def test_bypass_load_is_locked_until_unloaded_and_selected(self):
        v, _ = self.make()
        self.press(v, 4)
        items = v._mmu_items(v.pd.mmu_session.state)
        self.assertEqual([i[3] for i in items], [True,False,False,False])
        self.press(v, 2)
        v.pd.subscription.request.assert_not_called()

    def test_print_state_update_does_not_take_over_mmu_page(self):
        v, _ = self.make()
        v.pd.status = 'paused'
        v._present_print_state()
        self.assertEqual(v.checkkey, v.MMUMenu)

    def test_mmu_error_pause_routes_directly_to_recovery(self):
        v, data = self.make(print_state='pause_locked', reason_for_pause='Filament missing')
        v.checkkey = v.PrintProcess
        v.pd.status = 'paused'
        v._present_print_state()
        self.assertEqual(v.checkkey, v.MMUMenu)
        self.assertEqual(v._mmu_page, 'recover')

    def test_all_page_primitives_stay_inside_lcd(self):
        v, _ = self.make()
        self.press(v, 2)  # Supplies a confirmation target.
        for page in v.MMU_TITLES:
            v._mmu_page = page
            v._mmu_selection = 1
            v._mmu_canvas_page = None
            v.lcd.reset_mock()
            v.Draw_MMU_Menu()
            for c in v.lcd.Draw_Rectangle.call_args_list:
                _, _, x0, y0, x1, y1 = c.args
                with self.subTest(page=page, coords=c.args):
                    self.assertTrue(0 <= x0 <= x1 < 272)
                    self.assertTrue(0 <= y0 <= y1 < 480)
            for c in v.lcd.Draw_String.call_args_list:
                x,y,value = c.args[-3:]
                self.assertGreaterEqual(x,0)
                self.assertLess(x,272)
                self.assertGreaterEqual(y,0)
                self.assertLess(y,480)

    def test_gate_removal_rejects_stale_enter_instead_of_selecting_new_target(self):
        v, data = self.make()
        self.press(v, 1)
        v._mmu_selection = 4
        data['status']['mmu']['num_gates'] = 2
        self.press(v, 4)
        self.assertEqual(v._mmu_page, 'gates')
        self.assertIn('Menu changed', v._mmu_notice)
        self.assertLessEqual(v._mmu_selection, 2)
        v.pd.subscription.request.assert_not_called()

    def test_changed_load_unload_button_cannot_execute_old_enter(self):
        v, data = self.make()
        data['status']['mmu'].update(filament='Unloaded', filament_pos=0)
        self.press(v, 2)
        self.assertEqual(v._mmu_page, 'home')
        self.assertIn('Menu changed', v._mmu_notice)
        v.pd.subscription.request.assert_not_called()

    def test_manual_draft_cannot_apply_after_external_state_change(self):
        v, data = self.make()
        v._mmu_open('recover')
        self.press(v, 2)
        data['status']['mmu']['tool'] = 1
        self.press(v, 4)
        self.assertEqual(v._mmu_page, 'manual')
        self.assertIn('reopen editor', v._mmu_notice)
        v.pd.subscription.request.assert_not_called()

    def test_pending_operation_cannot_leave_mmu_and_start_another_ui_action(self):
        v, _ = self.make()
        self.press(v, 2)
        self.press(v, 2)
        self.press(v, 0)  # Return to MMU home.
        self.press(v, 0)  # Exit is deferred until MMU completes.
        self.assertEqual(v.checkkey, v.MMUMenu)
        self.assertEqual(v._mmu_page, 'status')
        self.assertIn('Wait', v._mmu_notice)
        self.assertEqual(v.pd.subscription.request.call_count, 1)

    def test_uart_reconnect_rebuilds_current_page_and_cache(self):
        from test_regressions import ui
        from unittest.mock import patch
        v, _ = self.make()
        self.press(v, 1)
        v._closed = False
        v._settings = ('/dev/fake',)
        v._uart_online = False
        v._next_uart_retry = 0
        v._uart_epoch = 0
        v.HMI_Init = Mock()
        port = Mock()
        with patch.object(ui, 'T5UIC1_LCD', return_value=port):
            self.assertTrue(v._ensure_uart())
        self.assertEqual(v._mmu_page, 'gates')
        self.assertIn((1,0x0000,0,0,271,479), [c.args for c in port.Draw_Rectangle.call_args_list])
        self.assertIn('G1 PLA', [c.args[-1] for c in port.Draw_String.call_args_list])
        v.pd.subscription.request.assert_not_called()

    def test_offline_encoder_navigation_can_back_out_but_never_sends_motion(self):
        from ui_events import InputEvent
        v, data = self.make()
        v._closed = False
        v._uart_online = True
        v._uart_epoch = 1
        v._encoder_event = v.ENCODER_DIFF_NO
        v.get_encoder_state = lambda: v._encoder_event
        data['state'] = 'disconnected'
        data['error'] = 'offline'
        v._process_input(InputEvent('press',1,1,1))  # Old Gates selection changed safely.
        self.assertEqual(v.checkkey,v.MMUMenu)
        v._process_input(InputEvent('rotate',1,1,1))  # CCW to Back.
        v.Draw_Status_Area = Mock()
        v._process_input(InputEvent('press',1,1,1))
        if v.checkkey == v.MMUMenu:
            v._mmu_selection = 0
            v._process_input(InputEvent('press',1,1,1))
        self.assertEqual(v.checkkey,v.MainMenu)
        v.pd.subscription.request.assert_not_called()

    def test_tick_keeps_full_screen_and_updates_only_changed_telemetry(self):
        v, data = self.make()
        v.last_status = v.pd.status
        v._offline = False
        v.lcd.reset_mock()
        data['status']['extruder']['temperature'] = 201
        v.EachMomentUpdate()
        self.assertEqual(v.checkkey,v.MMUMenu)
        self.assertIn('Nozzle 201/205 C', self.strings(v))
        self.assertNotIn((1,0x0000,0,0,271,479), [c.args for c in v.lcd.Draw_Rectangle.call_args_list])
        self.assertFalse(any(c.args[3] == v.STATUS_Y for c in v.lcd.Draw_Rectangle.call_args_list))
