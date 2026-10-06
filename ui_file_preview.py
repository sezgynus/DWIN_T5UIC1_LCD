"""File thumbnail confirmation screen; UART drawing stays on the UI owner."""
import logging
import time
from threading import Thread
from concurrent.futures import Future
from thumbnail_preview import load_thumbnail


class FilePreviewMixin:
    def _open_file_preview(self, path):
        self._preview_path = path
        self._preview_epoch = self.pd.state.epoch
        self._preview_choice = 1  # Cancel is the safe initial selection.
        self._preview_runs = None
        self._preview_index = 0
        self._preview_error = None
        prior = getattr(self, '_preview_worker', None)
        future = Future()
        self._preview_future = future
        if prior is not None and prior.is_alive():
            future.set_exception(ValueError('Thumbnail busy; retry'))
        else:
            client = self.pd.client
            def worker():
                try:
                    future.set_result(load_thumbnail(client, path))
                except Exception as error:
                    future.set_exception(error)
            self._preview_worker = Thread(target=worker, name='thumbnail-loader', daemon=True)
            self._preview_worker.start()
        self.checkkey = self.FilePreview
        if hasattr(self, '_loop'):
            self._loop.set_interval(.05)
        self.Draw_File_Preview()

    def _preview_buttons(self):
        for index, label in enumerate(('Print', 'Cancel')):
            x = 20 + index*126
            color = self.lcd.Color_Bg_Blue if self._preview_choice == index else self.lcd.Color_Bg_Black
            self.lcd.Draw_Rectangle(1, color, x, 290, x+106, 332)
            self.lcd.Draw_Rectangle(0, self.lcd.Color_White, x, 290, x+106, 332)
            self._draw_menu_text(label, x+(106-len(label)*8)//2, 303)

    def Draw_File_Preview(self):
        self.Clear_Main_Window()
        self.Draw_Title('Print preview')
        self._draw_menu_text(self._preview_path.rsplit('/', 1)[-1][:30], 16, 45)
        self._preview_index = 0
        self._preview_draw_at = time.monotonic()
        if self._preview_runs is None:
            self._draw_menu_text(self._preview_error or 'Loading thumbnail...', 16, 225)
        self._preview_buttons()
        self.lcd.UpdateLCD()

    def _leave_file_preview(self):
        if hasattr(self, '_loop'):
            self._loop.set_interval(2.0)
        self.checkkey = self.SelectFile
        self._refresh_file_snapshot()
        self.Draw_Print_File_Menu()
        self.lcd.UpdateLCD()

    def _poll_file_preview(self):
        if self.checkkey != self.FilePreview:
            return
        if self._preview_epoch != self.pd.state.epoch:
            if self._preview_error != 'Connection changed':
                self._preview_error = 'Connection changed'
                self._preview_runs = ()
                self.Draw_File_Preview()
                self._draw_menu_text(self._preview_error, 16, 225)
                self.lcd.UpdateLCD()
            return
        future = self._preview_future
        if self._preview_runs is None and future.done():
            try:
                self._preview_runs = future.result()
            except Exception as error:
                logging.info('Thumbnail unavailable: %s', error)
                self._preview_error = 'No thumbnail'
                self._preview_runs = ()
            self.Draw_File_Preview()
            if self._preview_error:
                self._draw_menu_text(self._preview_error, 16, 225)
        runs = self._preview_runs or ()
        stop = min(len(runs), self._preview_index + 64)
        for color, x0, y0, x1, y1 in runs[self._preview_index:stop]:
            self.lcd.Draw_Line(color, 72+x0, 80+y0, 72+x1, 80+y1)
        if stop == len(runs) and self._preview_index < stop:
            logging.info('Thumbnail %s: UART drawing %.3fs', self._preview_path,
                         time.monotonic()-self._preview_draw_at)
        self._preview_index = stop
        self.lcd.UpdateLCD()

    def HMI_File_Preview(self):
        event = self.get_encoder_state()
        if getattr(self, '_pending_start', None) or getattr(self, '_start_error_visible', False):
            if event == self.ENCODER_DIFF_ENTER and getattr(self, '_start_error_visible', False):
                self._start_error_visible = False
                self._leave_file_preview()
            return
        if event in (self.ENCODER_DIFF_CW, self.ENCODER_DIFF_CCW):
            self._preview_choice = 1 if event == self.ENCODER_DIFF_CW else 0
            self._preview_buttons()
        elif event == self.ENCODER_DIFF_ENTER:
            if self._preview_choice == 1:
                self._leave_file_preview()
                return
            try:
                if self.pd.state.epoch != self._preview_epoch:
                    raise ValueError('Connection changed; select file again')
                paths = self.pd.GetFiles(refresh=True)
                if self._preview_path not in paths or self.pd.file_error:
                    raise ValueError('File unavailable; select again')
                future = self.pd.openAndPrintFile(self._preview_path)
                self._pending_start = (future, self.pd.state.epoch, time.monotonic())
                self._show_message('Starting print...')
                if hasattr(self, '_loop'):
                    self._loop.set_interval(2.0)
            except ValueError as error:
                self._show_message(str(error))
                self._start_error_visible = True
        self.lcd.UpdateLCD()
