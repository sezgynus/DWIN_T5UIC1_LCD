"""Phase 2 render baseline workloads.

The packet/byte totals are deliberately reported rather than frozen as assertions:
future optimization commits are expected to reduce them. Tests only protect the
measurement contract and ensure each workload still exercises real UART output.
"""
import unittest
from unittest.mock import patch

from render_metrics import RenderMetrics
from test_capabilities import display, snapshot
from test_regressions import ui
from test_t5uic1_driver import driver


class RenderBaselineTests(unittest.TestCase):
    def screen(self):
        result = display(snapshot())
        result.lcd = driver()
        # Startup owns persistent atlas synchronization. Baseline rendering must
        # model the normal post-startup state without performing Flash writes.
        result.lcd._atlas_synced = True
        result.lcd._atlas_virtual_areas_loaded = True
        result.lcd._virtual_area_pictures = {0: 14}
        result.last_status = result.pd.status
        result._drawn_mmu_state = None
        return result

    def measure(self, name, screen, operation):
        metrics = RenderMetrics.measure(screen.lcd, operation)
        print('RENDER_BASELINE %s: %s' % (name, metrics.summary()))
        self.assertGreater(metrics.packets, 0)
        self.assertGreater(metrics.bytes, 0)
        return metrics

    def test_status_dashboard_full_redraw(self):
        screen = self.screen()
        with patch.object(ui.time, 'monotonic', return_value=0):
            metrics = self.measure(
                'status_dashboard_full_redraw', screen,
                lambda: (screen.Draw_Status_Area(True), screen.lcd.update()))
        self.assertIn((0x05, 1), metrics.opcodes)
        self.assertEqual(metrics.refreshes, 1)

    def test_print_progress_periodic_redraw(self):
        screen = self.screen()
        metrics = self.measure(
            'print_progress_periodic_redraw', screen,
            lambda: (screen.Draw_Print_ProgressBar(42.0), screen.lcd.update()))
        self.assertEqual(metrics.refreshes, 1)

    def test_print_time_periodic_redraw(self):
        screen = self.screen()
        screen.pd.job_Info = {
            'virtual_sdcard': {'is_active': True, 'progress': .42},
            'print_stats': {'state': 'printing', 'print_duration': 3600},
        }
        screen.pd.remain = lambda: 7200
        metrics = self.measure(
            'print_time_periodic_redraw', screen,
            lambda: (
                screen.Draw_Print_ProgressElapsed(),
                screen.Draw_Print_ProgressRemain(),
                screen.lcd.update(),
            ))
        self.assertEqual(metrics.refreshes, 1)

    def test_prepare_menu_full_draw(self):
        screen = self.screen()
        metrics = self.measure(
            'prepare_menu_full_draw', screen,
            lambda: (screen.Draw_Prepare_Menu(), screen.lcd.update()))
        self.assertEqual(metrics.refreshes, 1)

    def test_control_menu_full_draw(self):
        screen = self.screen()
        metrics = self.measure(
            'control_menu_full_draw', screen,
            lambda: (screen.Draw_Control_Menu(), screen.lcd.update()))
        self.assertEqual(metrics.refreshes, 1)


class RenderMetricsTests(unittest.TestCase):
    def test_measurement_is_scoped_to_new_frames(self):
        lcd = driver()
        lcd.clear(0)
        metrics = RenderMetrics.measure(
            lcd, lambda: (lcd.draw_line(0xFFFF, 0, 0, 10, 10), lcd.update()))
        self.assertEqual(metrics.packets, 2)
        self.assertEqual(metrics.bytes,
                         sum(len(frame) for frame in lcd.serial.frames[-2:]))
        self.assertEqual(metrics.refreshes, 1)
        self.assertEqual(dict(metrics.opcodes), {0x03: 1, 0x3D: 1})
        self.assertGreaterEqual(metrics.duration_ms, 0)


if __name__ == '__main__':
    unittest.main()
