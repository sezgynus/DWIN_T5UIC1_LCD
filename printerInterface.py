import copy
import logging
import math
from moonraker_client import MoonrakerClient, MoonrakerError
from moonraker_subscription import MoonrakerSubscription
from preset_store import PresetStore
from printer_state import PrinterState
from printer_capabilities import PrinterCapabilities

class xyze_t:
    x = 0.0
    y = 0.0
    z = 0.0
    e = 0.0
    home_x = False
    home_y = False
    home_z = False

    def homing(self):
        self.home_x = False
        self.home_y = False
        self.home_z = False


class AxisEnum:
    X_AXIS = 0
    A_AXIS = 0
    Y_AXIS = 1
    B_AXIS = 1
    Z_AXIS = 2
    C_AXIS = 2
    E_AXIS = 3
    X_HEAD = 4
    Y_HEAD = 5
    Z_HEAD = 6
    E0_AXIS = 3
    E1_AXIS = 4
    E2_AXIS = 5
    E3_AXIS = 6
    E4_AXIS = 7
    E5_AXIS = 8
    E6_AXIS = 9
    E7_AXIS = 10
    ALL_AXES = 0xFE
    NO_AXIS = 0xFF


class HMI_value_t:
    E_Temp = 0
    Bed_Temp = 0
    Fan_speed = 0
    print_speed = 100
    Max_Feedspeed = 0.0
    Max_Acceleration = 0.0
    Max_Jerk = 0.0
    Max_Step = 0.0
    Move_X_scale = 0.0
    Move_Y_scale = 0.0
    Move_Z_scale = 0.0
    Move_E_scale = 0.0
    offset_value = 0.0
    show_mode = 0  # -1: Temperature control    0: Printing temperature


class HMI_Flag_t:
    language = 0
    pause_flag = False
    pause_action = False
    print_finish = False
    done_confirm_flag = False
    select_flag = False
    home_flag = False
    heat_flag = False  # 0: heating done  1: during heating
    ETempTooLow_flag = False
    leveling_offset_flag = False
    feedspeed_axis = AxisEnum()
    acc_axis = AxisEnum()
    jerk_axis = AxisEnum()
    step_axis = AxisEnum()


class buzz_t:
    def tone(self, t, n):
        pass


class material_preset_t:
    def __init__(self, name, hotend_temp, bed_temp, fan_speed=100):
        self.name = name
        self.hotend_temp = hotend_temp
        self.bed_temp = bed_temp
        self.fan_speed = fan_speed


class PrinterData:
    Z_PROBE_OFFSET_RANGE_MIN = -20
    Z_PROBE_OFFSET_RANGE_MAX = 20

    buzzer = buzz_t()

    BABY_Z_VAR = 0
    feedrate_percentage = 100
    temphot = 0
    tempbed = 0

    HMI_ValueStruct = HMI_value_t()
    HMI_flag = HMI_Flag_t()

    current_position = xyze_t()

    thermalManager = {
        'temp_bed': {'celsius': 0, 'target': 0},
        'temp_hotend': [{'celsius': 0, 'target': 0}],
        'fan_speed': [0]
    }

    material_preset = [
        material_preset_t('PLA', 200, 60),
        material_preset_t('ABS', 210, 100)
    ]
    files = None
    MACHINE_SIZE = 'unknown'
    SHORT_BUILD_VERSION = "unknown"
    CORP_WEBSITE_E = "https://www.klipper3d.org/"

    def __init__(self, API_Key='', URL='http://127.0.0.1:7125', timeout=5.0, settings_path=None):
        self.client = MoonrakerClient(URL, API_Key, timeout)
        self.state = PrinterState()
        self.capabilities = PrinterCapabilities()
        self._apply_capabilities(self.capabilities)
        self.status = None
        self.connection_error = None
        self.last_command_error = None
        self.absolute_moves = True
        self.absolute_extrude = True
        self.file_name = ''
        self.job_Info = {'virtual_sdcard': {'is_active': False, 'progress': 0},
                         'print_stats': {'state': 'standby', 'print_duration': 0,
                                         'filename': ''}}
        self.current_position = xyze_t()
        self.HMI_ValueStruct = HMI_value_t()
        self.HMI_flag = HMI_Flag_t()
        self.thermalManager = copy.deepcopy(type(self).thermalManager)
        self.material_preset = copy.deepcopy(type(self).material_preset)
        self.preset_store = PresetStore(settings_path)
        self.settings_error = None
        try:
            saved = self.preset_store.load()
            if saved is not None:
                self.material_preset = [material_preset_t(**item) for item in saved]
        except (OSError, ValueError, TypeError, UnicodeError) as error:
            self.settings_error = str(error)
            logging.warning('Cannot load presets from %s: %s', self.preset_store.path, error)
        self.files = []
        self._file_revision = -1
        self.subscription = MoonrakerSubscription(URL, API_Key, timeout)

    def _apply_capabilities(self, caps):
        self.HAS_HOTEND = caps.active_hotend is not None
        self.HOTENDS = len(caps.hotends)
        self.HAS_HEATED_BED = caps.bed is not None
        self.HAS_FAN = caps.fan
        self.HAS_BED_PROBE = caps.probe
        self.HAS_PREHEAT = caps.has_heaters
        self.HAS_ZOFFSET_ITEM = True
        # Discovery does not enable the not-yet-implemented leveling wizard.
        self.HAS_ONESTEP_LEVELING = False
        self.PREVENT_COLD_EXTRUSION = True
        hotend = caps.active_hotend
        self.EXTRUDE_MINTEMP = hotend.min_extrude_temp if hotend else 0
        self.EXTRUDE_MAXLENGTH = hotend.max_extrude_distance if hotend else 0
        self.MAX_E_TEMP = hotend.maximum if hotend else 0
        self.MIN_E_TEMP = 0
        self.BED_MAX_TARGET = caps.bed.maximum if caps.bed else 0
        self.MIN_BED_TEMP = 0
        self.X_MIN_POS, self.Y_MIN_POS, self.Z_MIN_POS = caps.axis_minimum
        self.X_MAX_POS, self.Y_MAX_POS, self.Z_MAX_POS = caps.axis_maximum
        self.MACHINE_SIZE = 'x'.join('{:g}'.format(value) for value in caps.build_size)

    def close(self):
        self.subscription.close()
        self.client.close()

    def check_command_results(self):
        from queue import Empty
        while True:
            try:
                path, future = self.client.command_results.get_nowait()
            except Empty:
                return
            if future.cancelled():
                continue
            error = future.exception()
            if error:
                self.last_command_error = str(error)
                logging.error('LCD command %s failed: %s', path, error)

    # ------------- Klipper Function ----------

    def ishomed(self):
        if not self.connection_error and self.current_position.home_x and self.current_position.home_y and self.current_position.home_z:
            return True
        else:
            return False

    def offset_z(self, new_offset):
#        print('new z offset:', new_offset)
        self.BABY_Z_VAR = new_offset
        self.sendGCode('ACCEPT')

    def add_mm(self, axs, new_offset):
        gc = 'TESTZ Z={}'.format(new_offset)
        print(axs, gc)
        self.sendGCode(gc)

    def probe_calibrate(self):
        self.sendGCode('G28')
        self.sendGCode('PROBE_CALIBRATE')
        self.sendGCode('G1 Z0')

    # ------------- Moonraker transport ----------

    def getREST(self, path):
        return self.client.get(path)

    def postREST(self, path, json):
        snapshot = self.subscription.snapshot()
        if self.connection_error or snapshot['state'] != 'ready':
            from concurrent.futures import Future
            future = Future()
            future.set_exception(MoonrakerError('Printer connection is not ready'))
            self.last_command_error = 'Printer connection is not ready'
            return future
        epoch = snapshot['epoch']

        def guard():
            current = self.subscription.snapshot()
            return current['state'] == 'ready' and current['epoch'] == epoch

        return self.client.post(path, json, guard=guard)

    def init_Webservices(self):
        # Bootstrap and reconnection run on the subscription thread.
        return self.update_variable()

    def GetFiles(self, refresh=False):
        if not self.files or refresh:
            try:
                files = self.getREST('/server/files/list')['result']
                if not isinstance(files, list) or not all(
                        isinstance(item, dict) and isinstance(item.get('path'), str)
                        for item in files):
                    raise ValueError('Invalid file list')
                self.files = files
            except (MoonrakerError, KeyError, TypeError, ValueError) as exc:
                self.connection_error = str(exc)
        names = []
        for fl in self.files:
            names.append(fl["path"])
        return names

    def update_variable(self):
        self.check_command_results()
        try:
            state = PrinterState.from_snapshot(self.subscription.snapshot())
            if not state.ready:
                self.state = state
                self.connection_error = state.error or 'Klipper is not ready'
                return False
            data = state.status
            caps = PrinterCapabilities.from_state(state)
            gcm = data['gcode_move']
            toolhead = data['toolhead']
            # Validate required fields before committing the snapshot.
            job = {'virtual_sdcard': data['virtual_sdcard'], 'print_stats': data['print_stats']}
            print_state = job['print_stats']['state']
            position = toolhead['position']
            x, y, z, e = position[:4]
            origin = gcm['homing_origin'][2]
            absolute_moves = gcm['absolute_coordinates']
            absolute_extrude = gcm['absolute_extrude']
            thermal = copy.deepcopy(self.thermalManager)
            for obj, target in [(caps.active_hotend.name if caps.active_hotend else None, thermal['temp_hotend'][0]),
                                ('heater_bed' if caps.bed else None, thermal['temp_bed'])]:
                if obj is None:
                    target['celsius'] = target['target'] = 0
                else:
                    target['celsius'] = int(data[obj]['temperature'])
                    target['target'] = int(data[obj]['target'])
            thermal['fan_speed'][0] = int(data['fan']['speed'] * 100) if caps.fan else 0
        except (MoonrakerError, KeyError, TypeError, IndexError, ValueError) as exc:
            self.connection_error = str(exc)
            return False
        self.connection_error = None
        changed = state != self.state
        self.state = state
        self.capabilities = caps
        self._apply_capabilities(caps)
        self.SHORT_BUILD_VERSION = state.software_version
        if state.file_revision != self._file_revision:
            self.files = []
            self._file_revision = state.file_revision
        self.thermalManager = thermal
        self.absolute_moves = absolute_moves
        self.absolute_extrude = absolute_extrude
        self.current_position.x, self.current_position.y, self.current_position.z, self.current_position.e = x, y, z, e
        homed = toolhead.get('homed_axes', '')
        self.current_position.home_x = 'x' in homed
        self.current_position.home_y = 'y' in homed
        self.current_position.home_z = 'z' in homed
        self.BABY_Z_VAR = origin
        self.HMI_ValueStruct.offset_value = origin * 100
        self.job_Info = job
        self.file_name = job['print_stats'].get('filename', '')
        self.status = print_state
        self.HMI_flag.print_finish = print_state == 'complete'
        return changed

    def printingIsPaused(self):
        return self.job_Info['print_stats']['state'] == "paused" or self.job_Info['print_stats']['state'] == "pausing"

    def getPercent(self):
        # Paused/terminal jobs retain their statistics even when SD execution stops.
        if self.job_Info['print_stats']['state'] == 'standby':
            return 0
        return max(0, min(100, self.job_Info['virtual_sdcard']['progress'] * 100))

    def duration(self):
        if self.job_Info['print_stats']['state'] == 'standby':
            return 0
        return self.job_Info['print_stats'].get('print_duration', 0)

    def remain(self):
        percent = self.getPercent()
        duration = self.duration()
        if percent:
            total = duration / (percent / 100)
            return total - duration
        return 0

    def openAndPrintFile(self, filenum):
        self.file_name = self.files[filenum]['path']
        self.postREST('/printer/print/start', json={'filename': self.file_name})

    def cancel_job(self): #fixed
        print('Canceling job:')
        self.postREST('/printer/print/cancel', json=None)

    def pause_job(self): #fixed
        print('Pausing job:')
        self.postREST('/printer/print/pause', json=None)

    def resume_job(self): #fixed
        print('Resuming job:')
        self.postREST('/printer/print/resume', json=None)

    def set_feedrate(self, fr):
        self.feedrate_percentage = fr
        self.sendGCode('M220 S%s' % fr)

    def home(self, homeZ=False): #fixed using gcode
        script = 'G28 X Y'
        if homeZ:
            script += (' Z')
        self.sendGCode(script)

    def _jog(self, axis, value, speed, absolute):
        axis = str(axis).upper()
        if axis not in ('X', 'Y', 'Z', 'E'):
            raise ValueError('Invalid jog axis')
        value, speed = float(value), float(speed)
        if not math.isfinite(value) or not math.isfinite(speed) or speed <= 0:
            raise ValueError('Invalid jog value or speed')
        state = self.state
        if not state.ready or self.connection_error:
            raise ValueError('Printer is unavailable')
        if state.status['print_stats']['state'] in ('printing', 'paused', 'pausing'):
            raise ValueError('Jogging is unavailable during a print')
        toolhead = state.status['toolhead']
        # Use command-space position before transforms such as bed mesh.
        position = state.status['gcode_move']['position']
        index = 'XYZE'.index(axis)
        current = float(position[index])
        if not math.isfinite(current):
            raise ValueError('Invalid printer position')
        delta = value - current if absolute else value
        target = current + delta
        if axis == 'E':
            heater = self.capabilities.active_hotend
            if heater is None or not state.status.get(heater.name, {}).get('can_extrude', False):
                raise ValueError('Extruder is unavailable or too cold')
            if abs(delta) > heater.max_extrude_distance:
                raise ValueError('Extrusion exceeds configured distance')
        else:
            if axis.lower() not in toolhead.get('homed_axes', ''):
                raise ValueError('Axis must be homed before jogging')
            if not self.capabilities.axis_minimum[index] <= target <= self.capabilities.axis_maximum[index]:
                raise ValueError('Jog exceeds configured axis range')
        max_velocity = float(toolhead['max_velocity'])
        if axis == 'Z':
            max_velocity = min(max_velocity, float(state.settings.get('printer', {}).get('max_z_velocity', max_velocity)))
        if not math.isfinite(max_velocity) or max_velocity <= 0:
            raise ValueError('Invalid configured velocity')
        speed = min(speed, max_velocity * 60)
        if delta == 0:
            return None
        # Klipper saves/restores feed and extrusion factors as well as G90/M82.
        # Relative displacement avoids changing the G92/work origin.
        script = '\n'.join(('SAVE_GCODE_STATE NAME=_DWIN_JOG', 'G91', 'M83',
                            'M220 S100', 'M221 S100',
                            'G1 {}{:g} F{:g}'.format(axis, delta, speed),
                            'RESTORE_GCODE_STATE NAME=_DWIN_JOG MOVE=0'))
        return self.sendGCode(script)

    def moveRelative(self, axis, distance, speed):
        return self._jog(axis, distance, speed, False)

    def moveAbsolute(self, axis, position, speed):
        return self._jog(axis, position, speed, True)

    def sendGCode(self, gcode):
        return self.postREST('/printer/gcode/script', json={'script': gcode})

    def disable_all_heaters(self):
        if not self.capabilities.has_heaters:
            return None
        return self.sendGCode('TURN_OFF_HEATERS')

    def zero_fan_speeds(self):
        if self.HAS_FAN:
            return self.setFanSpeed(0)

    def setFanSpeed(self, percent):
        if not self.HAS_FAN or not 0 <= float(percent) <= 100:
            raise ValueError('Fan is unavailable or speed is out of range')
        return self.sendGCode('M106 S{:g}'.format(float(percent) * 255 / 100))

    def preheat(self, profile):
        if profile == "PLA":
            self.preHeat(self.material_preset[0].bed_temp, self.material_preset[0].hotend_temp)
        elif profile == "ABS":
            self.preHeat(self.material_preset[1].bed_temp, self.material_preset[1].hotend_temp)

    def save_settings(self):
        try:
            self.preset_store.save([vars(preset).copy() for preset in self.material_preset])
        except (OSError, ValueError, TypeError, UnicodeError) as error:
            self.settings_error = str(error)
            logging.error('Cannot save presets to %s: %s', self.preset_store.path, error)
            return False
        self.settings_error = None
        return True

    def setExtTemp(self, target, toolnum=None):
        heater = self.capabilities.active_hotend
        if toolnum is not None:
            name = 'extruder' + (str(toolnum) if toolnum else '')
            heater = next((item for item in self.capabilities.hotends if item.name == name), None)
        if heater is None:
            raise ValueError('Hotend is unavailable')
        value = heater.validate_target(target)
        return self.sendGCode('SET_HEATER_TEMPERATURE HEATER={} TARGET={:g}'.format(heater.name, value))

    def setBedTemp(self, target):
        heater = self.capabilities.bed
        if heater is None:
            raise ValueError('Heated bed is unavailable')
        value = heater.validate_target(target)
        return self.sendGCode('SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={:g}'.format(value))

    def preHeat(self, bedtemp, exttemp, toolnum=None):
        # Validate the whole preset before sending any command.
        commands = []
        if self.capabilities.bed:
            value = self.capabilities.bed.validate_target(bedtemp)
            commands.append('SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={:g}'.format(value))
        heater = self.capabilities.active_hotend
        if toolnum is not None:
            name = 'extruder' + (str(toolnum) if toolnum else '')
            heater = next((item for item in self.capabilities.hotends if item.name == name), None)
            if heater is None:
                raise ValueError('Hotend is unavailable')
        if heater:
            value = heater.validate_target(exttemp)
            commands.append('SET_HEATER_TEMPERATURE HEATER={} TARGET={:g}'.format(heater.name, value))
        if commands:
            return self.sendGCode('\n'.join(commands))

    def setZOffset(self, offset):
        self.sendGCode('SET_GCODE_OFFSET Z=%s MOVE=1' % offset)