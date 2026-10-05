from concurrent.futures import Future
import unittest
from unittest.mock import Mock, patch

from test_regressions import backend, ui
MoonrakerError = backend.MoonrakerError
from test_capabilities import snapshot, printer, display


class FileTests(unittest.TestCase):
    def backend(self, paths):
        result = printer(snapshot())
        result.getREST = Mock(return_value={'result': [{'path': path} for path in paths]})
        result.GetFiles()
        return result

    def display(self, paths):
        result = display(snapshot())
        result.pd = self.backend(paths)
        result.lcd.DWIN_WIDTH = 272
        result._refresh_file_snapshot()
        result._show_message = Mock()
        result.Goto_PrintProcess = Mock()
        result.Goto_MainMenu = Mock()
        result.Draw_Status_Area = Mock()
        result._offline = False
        result.checkkey = result.SelectFile
        result.last_status = result.pd.status
        return result

    def test_empty_list_is_cached_and_navigation_does_not_fetch(self):
        result = self.display([])
        result.get_encoder_state = Mock(return_value=result.ENCODER_DIFF_CW)
        for _ in range(10):
            result.HMI_SelectFile()
        result.pd.getREST.assert_called_once()
        self.assertEqual(result.select_file.now, 0)

    def test_selection_survives_insert_and_returns_back_after_delete(self):
        result = self.display(['b.gcode', 'c.gcode'])
        result.select_file.set(2)
        result.pd.getREST.return_value = {'result': [{'path': 'a.gcode'}, {'path': 'c.gcode'}]}
        result.pd._files_loaded = False
        result._refresh_file_snapshot()
        self.assertEqual(result._file_paths[result.select_file.now - 1], 'c.gcode')
        result.pd.getREST.return_value = {'result': [{'path': 'a.gcode'}]}
        result.pd._files_loaded = False
        result._refresh_file_snapshot()
        self.assertEqual(result.select_file.now, 0)

    def test_failed_refresh_preserves_list_and_blocks_start(self):
        result = self.backend(['a.gcode'])
        result.getREST.side_effect = MoonrakerError('timeout')
        self.assertEqual(result.GetFiles(refresh=True), ('a.gcode',))
        self.assertIsNone(result.connection_error)
        result.postREST = Mock()
        with self.assertRaises(ValueError):
            result.openAndPrintFile('a.gcode')
        result.postREST.assert_not_called()

    def test_start_addresses_path_and_waits_for_result_and_status(self):
        result = self.display(['a.gcode'])
        future = Future()
        result.pd.postREST = Mock(return_value=future)
        result.select_file.set(1)
        result.get_encoder_state = Mock(return_value=result.ENCODER_DIFF_ENTER)
        result.HMI_SelectFile()
        result.HMI_SelectFile()
        result.pd.postREST.assert_called_once_with('/printer/print/start', json={'filename': 'a.gcode'})
        self.assertEqual(result.pd.file_name, '')
        result.Goto_PrintProcess.assert_not_called()
        future.set_result({'result': 'ok'})
        self.assertTrue(result._poll_print_start())
        result.pd.status = 'printing'
        result.pd.job_Info['print_stats'] = {'state': 'printing'}
        self.assertFalse(result._poll_print_start())
        result.Goto_PrintProcess.assert_called_once()

    def test_start_failure_cancel_and_epoch_change_are_not_retried(self):
        for outcome in ('failure', 'cancel', 'epoch'):
            result = self.display(['a.gcode'])
            future = Future()
            result.pd.postREST = Mock(return_value=future)
            result.select_file.set(1)
            result.get_encoder_state = Mock(return_value=result.ENCODER_DIFF_ENTER)
            result.HMI_SelectFile()
            if outcome == 'failure':
                future.set_exception(MoonrakerError('denied'))
            elif outcome == 'cancel':
                future.cancel()
            else:
                pending = result._pending_start
                result._pending_start = (pending[0], pending[1] - 1, pending[2])
            result._poll_print_start()
            result._poll_print_start()
            self.assertTrue(result._start_error_visible)
            self.assertIsNone(result._pending_start)
            result.Goto_PrintProcess.assert_not_called()
            result.pd.postREST.assert_called_once()

    def test_success_without_status_times_out_without_retry(self):
        result = self.display(['a.gcode'])
        future = Future()
        future.set_result({'result': 'ok'})
        result._pending_start = (future, result.pd.state.epoch, 0)
        with patch.object(ui.time, 'monotonic', return_value=31):
            result._poll_print_start()
        self.assertTrue(result._start_error_visible)
        result.Goto_PrintProcess.assert_not_called()

    def test_obsolete_index_and_unlisted_path_are_rejected(self):
        result = self.backend(['a.gcode'])
        for path in (0, 'deleted.gcode'):
            with self.assertRaises(ValueError):
                result.openAndPrintFile(path)

    def test_renderer_scrolls_only_snapshot_without_network(self):
        result = self.display([f'{i:02}.gcode' for i in range(12)])
        result.select_file.set(10)
        result.index_file = 10
        result.Draw_Menu_Line = Mock()
        result.Redraw_SD_List()
        self.assertEqual(result.Draw_Menu_Line.call_count, result.TROWS)
        self.assertEqual(result.Draw_Menu_Line.call_args.args[-1], '09.gcode')
        result.pd.getREST.assert_called_once()
