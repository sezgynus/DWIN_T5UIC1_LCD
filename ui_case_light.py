"""Case-light screen rendering and interaction mixin."""

class CaseLightMixin:
    def Draw_Case_Light_Menu(self):
        self.Clear_Main_Window()
        self.Draw_Title('Case Light')
        self.Draw_Back_First(self.select_light.now == 0)
        self.Draw_Menu_Line(1, self.ICON_CaseLight, 'Light')
        self.Draw_Menu_Line(2, self.ICON_CaseLight, 'Brightness')
        if self.select_light.now:
            self.Draw_Menu_Cursor(self.select_light.now)
        self.lcd.Draw_String(False, True, self.lcd.font8x16, self.lcd.Color_White,
                             self.lcd.Color_Bg_Black, 224, self.MBASE(1),
                             '[X]' if getattr(self, '_case_light_on', False) else '[ ]')
        self.lcd.Draw_IntValue(True, True, 0, self.lcd.font8x16,
                               self.lcd.Color_White, self.lcd.Color_Bg_Black,
                               3, 208, self.MBASE(2), getattr(self, '_case_light_brightness', 0))
        self.lcd.Draw_String(False, True, self.lcd.font8x16, self.lcd.Color_White,
                             self.lcd.Color_Bg_Black, 232, self.MBASE(2), '%')

    def _poll_case_light_query(self):
        if not getattr(self, '_case_light_query_pending', False):
            return False
        import re
        while True:
            response = self.pd.pop_gcode_response()
            if response is None:
                return False
            match = re.search(r'Light is (ON|OFF),\s*Brightness=(\d+)', response, re.IGNORECASE)
            if match:
                self._case_light_on = match.group(1).upper() == 'ON'
                raw_brightness = max(0, min(255, int(match.group(2))))
                self._case_light_brightness = int(round(raw_brightness * 100.0 / 255.0))
                self._case_light_query_pending = False
                if self.checkkey == self.CaseLight:
                    self.Draw_Case_Light_Menu()
                    self.lcd.UpdateLCD()
                return True

    def _refresh_case_light_state(self):
        # Commit displayed light state only after a successful command and a
        # fresh M355 query response; never optimistically change the UI.
        self._case_light_query_pending = True
        self.pd.query_case_light()

    def HMI_Case_Light(self):
        event = self.get_encoder_state()
        if event == self.ENCODER_DIFF_CW:
            self.select_light.inc(3)
            self.Draw_Case_Light_Menu()
        elif event == self.ENCODER_DIFF_CCW:
            self.select_light.dec()
            self.Draw_Case_Light_Menu()
        elif event == self.ENCODER_DIFF_ENTER:
            if self.select_light.now == 0:
                self.checkkey = self.Control
                self.select_control.set(self.CONTROL_CASE_LIGHT)
                self.Draw_Control_Menu()
            elif self.select_light.now == 1:
                target = not getattr(self, '_case_light_on', False)
                self._action(
                    "Case light",
                    lambda: self.pd.sendGCode('M355 S{}'.format(1 if target else 0)),
                    on_accept=self._refresh_case_light_state)
            else:
                self.checkkey = self.CaseLightBrightness
                self._case_light_brightness_target = getattr(self, '_case_light_brightness', 0)
                self.lcd.Draw_IntValue(True, True, 0, self.lcd.font8x16,
                                       self.lcd.Color_White, self.lcd.Select_Color,
                                       3, 208, self.MBASE(2), self._case_light_brightness_target)
        self.lcd.UpdateLCD()

    def HMI_Case_Light_Brightness(self):
        event = self.get_encoder_state()
        if event == self.ENCODER_DIFF_ENTER:
            target = self._case_light_brightness_target
            raw_brightness = int(round(target * 255.0 / 100.0))
            self.checkkey = self.CaseLight
            self._action(
                "Case light brightness",
                lambda: self.pd.sendGCode('M355 P{}'.format(raw_brightness)),
                on_accept=self._refresh_case_light_state)
        elif event in (self.ENCODER_DIFF_CW, self.ENCODER_DIFF_CCW):
            delta = self._encoder_move_value if event == self.ENCODER_DIFF_CW else -self._encoder_move_value
            self._case_light_brightness_target = max(0, min(100, self._case_light_brightness_target + delta))
            self.lcd.Draw_IntValue(True, True, 0, self.lcd.font8x16,
                                   self.lcd.Color_White, self.lcd.Select_Color,
                                   3, 208, self.MBASE(2), self._case_light_brightness_target)
        self.lcd.UpdateLCD()

