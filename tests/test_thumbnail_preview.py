from io import BytesIO
from concurrent.futures import Future
from unittest.mock import Mock, patch
import unittest
from PIL import Image
from thumbnail_preview import image_runs, load_thumbnail
from test_capabilities import display, snapshot
import test_files


def png(size=(128,128), color='red'):
    stream=BytesIO();Image.new('RGBA',size,color).save(stream,format='PNG');return stream.getvalue()


class ThumbnailTests(unittest.TestCase):
    def test_solid_image_run_compression_and_rgb565(self):
        runs=image_runs(png())
        self.assertEqual(len(runs),128)
        self.assertEqual(runs[0],(0xF800,0,0,127,0))

    def test_aspect_ratio_transparency_and_black_background(self):
        runs=image_runs(png((200,100)))
        self.assertTrue(all(32<=r[2]<=95 for r in runs))
        self.assertEqual(image_runs(png(color=(0,0,0,0))),())

    def test_corrupt_and_oversized_images_rejected(self):
        with self.assertRaises(Exception):image_runs(b'invalid')
        with self.assertRaises(ValueError):image_runs(png((2100,2100)))

    def test_thumbnail_parent_path_encoding_and_download_limit(self):
        client=Mock();client.get.return_value={'result':{'thumbnails':[
            {'relative_path':'.thumbs/model.png','width':128,'height':128}]}}
        client.get_bytes.return_value=png()
        self.assertEqual(len(load_thumbnail(client,'parts a/model.gcode')),128)
        client.get.assert_called_once_with('/server/files/metadata?filename=parts%20a%2Fmodel.gcode')
        client.get_bytes.assert_called_once_with('/server/files/gcodes/parts%20a/.thumbs/model.png',max_bytes=2_000_000)

    def test_missing_thumbnail_and_root_escape_rejected(self):
        for thumbs in ([],[{'relative_path':'../../secret','width':128,'height':128}]):
            client=Mock();client.get.return_value={'result':{'thumbnails':thumbs}}
            with self.assertRaises(ValueError):load_thumbnail(client,'parts/model.gcode')
            client.get_bytes.assert_not_called()

    def make(self):
        view=test_files.FileTests().display(['a.gcode','b.gcode'])
        # Restore production preview entry, replacing the original start-contract shortcut.
        del view._open_file_preview
        view.get_encoder_state=Mock(return_value=view.ENCODER_DIFF_ENTER)
        view._preview_path='a.gcode';view._preview_epoch=view.pd.state.epoch
        view._preview_choice=1;view._preview_error=None
        view._preview_runs=None;view._preview_index=0
        view._preview_future=Future();view.checkkey=view.FilePreview
        view._loop=Mock()
        return view

    def test_selecting_file_opens_confirmation_without_print(self):
        view=self.make();view.checkkey=view.SelectFile;view.select_file.set(1)
        view.pd.openAndPrintFile=Mock()
        thread=Mock()
        with patch.dict(view._open_file_preview.__func__.__globals__, {'Thread':thread}):
            view.HMI_SelectFile()
        thread.return_value.start.assert_called_once()
        self.assertEqual(view.checkkey,view.FilePreview)
        self.assertEqual(view._preview_choice,1)
        view.pd.openAndPrintFile.assert_not_called()

    def test_cancel_keeps_file_selection_without_command(self):
        view=self.make();view.select_file.set(1)
        view.HMI_File_Preview()
        self.assertEqual(view.checkkey,view.SelectFile)
        self.assertEqual(view._file_paths[view.select_file.now-1],'a.gcode')
        view.pd.sendGCode.assert_not_called()
        view._loop.set_interval.assert_called_with(2.0)

    def test_draw_is_bounded_incremental_and_reconnect_restarts_cached_runs(self):
        view=self.make();view._preview_future.set_result(image_runs(png()))
        view._poll_file_preview();self.assertEqual(view._preview_index,64)
        for call in view.lcd.Draw_Line.call_args_list:
            _,x0,y0,x1,y1=call.args
            self.assertTrue(72<=x0<=x1<=199);self.assertTrue(80<=y0<=y1<=207)
        view.Draw_File_Preview();self.assertEqual(view._preview_index,0)
        view._poll_file_preview();view._poll_file_preview()
        self.assertEqual(view._preview_index,128)

    def test_missing_thumbnail_leaves_buttons_usable(self):
        view=self.make();view._preview_future.set_exception(ValueError('No thumbnail'))
        view._poll_file_preview()
        self.assertEqual(view._preview_error,'No thumbnail')
        self.assertIn('Cancel',[c.args[-1] for c in view.lcd.Draw_String.call_args_list])

    def test_print_revalidates_file_and_duplicate_press_does_not_resubmit(self):
        view=self.make();view._preview_choice=0
        view.pd.postREST=Mock(return_value=Future())
        view.HMI_File_Preview();view.HMI_File_Preview()
        view.pd.postREST.assert_called_once_with('/printer/print/start',json={'filename':'a.gcode'})

    def test_deleted_file_or_epoch_change_blocks_print(self):
        for changed_epoch in (False,True):
            view=self.make();view._preview_choice=0
            view.pd.openAndPrintFile=Mock()
            if changed_epoch:view._preview_epoch-=1
            else:view.pd.getREST.return_value={'result':[{'path':'b.gcode'}]}
            view.HMI_File_Preview();view.pd.openAndPrintFile.assert_not_called()
            self.assertTrue(view._start_error_visible)

    def test_late_completion_after_cancel_does_not_draw(self):
        view=self.make();view.HMI_File_Preview();view.lcd.reset_mock()
        view._preview_future.set_result(image_runs(png()))
        view._poll_file_preview();view.lcd.Draw_Line.assert_not_called()

    def test_large_source_preferred_over_tiny_icon(self):
        client=Mock();client.get.return_value={'result':{'thumbnails':[
            {'relative_path':'.thumbs/tiny.png','width':32,'height':32},
            {'relative_path':'.thumbs/large.png','width':400,'height':300}]}}
        client.get_bytes.return_value=png()
        load_thumbnail(client,'a.gcode')
        self.assertIn('large.png',client.get_bytes.call_args.args[0])
