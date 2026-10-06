"""Marlin ProUI-style four-corner result view with Klipper turn instructions."""


class ScrewsTiltMixin:
    def Draw_Screws_Menu(self):
        self.Clear_Main_Window()
        self.Draw_Title('Screws Tilt Adjust')
        self.Draw_Menu_Line(0, self.ICON_Back, 'Back')
        self.Draw_Menu_Line(1, self.ICON_SetEndTemp, 'Calculate')
        self.Draw_Menu_Cursor(getattr(self, '_screws_selection', 0))
        self.lcd.UpdateLCD()

    def _screws_text(self, text, y, color=None, font=None, width=8):
        self.lcd.Draw_String(False, False, font or self.lcd.font8x16,
                             self.lcd.Color_White if color is None else color,
                             self.lcd.Color_Bg_Black, max(0, (272 - len(text) * width) // 2), y, text)

    def Draw_Screws_Result(self):
        self.Clear_Main_Window()
        self.Draw_Title('Screws Tilt Adjust')
        session = self.pd.screws_tilt
        self.lcd.Draw_Rectangle(0, 0x7BEF, 25, 55, 247, 277)
        base_z = next((v['z'] for v in session.results.values() if v['is_base']), 0)
        for key, x, y, _ in session.corners:
            value = session.results.get(key)
            # Scanlines avoid the slow point-by-point legacy circle fill.
            delta = 0 if value is None else value['z'] - base_z
            color = 0x7BEF if value is None else 0x07E0 if abs(delta) < .025 else 0xF800 if delta > 0 else 0x001F
            radius = 14 if value is None else max(5, min(23, round(14 + delta * 45)))
            for dy in range(-radius, radius + 1):
                dx = int((radius * radius - dy * dy) ** .5)
                self.lcd.Draw_Rectangle(1, color, x - dx, y + dy, x + dx, y + dy)
            labels = ('...',) if value is None else ('Base',) if value['is_base'] else (value['sign'], value['adjust'])
            ty = 62 if y < 166 else 235
            for line, label in enumerate(labels):
                # Place labels inwards on black; leave the maximum circle radius clear.
                tx = 52 if x < 136 else 220 - len(label) * 8
                self.lcd.Draw_String(False, False, self.lcd.font8x16, self.lcd.Color_White,
                                     self.lcd.Color_Bg_Black, tx, ty + line * 20, label)
        if session.pending:
            self._screws_text(session.message, 140)
        elif session.phase != 'complete':
            self._screws_text(session.message[:32], 140, font=self.lcd.font6x12, width=6)
        elif session.leveled:
            self._screws_text('Corners leveled', 140)
            self._screws_text('Tolerance achieved!', 160)
        else:
            value = session.results[session.recommendation]
            name = next(c[3] for c in session.corners if c[0] == session.recommendation)
            self._screws_text('Adjust ' + name, 140)
            self._screws_text(value['sign'] + ' ' + value['adjust'], 166,
                              color=0x07E0, font=self.lcd.font10x20, width=10)
        if not session.pending:
            self.lcd.Draw_Rectangle(1, 0x03B5, 86, 305, 186, 343)
            self._screws_text('Continue', 316)
        self.lcd.UpdateLCD()

    def HMI_Screws_Tilt(self):
        event = self.get_encoder_state()
        if self.checkkey == self.ScrewsTiltResult:
            if not self.pd.screws_tilt.pending and event == self.ENCODER_DIFF_ENTER:
                self.checkkey = self.ScrewsTiltMenu
                self.Draw_Screws_Menu()
            return
        selection = getattr(self, '_screws_selection', 0)
        if event == self.ENCODER_DIFF_CW:
            self._screws_selection = min(1, selection + 1)
        elif event == self.ENCODER_DIFF_CCW:
            self._screws_selection = max(0, selection - 1)
        elif event == self.ENCODER_DIFF_ENTER:
            if selection == 0:
                self.checkkey = self.Prepare
                self.Draw_Prepare_Menu()
                return
            try:
                self.pd.screws_tilt.start()
            except ValueError as error:
                self._show_message(str(error))
                return
            self.checkkey = self.ScrewsTiltResult
            self.Draw_Screws_Result()
            return
        if event != self.ENCODER_DIFF_NO:
            self.Draw_Screws_Menu()

    def _poll_screws_tilt(self):
        session = self.pd.screws_tilt
        previous = (session.phase, session.message)
        session.update()
        if self.checkkey == self.ScrewsTiltResult and previous != (session.phase, session.message):
            self.Draw_Screws_Result()
