"""MMU menu and Happy Hare home-screen rendering mixin."""

class MMUViewMixin:
    def Draw_MMU_Home_Icon(self, x, y, selected):
        # Three filament reels fit the same tile as the stock Home icons.
        edge = self.lcd.Color_White if selected else 0x8410
        colors = (0xF800, 0x07E0, 0x001F) if selected else (0x7800, 0x03E0, 0x0010)
        for lane, color in enumerate(colors):
            left = x + 16 + lane * 27
            self.lcd.draw_rectangle(1, color, left+4, y+22, left+18, y+49)
            for flange in (left, left+19):
                self.lcd.draw_rectangle(1, edge, flange, y+16, flange+3, y+55)
            self.lcd.draw_line(color, left+11, y+56, left+11, y+62)
        self.lcd.draw_line(edge, x+27, y+62, x+81, y+62)

    def Draw_MMU_Menu(self):
        self.Clear_Main_Window()
        self.Draw_Title('MMU')
        self.Draw_Back_First(True)

    def HMI_MMU_Menu(self):
        if self.get_encoder_state() == self.ENCODER_DIFF_ENTER:
            self.Goto_MainMenu()
            self.lcd.update()

    @staticmethod
    def _rgb565(rgb):
        r, g, b = (int(round(max(0.0, min(1.0, value)) * 31)) for value in rgb)
        # Green has 6 bits in RGB565.
        g = int(round(max(0.0, min(1.0, rgb[1])) * 63))
        return (r << 11) | (g << 5) | b

    def Draw_MMU_Status(self):
        mmu = self.pd.mmu
        if not mmu:
            return
        count = mmu['num_gates']
        active = mmu['gate']
        # Fill nearly the entire strip above the main menu icons.
        left, top, width = 8, 39, 256
        gap = 5 if count <= 4 else 2 if count <= 8 else 1
        if count > 32:
            gap = 0
        slot = max(1, min(60, (width - gap * (count - 1)) // count))
        total = slot * count + gap * (count - 1)
        start = left + max(0, (width - total) // 2)
        title = str(mmu.get('name') or 'MMU')[:22]
        title_x = max(4, (self.lcd.DWIN_WIDTH - 6 * len(title)) // 2)
        self.lcd.draw_text(False, True, self.lcd.font6x12,
                             self.lcd.Color_White, self.lcd.Color_Bg_Black,
                             title_x, 32, title)

        percentages = mmu.get('remaining_percent', ())
        for gate in range(count):
            x = start + gate * (slot + gap)
            status = mmu['gate_status'][gate]
            color = self._rgb565(mmu['gate_color_rgb'][gate]) if status > 0 else 0x8410
            cx = x + slot // 2
            flange = 0x9B46
            flange_edge = 0xD58A
            # Keep lane spacing unchanged, but narrow the reel itself so its
            # height-to-width ratio resembles a physical filament spool.
            reel_w = min(max(8, int(slot * 0.70)), max(1, slot - 2))
            reel_x = x + (slot - reel_w) // 2
            flange_w = max(1, min(max(2, reel_w // 9), max(1, (reel_w - 2) // 2)))
            body_left = reel_x + flange_w
            body_right = reel_x + reel_w - flange_w - 1
            y0, y1 = top + 13, top + 52

            # Warm cardboard/wood flanges stand out against the black UI.
            self.lcd.draw_rectangle(1, flange, reel_x + 1, top + 7,
                                    reel_x + flange_w, top + 58)
            self.lcd.draw_rectangle(0, flange_edge, reel_x + 1, top + 7,
                                    reel_x + flange_w, top + 58)
            self.lcd.draw_rectangle(1, flange, reel_x + reel_w - flange_w - 1, top + 7,
                                    reel_x + reel_w - 2, top + 58)
            self.lcd.draw_rectangle(0, flange_edge, reel_x + reel_w - flange_w - 1, top + 7,
                                    reel_x + reel_w - 2, top + 58)
            self.lcd.draw_rectangle(1, color, body_left, y0, body_right, y1)

            winding = self.lcd.Color_White if sum(mmu['gate_color_rgb'][gate]) < 0.7 else flange
            for line_x in range(body_left + 5, body_right, 7):
                self.lcd.draw_line(winding, line_x, y0, line_x, y1)

            percent = percentages[gate] if gate < len(percentages) else None
            # Percent text needs enough horizontal room. Compact high-gate
            # layouts prioritize distinct lanes over overlapping text.
            if slot >= 28:
                pct = '--' if percent is None else '%d%%' % percent
                # Black backing keeps the percentage readable on white/yellow filament.
                pct_w = 6 * len(pct) + 4
                self.lcd.draw_rectangle(1, self.lcd.Color_Bg_Black,
                                        cx - pct_w // 2, top + 27,
                                        cx + pct_w // 2, top + 41)
                self.lcd.draw_text(False, True, self.lcd.font6x12,
                                     self.lcd.Color_White, self.lcd.Color_Bg_Black,
                                     cx - 3 * len(pct), top + 28, pct)

            label = str(gate + 1)
            label_w = max(1, min(38, slot - 2 if slot > 2 else slot))
            lx0, lx1 = cx - label_w // 2, cx + label_w // 2
            exit_leds = mmu.get('exit_led_rgb', ())
            led_color = None
            if gate < len(exit_leds):
                rgb = exit_leds[gate]
                peak = max(rgb)
                # Mirror the LED hue, not its physical brightness.  Happy Hare
                # may deliberately drive a color at low intensity (e.g. red
                # at 0.1), which is too dark on the LCD if copied literally.
                normalized_rgb = (tuple(channel / peak for channel in rgb)
                                  if peak > 0 else rgb)
                led_color = self._rgb565(normalized_rgb)
            active_green = 0x07E0
            indicator = led_color if led_color is not None else (
                active_green if gate == active else self.lcd.Line_Color)
            # Every lane mirrors its live Happy Hare exit LED continuously.
            # Black/off LEDs therefore render as black rather than falling back.
            label_bg = indicator
            border = indicator
            self.lcd.draw_rectangle(1, label_bg, lx0, top + 64, lx1, top + 78)
            self.lcd.draw_rectangle(0, border, lx0, top + 64, lx1, top + 78)
            # Choose black or white text for maximum contrast against
            # the live lane color.  This keeps bright green/yellow/cyan lane
            # numbers readable without sacrificing dark-color visibility.
            r5 = (label_bg >> 11) & 0x1F
            g6 = (label_bg >> 5) & 0x3F
            b5 = label_bg & 0x1F
            luminance = (299 * r5 * 255 // 31 +
                         587 * g6 * 255 // 63 +
                         114 * b5 * 255 // 31) // 1000
            label_fg = 0x0000 if luminance >= 140 else self.lcd.Color_White
            self.lcd.draw_text(False, True, self.lcd.font6x12,
                                 label_fg, label_bg,
                                 cx - 3 * len(label), top + 65, label)

