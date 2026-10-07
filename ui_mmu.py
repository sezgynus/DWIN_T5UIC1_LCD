"""MMU menu and Happy Hare home-screen rendering mixin."""

class MMUViewMixin:
    def Draw_MMU_Home_Icon(self, x, y, selected):
        # Three filament reels fit the same tile as the stock Home icons.
        edge = self.lcd.Color_White if selected else 0x8410
        colors = (0xF800, 0x07E0, 0x001F) if selected else (0x7800, 0x03E0, 0x0010)
        for lane, color in enumerate(colors):
            left = x + 16 + lane * 27
            self.lcd.Draw_Rectangle(1, color, left+4, y+22, left+18, y+49)
            for flange in (left, left+19):
                self.lcd.Draw_Rectangle(1, edge, flange, y+16, flange+3, y+55)
            self.lcd.Draw_Line(color, left+11, y+56, left+11, y+62)
        self.lcd.Draw_Line(edge, x+27, y+62, x+81, y+62)

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
        self.lcd.Draw_String(False, True, self.lcd.font6x12,
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
            self.lcd.Draw_Rectangle(1, flange, reel_x + 1, top + 7,
                                    reel_x + flange_w, top + 58)
            self.lcd.Draw_Rectangle(0, flange_edge, reel_x + 1, top + 7,
                                    reel_x + flange_w, top + 58)
            self.lcd.Draw_Rectangle(1, flange, reel_x + reel_w - flange_w - 1, top + 7,
                                    reel_x + reel_w - 2, top + 58)
            self.lcd.Draw_Rectangle(0, flange_edge, reel_x + reel_w - flange_w - 1, top + 7,
                                    reel_x + reel_w - 2, top + 58)
            self.lcd.Draw_Rectangle(1, color, body_left, y0, body_right, y1)

            winding = self.lcd.Color_White if sum(mmu['gate_color_rgb'][gate]) < 0.7 else flange
            for line_x in range(body_left + 5, body_right, 7):
                self.lcd.Draw_Line(winding, line_x, y0, line_x, y1)

            percent = percentages[gate] if gate < len(percentages) else None
            # Percent text needs enough horizontal room. Compact high-gate
            # layouts prioritize distinct lanes over overlapping text.
            if slot >= 28:
                pct = '--' if percent is None else '%d%%' % percent
                # Black backing keeps the percentage readable on white/yellow filament.
                pct_w = 6 * len(pct) + 4
                self.lcd.Draw_Rectangle(1, self.lcd.Color_Bg_Black,
                                        cx - pct_w // 2, top + 27,
                                        cx + pct_w // 2, top + 41)
                self.lcd.Draw_String(False, True, self.lcd.font6x12,
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
            self.lcd.Draw_Rectangle(1, label_bg, lx0, top + 64, lx1, top + 78)
            self.lcd.Draw_Rectangle(0, border, lx0, top + 64, lx1, top + 78)
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
            self.lcd.Draw_String(False, True, self.lcd.font6x12,
                                 label_fg, label_bg,
                                 cx - 3 * len(label), top + 65, label)

    # Dedicated MMU pages own the complete 272x480 canvas. The home dashboard
    # above is intentionally independent and keeps its existing appearance.
    MMU_TITLES = {'home': 'MMU', 'gates': 'GATES', 'gate': 'GATE',
                  'filament': 'FILAMENT', 'map': 'TOOL MAP', 'manage': 'MANAGE',
                  'status': 'MMU STATUS', 'bypass': 'BYPASS', 'recover': 'RECOVER STATE',
                  'manual': 'SET MMU STATE', 'confirm': 'CONFIRM'}

    def Enter_MMU_Menu(self, page='home'):
        self.checkkey = self.MMUMenu
        self._mmu_page = page
        self._mmu_selection = 1 if self.pd.mmu else 0
        self._mmu_gate = 0
        self._mmu_history = []
        self._mmu_notice = ''
        self._mmu_canvas_page = None
        self.Draw_MMU_Menu()

    def _mmu_open(self, page):
        self._mmu_history.append((self._mmu_page, self._mmu_selection))
        self._mmu_page, self._mmu_selection = page, 1
        self._mmu_notice = ''
        self.Draw_MMU_Menu()

    def _mmu_back(self):
        if self._mmu_history:
            self._mmu_page, self._mmu_selection = self._mmu_history.pop()
            self._mmu_notice = ''
            self.Draw_MMU_Menu()
        elif self.pd.mmu_session.pending is not None:
            self._mmu_page, self._mmu_selection = 'status', 0
            self._mmu_notice = 'Wait for MMU operation'
            self.Draw_MMU_Menu()
        else:
            self._mmu_canvas_page = None
            self.Goto_MainMenu()
            self.Draw_Status_Area(False)
        self.lcd.UpdateLCD()

    def _mmu_text(self, key, value, x, y, cells=31, small=False, color=0xFFFF, bg=0x0000):
        value = str(value).replace('\n', ' ').replace('\r', ' ')
        value = value[:cells] if len(value) <= cells else value[:max(0, cells - 1)] + '~'
        width, height = (6, 12) if small else (8, 16)
        cells = min(cells, (272 - x) // width)
        value = value[:cells]
        signature = (value, x, y, cells, small, color, bg)
        if self._mmu_render.get(key) == signature:
            return
        self._mmu_render[key] = signature
        self.lcd.Draw_Rectangle(1, bg, x, y, min(271, x + cells * width - 1), y + height - 1)
        self.lcd.Draw_String(False, False, self.lcd.font6x12 if small else self.lcd.font8x16,
                             color, bg, x, y, value)

    def _mmu_row(self, key, label, value, x, y, width, selected, enabled=True):
        signature = (label, value, selected, enabled, x, y, width)
        if self._mmu_render.get(key) == signature:
            return
        self._mmu_render[key] = signature
        bg = 0x33BD if selected else 0x18E4
        fg = 0xFFFF if enabled else 0x8410
        self.lcd.Draw_Rectangle(1, bg, x, y, x + width - 1, y + 39)
        if selected:
            self.lcd.Draw_Rectangle(0, 0xFFFF, x, y, x + width - 1, y + 39)
        cells = (width - 16) // 8
        value = str(value)
        available = cells - (len(value) + 1 if value else 0)
        label = label[:available] if len(label) <= available else label[:max(0, available - 1)] + '~'
        self.lcd.Draw_String(False, False, self.lcd.font8x16, fg, bg, x + 8, y + 12, label)
        if value:
            self.lcd.Draw_String(False, False, self.lcd.font8x16, fg, bg,
                                 x + width - 8 - 8 * len(value), y + 12, value)

    @staticmethod
    def _mmu_gate_label(gate):
        return 'Bypass' if gate == -2 else 'G%d' % (gate + 1) if gate is not None and gate >= 0 else 'G?'

    @staticmethod
    def _mmu_tool_label(tool):
        return 'Bypass' if tool == -2 else 'T%d' % tool if tool is not None and tool >= 0 else 'T?'

    def _mmu_action_item(self, action, label, gate=None):
        try:
            self.pd.mmu_session.prepare(action, gate=gate)
        except ValueError:
            return (('action', action, gate), label, 'LOCK', False)
        return (('action', action, gate), label, '>', True)

    def _mmu_items(self, m):
        page = self._mmu_page
        nav = lambda key, label: (('page', key), label, '>', True)
        if page == 'confirm':
            return [(('cancel',), 'Cancel', '', True),
                    (('execute',), 'Confirm', '', self._mmu_confirmation_valid())]
        if page == 'home':
            current = m.gate if m and m.gate is not None and m.gate >= 0 else None
            primary = ('unload', 'Unload') if m and m.filament == 'loaded' else ('load', 'Load')
            return [nav('gates', 'Gates'), self._mmu_action_item(*primary, gate=current),
                    nav('map', 'Tool map'), nav('bypass', 'Bypass'),
                    nav('manage', 'Manage'), nav('status', 'Status')]
        if page == 'gates':
            if not m:
                return []
            return [(('gate', gate), '%s %s' % (self._mmu_gate_label(gate), m.materials[gate] or '--'),
                     self._mmu_percent(gate), True) for gate in range(m.num_gates)]
        if page == 'gate':
            gate = self._mmu_gate
            return [self._mmu_action_item(action, label, gate) for action, label in
                    [('select', 'Select only'), ('load', 'Load selected'), ('change', 'Load / change'),
                     ('unload', 'Unload'), ('eject', 'Eject spool'), ('preload', 'Preload'), ('check', 'Check')]] + [nav('filament', 'Filament details')]
        if page == 'bypass':
            current = m.gate if m and m.gate is not None and m.gate >= 0 else None
            return [self._mmu_action_item('unload', 'Unload current gate', current),
                    self._mmu_action_item('bypass', 'Select bypass'),
                    self._mmu_action_item('load_extruder', 'Load extruder'),
                    self._mmu_action_item('unload_extruder', 'Unload extruder')]
        if page == 'manage':
            return [nav('recover', 'Recover state'), nav('status', 'Sensors / status'),
                    nav('bypass', 'Extruder / bypass'), (('web',), 'Calibration', 'WEB', False)]
        if page == 'recover':
            return [self._mmu_action_item('recover', 'Auto recover'), nav('manual', 'Set state manually'),
                    self._mmu_action_item('unlock', 'Unlock / reheat'),
                    self._mmu_action_item('resume', 'Resume print')]
        if page == 'manual':
            draft = self._mmu_manual
            return [(('edit', 'tool'), 'Tool', self._mmu_tool_label(draft['tool']), True),
                    (('edit', 'gate'), 'Gate', self._mmu_gate_label(draft['gate']), True),
                    (('edit', 'loaded'), 'Filament', 'LOADED' if draft['loaded'] else 'UNLOADED', True),
                    (('apply',), 'Apply', '>', m is not None), (('cancel',), 'Cancel', '', True)]
        if page == 'status':
            if self.pd.mmu_session.phase == 'error':
                return [(('ack',), 'Acknowledge', '', True), nav('recover', 'Recover state')]
            return []
        return []

    def _mmu_percent(self, gate):
        percentages = (self.pd.mmu or {}).get('remaining_percent', ())
        value = percentages[gate] if gate < len(percentages) else None
        return '--' if value is None else '%d%%' % value

    def _mmu_spools(self, m):
        count = min(4, m.num_gates)
        start = (max(0, m.gate) // 4) * 4 if m.gate is not None and m.gate >= 0 else 0
        start = min(start, ((m.num_gates - 1) // 4) * 4)
        home = self.pd.mmu or {}
        colors = home.get('gate_color_rgb', ())
        signature = (start, m.gate, m.gate_status, m.ttg_map, colors, home.get('remaining_percent', ()))
        if self._mmu_render.get('spools') == signature:
            return
        self._mmu_render['spools'] = signature
        self.lcd.Draw_Rectangle(1, 0x0000, 8, 59, 263, 164)
        for slot, gate in enumerate(range(start, min(m.num_gates, start + count))):
            x = 14 + slot * 66
            rgb = colors[gate] if gate < len(colors) else (0.5, 0.5, 0.5)
            color = self._rgb565(rgb) if m.gate_status[gate] in (1, 2) else 0x8410
            tools = m.tools_for_gate(gate)
            label = 'T%d' % tools[0] if len(tools) == 1 else 'T*' if tools else '--'
            self.lcd.Draw_String(False, False, self.lcd.font6x12, 0xFFFF, 0x0000, x + 6, 61, label)
            self.lcd.Draw_Rectangle(1, color, x + 6, 85, x + 35, 123)
            for fx in (x, x + 36):
                self.lcd.Draw_Rectangle(1, 0x9B46, fx, 79, fx + 5, 129)
            percent = self._mmu_percent(gate)
            self.lcd.Draw_Rectangle(1, 0x0000, x + 3, 99, x + 38, 113)
            self.lcd.Draw_String(False, False, self.lcd.font6x12, 0xFFFF, 0x0000, x + 6, 100, percent)
            bg = 0x07E0 if gate == m.gate else 0x18E4
            self.lcd.Draw_Rectangle(1, bg, x, 138, x + 41, 158)
            self.lcd.Draw_String(False, False, self.lcd.font6x12, 0x0000 if bg == 0x07E0 else 0xFFFF,
                                 bg, x + 12, 142, 'G%d' % (gate + 1))
        if m.num_gates > 4:
            self._mmu_render.pop('gatepage', None)
            self._mmu_text('gatepage', '%d/%d' % (start // 4 + 1, (m.num_gates + 3) // 4), 218, 165, 8, small=True)

    def _mmu_nozzle(self, y):
        temps = self.pd.thermalManager['temp_hotend'][0]
        value = 'Nozzle %d/%d C' % (temps['celsius'], temps['target']) if self.pd.HAS_HOTEND else 'Nozzle unavailable'
        self._mmu_text('nozzle', value, 12, y)

    def _mmu_path(self, m, y):
        signature = (m.filament, y)
        if self._mmu_render.get('path') == signature:
            return
        self._mmu_render['path'] = signature
        self.lcd.Draw_Rectangle(1, 0x0000, 12, y, 259, y + 40)
        color = 0x249F if m.filament == 'loaded' else 0x8410
        for x, name in ((14, 'GATE'), (82, 'BOWDEN'), (200, 'NOZZLE')):
            self.lcd.Draw_String(False, False, self.lcd.font6x12, 0x8410, 0x0000, x, y, name)
        self.lcd.Draw_Line(color, 30, y + 24, 233, y + 24)
        for x in (26, 106, 229):
            self.lcd.Draw_Rectangle(1, color, x, y + 20, x + 7, y + 27)

    def _mmu_confirmation_valid(self):
        op = getattr(self, '_mmu_confirmation', None)
        if op is None:
            return False
        try:
            return self.pd.mmu_session.prepare(op.action, op.gate, op.tool, op.loaded) == op
        except ValueError:
            return False

    def Draw_MMU_Menu(self):
        if not hasattr(self, '_mmu_page'):
            self._mmu_page, self._mmu_selection = 'home', 0
            self._mmu_gate, self._mmu_history, self._mmu_notice = 0, [], ''
        page = self._mmu_page
        m = self.pd.mmu_session.state
        if getattr(self, '_mmu_canvas_page', None) != page:
            self.lcd.Draw_Rectangle(1, 0x0000, 0, 0, 271, 479)
            self.lcd.Draw_Rectangle(1, 0x1105, 0, 0, 271, 29)
            self._mmu_canvas_page, self._mmu_render = page, {}
        if page == 'manual' and not hasattr(self, '_mmu_manual'):
            self._mmu_manual_base = m.fingerprint if m else None
            self._mmu_manual = {'tool': m.tool if m and m.tool is not None and m.tool >= 0 else 0,
                                'gate': m.gate if m and m.gate is not None and m.gate >= 0 else 0,
                                'loaded': bool(m and m.filament == 'loaded')}
        items = self._mmu_items(m)
        self._mmu_drawn_keys = tuple(item[0] for item in items)
        self._mmu_selection = min(self._mmu_selection, len(items))
        self._mmu_text('back', '<', 8, 5, 2, bg=0x33BD if self._mmu_selection == 0 else 0x1105)
        title = self.MMU_TITLES[page]
        if page in ('gate', 'filament'):
            title += ' / ' + self._mmu_gate_label(self._mmu_gate)
        self._mmu_text('title', title, 34, 5, 28, bg=0x1105)
        connection = 'OFFLINE' if self.pd.connection_error else 'MMU unavailable' if not m else (
            'MMU DISABLED' if m.enabled is not True else m.action.upper())
        self._mmu_text('connection', connection, 10, 36, 42, small=True,
                       color=0xFD20 if not m or m.enabled is not True else 0x8410)
        first_y, visible = 67, 8
        if page == 'home':
            if m:
                self._mmu_spools(m)
                self._mmu_text('active', '%s > %s  %s' % (self._mmu_tool_label(m.tool), self._mmu_gate_label(m.gate), m.filament.upper()), 12, 182, color=0x07E0)
                self._mmu_path(m, 209)
                self._mmu_nozzle(253)
            else:
                self._mmu_text('unavailable', 'Happy Hare unavailable', 12, 100)
                self._mmu_text('hint', 'Check MMU / Moonraker', 12, 126)
            for i, (_, label, _, enabled) in enumerate(items):
                self._mmu_row('item%d' % i, label, '', 8 + (i % 2) * 132,
                              283 + (i // 2) * 54, 124, self._mmu_selection == i + 1, enabled)
            self._mmu_text('notice', self._mmu_notice, 10, 438, 42, small=True, color=0xFD20)
            first_y = None
        elif page == 'gate':
            gate = self._mmu_gate
            if m and gate < m.num_gates:
                tools = ','.join('T%d' % t for t in m.tools_for_gate(gate)) or 'Unmapped'
                self._mmu_text('summary', tools + ' / ' + (m.materials[gate] or '--'), 12, 68)
                state = m.filament.upper() if gate == m.gate else {-1: 'UNKNOWN', 0: 'EMPTY', 1: 'AVAILABLE', 2: 'BUFFERED'}.get(m.gate_status[gate], 'UNKNOWN')
                self._mmu_text('gatestate', state + ' / ' + self._mmu_percent(gate), 12, 98)
            first_y, visible = 132, 7
        elif page == 'filament':
            gate = self._mmu_gate
            if m and gate < m.num_gates:
                for i, (label, value) in enumerate((('Name', m.names[gate]), ('Material', m.materials[gate]),
                        ('Spool ID', '#%s' % m.spool_ids[gate] if m.spool_ids[gate] and m.spool_ids[gate] > 0 else '--'),
                        ('Remaining', self._mmu_percent(gate)), ('Temperature', '%s C' % m.temperatures[gate] if m.temperatures[gate] is not None else '--'),
                        ('Spoolman', m.spoolman_support))):
                    self._mmu_text('meta%d' % i, label + ': ' + str(value or '--'), 12, 70 + 42 * i)
                self._mmu_text('readonly', 'Read-only; edit in web UI', 12, 358, 40, small=True)
            first_y = None
        elif page == 'map':
            if m:
                start = getattr(self, '_mmu_map_start', 0)
                start = min(start, max(0, m.num_gates - 8))
                for i, tool in enumerate(range(start, min(m.num_gates, start + 8))):
                    self._mmu_text('map%d' % i, 'T%d > %s' % (tool, self._mmu_gate_label(m.ttg_map[tool])), 12, 70 + 37 * i)
                self._mmu_text('readonly', 'Read-only; edit in web UI', 12, 398, 40, small=True)
                self._mmu_text('maphint', 'Turn: scroll   Press Back: return', 12, 421, 40, small=True)
            first_y = None
        elif page == 'status':
            session = self.pd.mmu_session
            self._mmu_text('result', session.message or 'Live MMU telemetry', 12, 66, 40, small=True, color=0xFD20 if session.phase == 'error' else 0xFFFF)
            if m:
                self._mmu_text('active', '%s / %s / %s' % (self._mmu_tool_label(m.tool), self._mmu_gate_label(m.gate), m.filament.upper()), 12, 100)
                self._mmu_path(m, 132)
                progress = 'Bowden: %d%%' % m.bowden_progress if m.bowden_progress is not None else 'Stage: ' + m.action
                self._mmu_text('progress', progress, 12, 186)
                sensors = dict(m.sensors)
                for i, sensor in enumerate(('mmu_shared_exit', 'extruder', 'toolhead')):
                    value = 'ABSENT' if sensor not in sensors else {True: 'TRIGGERED', False: 'CLEAR', None: 'UNKNOWN/OFF'}[sensors[sensor]]
                    self._mmu_text('sensor%d' % i, sensor + ': ' + value, 12, 218 + i * 27, 40, small=True)
                self._mmu_text('sync', 'Gear sync: ' + {True: 'ON', False: 'OFF', None: '--'}[m.sync_drive], 12, 306)
                self._mmu_nozzle(336)
            first_y, visible = 376, 2
        elif page == 'bypass':
            self._mmu_text('filament', 'Filament: ' + (m.filament.upper() if m else 'UNKNOWN'), 12, 75)
            self._mmu_text('hint', 'Unload before selecting bypass', 12, 105, 40, small=True)
            first_y, visible = 156, 6
        elif page == 'recover':
            if m:
                reason = m.reason or ('MMU locked' if m.locked else 'Check physical filament state')
                for i in range(3):
                    self._mmu_text('reason%d' % i, reason[i * 40:(i + 1) * 40], 12, 66 + i * 17, 40, small=True, color=0xFD20)
                self._mmu_text('active', '%s / %s / %s' % (self._mmu_tool_label(m.tool), self._mmu_gate_label(m.gate), m.filament.upper()), 12, 131)
            first_y, visible = 186, 6
        elif page == 'manual':
            self._mmu_text('hint', 'Report actual state; no movement', 12, 70, 40, small=True)
            first_y, visible = 113, 7
        elif page == 'confirm':
            op = self._mmu_confirmation
            self._mmu_text('target', op.label, 12, 82)
            summary = 'Physical state: ' + (m.filament.upper() if m else 'UNKNOWN')
            self._mmu_text('details', summary, 12, 120, 40, small=True)
            self._mmu_text('valid', 'Target changed; cancel and retry' if not self._mmu_confirmation_valid() else 'Check target before confirming', 12, 170, 40, small=True, color=0xFD20)
            message = {'unload': 'Filament returns to MMU.', 'eject': 'Spool removed from MMU.',
                       'manual': 'Reports state; does not move.', 'resume': 'Print motion will resume.'}.get(op.action, 'This may move filament/motors.')
            self._mmu_text('effect', message, 12, 210, 40, small=True)
            for i, (_, label, _, enabled) in enumerate(items):
                self._mmu_row('item%d' % i, label, '', 8 + i * 132, 374, 124,
                              self._mmu_selection == i + 1, enabled)
            first_y = None
        if first_y is not None:
            start = max(0, self._mmu_selection - visible)
            for row in range(visible):
                i = start + row
                if i < len(items):
                    _, label, value, enabled = items[i]
                    if page == 'manual' and items[i][0][0] == 'edit' and getattr(self, '_mmu_edit', None) == items[i][0][1]:
                        value = '[' + value + ']'
                    self._mmu_row('row%d' % row, label, value, 8, first_y + row * 43, 256,
                                  self._mmu_selection == i + 1, enabled)
                elif self._mmu_render.get('row%d' % row) is not None:
                    self.lcd.Draw_Rectangle(1, 0x0000, 8, first_y + row * 43, 263, first_y + row * 43 + 39)
                    self._mmu_render.pop('row%d' % row, None)
            if len(items) > visible:
                self._mmu_text('pagination', '%d-%d / %d' % (start + 1, min(len(items), start + visible), len(items)), 12, 436, 40, small=True)
        self._mmu_text('footer', self._mmu_notice or ('Turn: edit   Press: accept' if getattr(self, '_mmu_edit', None) else 'Turn: select   Press: open'), 10, 463, 42, small=True, color=0xFD20 if self._mmu_notice else 0x8410)
        self.lcd.UpdateLCD()

    def HMI_MMU_Menu(self):
        if not hasattr(self, '_mmu_page'):
            self.Draw_MMU_Menu()
        event = self.get_encoder_state()
        if event == self.ENCODER_DIFF_NO:
            return
        m = self.pd.mmu_session.state
        edit = getattr(self, '_mmu_edit', None)
        if edit:
            if event == self.ENCODER_DIFF_ENTER:
                self._mmu_edit = None
            elif m and event in (self.ENCODER_DIFF_CW, self.ENCODER_DIFF_CCW):
                delta = 1 if event == self.ENCODER_DIFF_CW else -1
                self._mmu_manual[edit] = (not self._mmu_manual[edit] if edit == 'loaded'
                    else max(0, min(m.num_gates - 1, self._mmu_manual[edit] + delta)))
            self.Draw_MMU_Menu()
            return
        if self._mmu_page == 'map' and m and event in (self.ENCODER_DIFF_CW, self.ENCODER_DIFF_CCW):
            delta = 1 if event == self.ENCODER_DIFF_CW else -1
            self._mmu_map_start = max(0, min(max(0, m.num_gates - 8), getattr(self, '_mmu_map_start', 0) + delta))
            self.Draw_MMU_Menu()
            return
        items = self._mmu_items(m)
        if event == self.ENCODER_DIFF_ENTER and tuple(item[0] for item in items) != self._mmu_drawn_keys:
            self._mmu_notice = 'Menu changed; select again'
            self.Draw_MMU_Menu()
            return
        self._mmu_selection = min(self._mmu_selection, len(items))
        if event == self.ENCODER_DIFF_CW:
            self._mmu_selection = min(len(items), self._mmu_selection + 1)
        elif event == self.ENCODER_DIFF_CCW:
            self._mmu_selection = max(0, self._mmu_selection - 1)
        elif event == self.ENCODER_DIFF_ENTER:
            if self._mmu_selection == 0:
                self._mmu_back()
                return
            key, _, _, enabled = items[self._mmu_selection - 1]
            if not enabled:
                self._mmu_notice = 'Unavailable in current state'
            elif key[0] == 'page':
                if key[1] == 'manual':
                    self._mmu_manual_base = m.fingerprint if m else None
                    self._mmu_manual = {'tool': m.tool if m and m.tool is not None and m.tool >= 0 else 0,
                                        'gate': m.gate if m and m.gate is not None and m.gate >= 0 else 0,
                                        'loaded': bool(m and m.filament == 'loaded')}
                    self._mmu_edit = None
                self._mmu_open(key[1])
                return
            elif key[0] == 'gate':
                self._mmu_gate = key[1]
                self._mmu_open('gate')
                return
            elif key[0] in ('action', 'apply'):
                try:
                    if key[0] == 'apply' and (m is None or m.fingerprint != self._mmu_manual_base):
                        raise ValueError('MMU changed; reopen editor')
                    self._mmu_confirmation = (self.pd.mmu_session.prepare(key[1], gate=key[2])
                        if key[0] == 'action' else self.pd.mmu_session.prepare('manual', **self._mmu_manual))
                except ValueError as error:
                    self._mmu_notice = str(error)
                else:
                    self._mmu_open('confirm')
                    self._mmu_selection = 1  # Cancel always owns initial focus.
                    self.Draw_MMU_Menu()
                    return
            elif key[0] == 'execute':
                try:
                    self.pd.mmu_session.start(self._mmu_confirmation)
                except ValueError as error:
                    self._mmu_notice = str(error)
                else:
                    # Drop confirmation so Back can never submit it again.
                    self._mmu_page, self._mmu_selection = 'status', 0
                    self.Draw_MMU_Menu()
                    return
            elif key[0] == 'cancel':
                self._mmu_back()
                return
            elif key[0] == 'edit':
                self._mmu_edit = key[1]
            elif key[0] == 'ack':
                self.pd.mmu_session.phase, self.pd.mmu_session.message = 'idle', ''
        self.Draw_MMU_Menu()

    def _poll_mmu(self):
        session = self.pd.mmu_session
        was_pending = session.pending is not None
        session.update()
        if self.checkkey == self.MMUMenu:
            if was_pending and getattr(self, '_mmu_page', 'home') != 'status' and session.phase == 'error':
                self._mmu_page, self._mmu_selection = 'status', 1
            self.Draw_MMU_Menu()
