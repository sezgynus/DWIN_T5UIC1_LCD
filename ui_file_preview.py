"""File thumbnail confirmation screen; UART drawing stays on the UI owner."""
import logging
import time
from thumbnail_cache import ThumbnailCache


class FilePreviewMixin:
    def _sync_thumbnail_cache(self):
        if not hasattr(self, '_thumbnail_cache'):
            self._thumbnail_cache = ThumbnailCache(self.pd.client)
        # File size/mtime identify replacements without flushing unrelated images.
        revision = self.pd.state.file_revision
        stamp = (getattr(self, '_uart_epoch', 0), self.pd.state.epoch, revision,
                 self.pd.file_sort_revision, id(self.pd.files), getattr(self, '_file_paths', ()))
        if stamp == getattr(self, '_thumbnail_stamp', None):
            return
        self._thumbnail_stamp = stamp
        self._thumbnail_keys = {
            item['path']: (item['path'], item.get('modified'), item.get('size'),
                           revision if item.get('modified') is None else None)
            for item in self.pd.files
        }
        priority = tuple(self._thumbnail_keys[path] for path in getattr(self, '_file_paths', ())
                         if path in self._thumbnail_keys and not path.endswith('/'))[:5]
        self._thumbnail_cache.sync((getattr(self, '_uart_epoch', 0), self.pd.state.epoch),
                                   self._thumbnail_keys.values(), priority)

    def _poll_thumbnail_preload(self):
        self._sync_thumbnail_cache()
        self._thumbnail_cache.tick(self.lcd, chunks=2)

    def _open_file_preview(self, path):
        self._sync_thumbnail_cache()
        self._preview_path = path
        self._preview_epoch = self.pd.state.epoch
        self._preview_choice = 1  # Cancel is the safe initial selection.
        self._preview_cache_key = self._thumbnail_keys.get(path)
        self._thumbnail_cache.errors.pop(self._preview_cache_key, None)
        self._thumbnail_cache.retry_at.pop(self._preview_cache_key, None)
        self._preview_error = None
        self._preview_shown = False
        self._preview_cache_hit = self._thumbnail_cache.address(self._preview_cache_key) is not None
        self._preview_open_at = time.monotonic()
        self.checkkey = self.FilePreview
        if hasattr(self, '_loop'):
            self._loop.set_interval(.02)
        self.Draw_File_Preview()
        self._poll_file_preview()

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
        self._preview_shown = False
        self._preview_message = None
        if self._thumbnail_cache.address(self._preview_cache_key) is None:
            self._preview_message = self._preview_error or 'Loading thumbnail...'
            self._draw_menu_text(self._preview_message, 16, 225)
        self._preview_buttons()
        self.lcd.UpdateLCD()

    def _leave_file_preview(self):
        if hasattr(self, '_loop'):
            self._loop.set_interval(.02)
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
                self.Draw_File_Preview()
                self._draw_menu_text(self._preview_error, 16, 225)
                self.lcd.UpdateLCD()
            return
        self._sync_thumbnail_cache()
        cache = self._thumbnail_cache
        key = self._preview_cache_key
        if key not in cache.valid:
            self._preview_error = 'File changed; select again'
        elif not self._preview_shown:
            cache.tick(self.lcd, foreground=key, chunks=8)
            address = cache.address(key, touch=True)
            if address is not None:
                self.lcd.Draw_Rectangle(1, self.lcd.Color_Bg_Black, 0, 220, 271, 250)
                self.lcd.SRAM_Icon(72, 80, address)
                self._preview_shown = True
                self._preview_error = None
                self._preview_message = None
                logging.info('Thumbnail %s: SRAM cache %s, preview ready %.3fs',
                             self._preview_path, 'hit' if self._preview_cache_hit else 'miss',
                             time.monotonic()-self._preview_open_at)
            elif key in cache.errors:
                self._preview_error = 'No thumbnail'
        if self._preview_error and self._preview_error != self._preview_message:
            self.lcd.Draw_Rectangle(1, self.lcd.Color_Bg_Black, 0, 220, 271, 250)
            self._draw_menu_text(self._preview_error, 16, 225)
            self._preview_message = self._preview_error
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
                self._sync_thumbnail_cache()
                if hasattr(self, '_preview_cache_key') and self._preview_cache_key not in self._thumbnail_cache.valid:
                    raise ValueError('File changed; select again')
                future = self.pd.openAndPrintFile(self._preview_path)
                self._pending_start = (future, self.pd.state.epoch, time.monotonic())
                self._show_message('Starting print...')
                if hasattr(self, '_loop'):
                    self._loop.set_interval(2.0)
            except ValueError as error:
                self._show_message(str(error))
                self._start_error_visible = True
        self.lcd.UpdateLCD()
