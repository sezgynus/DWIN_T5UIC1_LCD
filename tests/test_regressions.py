"""Behavioral regression contracts; no GPIO, serial port or server required."""
import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


def load_application():
    # Only import-time dependencies are replaced. Application methods stay real.
    dependencies = {}
    for name in ('requests', 'requests.exceptions', 'multitimer', 'encoder',
                 'gpiozero', 'gpiozero.pins', 'gpiozero.pins.lgpio', 'serial'):
        dependencies[name] = types.ModuleType(name)
    dependencies['requests.exceptions'].ConnectionError = ConnectionError
    dependencies['encoder'].Encoder = Mock()
    dependencies['gpiozero'].Button = Mock()
    dependencies['gpiozero'].Device = types.SimpleNamespace(pin_factory=None)
    dependencies['gpiozero.pins.lgpio'].LGPIOFactory = Mock()
    with patch.dict(sys.modules, dependencies):
        backend = importlib.import_module('printerInterface')
        ui = importlib.import_module('dwinlcd')
    return backend, ui


backend, ui = load_application()


class RegressionContracts(unittest.TestCase):
    def printer(self):
        printer = backend.PrinterData.__new__(backend.PrinterData)
        printer.sendGCode = Mock()
        printer.postREST = Mock()
        printer.current_position = backend.xyze_t()
        printer.HMI_ValueStruct = backend.HMI_value_t()
        printer.HMI_flag = backend.HMI_Flag_t()
        printer.job_Info = {
            'virtual_sdcard': {'is_active': False, 'progress': 0.42},
            'print_stats': {'state': 'paused', 'print_duration': 120.0},
        }
        return printer

    def display(self, mode):
        display = ui.DWIN_LCD.__new__(ui.DWIN_LCD)
        display.pd = self.printer()
        display.pd.HMI_ValueStruct.show_mode = mode
        display.pd.HMI_ValueStruct.E_Temp = 205
        display.pd.HMI_ValueStruct.Bed_Temp = 65
        display.lcd = Mock()
        display.get_encoder_state = Mock(return_value=display.ENCODER_DIFF_ENTER)
        return display

    def test_pause_state_is_reported(self):
        self.assertTrue(self.printer().printingIsPaused())

    def test_resume_uses_absolute_endpoint_path(self):
        printer = self.printer()
        printer.resume_job()
        printer.postREST.assert_called_once_with('/printer/print/resume', json=None)

    @unittest.expectedFailure
    def test_paused_progress_is_retained(self):
        self.assertAlmostEqual(self.printer().getPercent(), 42.0)

    @unittest.expectedFailure
    def test_paused_duration_is_retained(self):
        self.assertEqual(self.printer().duration(), 120.0)

    def test_unhomed_axes_clear_previous_flags(self):
        printer = self.printer()
        printer.klippy_callback('{"result":{"status":{"toolhead":{"homed_axes":"xyz"}}}}')
        printer.klippy_callback('{"result":{"status":{"toolhead":{"homed_axes":""}}}}')
        self.assertFalse(printer.current_position.home_x)
        self.assertFalse(printer.current_position.home_y)
        self.assertFalse(printer.current_position.home_z)

    @unittest.expectedFailure
    def test_temperature_menu_applies_hotend_target(self):
        display = self.display(-1)
        display.HMI_ETemp()
        display.pd.sendGCode.assert_called_once_with('M104 T0 S205')

    @unittest.expectedFailure
    def test_temperature_menu_applies_bed_target(self):
        display = self.display(-1)
        display.HMI_BedTemp()
        display.pd.sendGCode.assert_called_once_with('M140 S65')

    @unittest.expectedFailure
    def test_tune_applies_hotend_target(self):
        display = self.display(0)
        display.HMI_ETemp()
        display.pd.sendGCode.assert_called_once_with('M104 T0 S205')

    @unittest.expectedFailure
    def test_tune_applies_bed_target(self):
        display = self.display(0)
        display.HMI_BedTemp()
        display.pd.sendGCode.assert_called_once_with('M140 S65')


class BackendConnectionTests(unittest.TestCase):
    def test_initialization_does_not_open_klipper_socket(self):
        with patch.object(backend, 'MoonrakerClient') as transport, patch.object(backend, 'MoonrakerSubscription') as subscription:
            printer = backend.PrinterData(URL='http://localhost:7125', timeout=2)
            transport.assert_called_once_with('http://localhost:7125', '', 2)
            self.assertIsNone(printer.status)
            printer.close()
            transport.return_value.close.assert_called_once()

    def test_missing_snapshot_preserves_previous_state(self):
        with patch.object(backend, 'MoonrakerClient'), patch.object(backend, 'MoonrakerSubscription'):
            printer = backend.PrinterData()
        printer.check_command_results = Mock()
        printer.subscription.snapshot.return_value = {'state': 'ready', 'status': {}}
        printer.status = 'paused'
        self.assertFalse(printer.update_variable())
        self.assertEqual(printer.status, 'paused')
        self.assertIsNotNone(printer.connection_error)

    def test_offline_command_is_rejected_without_network(self):
        with patch.object(backend, 'MoonrakerClient') as transport, patch.object(backend, 'MoonrakerSubscription') as subscription:
            printer = backend.PrinterData()
            printer.connection_error = 'Disconnected'
            future = printer.postREST('/printer/print/start', {'filename': 'test.gcode'})
            with self.assertRaises(backend.MoonrakerError):
                future.result()
            transport.return_value.post.assert_not_called()

    def test_ready_snapshot_updates_without_http_polling(self):
        with patch.object(backend, 'MoonrakerClient'), patch.object(backend, 'MoonrakerSubscription'):
            printer = backend.PrinterData()
        printer.check_command_results = Mock()
        printer.getREST = Mock(side_effect=AssertionError('status must not poll HTTP'))
        printer.subscription.snapshot.return_value = {
            'state': 'ready', 'file_revision': 1,
            'status': {
                'toolhead': {'position': [1, 2, 3, 4], 'axis_maximum': [220, 220, 250, 0],
                             'homed_axes': 'xy'},
                'gcode_move': {'homing_origin': [0, 0, 0.1, 0],
                               'absolute_coordinates': True, 'absolute_extrude': False},
                'print_stats': {'state': 'paused', 'filename': 'test.gcode'},
                'virtual_sdcard': {'is_active': False, 'progress': 0.4},
                'extruder': {'temperature': 200, 'target': 205},
            },
        }
        self.assertTrue(printer.update_variable())
        self.assertEqual(printer.status, 'paused')
        self.assertFalse(printer.absolute_extrude)
        self.assertFalse(printer.current_position.home_z)
        self.assertEqual(printer.thermalManager['temp_hotend'][0]['target'], 205)
        printer.getREST.assert_not_called()

    def test_backend_guard_rejects_new_epoch(self):
        with patch.object(backend, 'MoonrakerClient') as transport, patch.object(backend, 'MoonrakerSubscription'):
            printer = backend.PrinterData()
        printer.subscription.snapshot.return_value = {'state': 'ready', 'epoch': 1}
        printer.postREST('/printer/print/start', {'filename': 'test.gcode'})
        guard = transport.return_value.post.call_args.kwargs['guard']
        self.assertTrue(guard())
        printer.subscription.snapshot.return_value = {'state': 'ready', 'epoch': 2}
        self.assertFalse(guard())


if __name__ == '__main__':
    unittest.main()
