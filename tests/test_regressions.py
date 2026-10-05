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

    @unittest.expectedFailure
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

    @unittest.expectedFailure
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


if __name__ == '__main__':
    unittest.main()
