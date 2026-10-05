import copy
import logging
from moonraker_client import MoonrakerClient, MoonrakerError
from moonraker_subscription import MoonrakerSubscription
from printer_state import PrinterState

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
    event_loop = None
    HAS_HOTEND = True
    HOTENDS = 1
    HAS_HEATED_BED = True
    HAS_FAN = False
    HAS_ZOFFSET_ITEM = True
    HAS_ONESTEP_LEVELING = False
    HAS_PREHEAT = True
    HAS_BED_PROBE = False
    PREVENT_COLD_EXTRUSION = True
    EXTRUDE_MINTEMP = 170
    EXTRUDE_MAXLENGTH = 200

    HEATER_0_MAXTEMP = 275
    HEATER_0_MINTEMP = 5
    HOTEND_OVERSHOOT = 15

    MAX_E_TEMP = (HEATER_0_MAXTEMP - (HOTEND_OVERSHOOT))
    MIN_E_TEMP = HEATER_0_MINTEMP

    BED_OVERSHOOT = 10
    BED_MAXTEMP = 150
    BED_MINTEMP = 5

    BED_MAX_TARGET = (BED_MAXTEMP - (BED_OVERSHOOT))
    MIN_BED_TEMP = BED_MINTEMP

    X_MIN_POS = 0.0
    Y_MIN_POS = 0.0
    Z_MIN_POS = 0.0
    Z_MAX_POS = 200

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
        'temp_bed': {'celsius': 20, 'target': 120},
        'temp_hotend': [{'celsius': 20, 'target': 120}],
        'fan_speed': [100]
    }

    material_preset = [
        material_preset_t('PLA', 200, 60),
        material_preset_t('ABS', 210, 100)
    ]
    files = None
    MACHINE_SIZE = "220x220x250"
    SHORT_BUILD_VERSION = "1.00"
    CORP_WEBSITE_E = "https://www.klipper3d.org/"

    def __init__(self, API_Key='', URL='http://127.0.0.1:7125', timeout=5.0):
        self.client = MoonrakerClient(URL, API_Key, timeout)
        self.state = PrinterState()
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
        self.files = []
        self._file_revision = -1
        self.subscription = MoonrakerSubscription(URL, API_Key, timeout)

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
            maximum = toolhead['axis_maximum']
            xmax, ymax = maximum[:2]
            size = '{}x{}x{}'.format(*(int(v) for v in maximum[:3]))
            thermal = copy.deepcopy(self.thermalManager)
            for obj, target in [('extruder', thermal['temp_hotend'][0]),
                                ('heater_bed', thermal['temp_bed'])]:
                if obj in data:
                    target['celsius'] = int(data[obj]['temperature'])
                    target['target'] = int(data[obj]['target'])
            if 'fan' in data:
                thermal['fan_speed'][0] = int(data['fan']['speed'] * 100)
        except (MoonrakerError, KeyError, TypeError, IndexError, ValueError) as exc:
            self.connection_error = str(exc)
            return False
        self.connection_error = None
        changed = state != self.state
        self.state = state
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
        self.X_MAX_POS, self.Y_MAX_POS = xmax, ymax
        self.MACHINE_SIZE = size
        self.BABY_Z_VAR = origin
        self.HMI_ValueStruct.offset_value = origin * 100
        self.job_Info = job
        self.file_name = job['print_stats'].get('filename', '')
        self.status = print_state
        self.HMI_flag.print_finish = self.getPercent() == 100.0
        return changed

    def printingIsPaused(self):
        return self.job_Info['print_stats']['state'] == "paused" or self.job_Info['print_stats']['state'] == "pausing"

    def getPercent(self):
        if self.job_Info['virtual_sdcard']['is_active']:
            return self.job_Info['virtual_sdcard']['progress'] * 100
        else:
            return 0

    def duration(self):
        if self.job_Info['virtual_sdcard']['is_active']:
            return self.job_Info['print_stats']['print_duration']
        return 0

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

    def moveRelative(self, axis, distance, speed):
        self.sendGCode('%s \n%s %s%s F%s%s' % ('G91', 'G1', axis, distance, speed,
            '\nG90' if self.absolute_moves else ''))

    def moveAbsolute(self, axis, position, speed):
        self.sendGCode('%s \n%s %s%s F%s%s' % ('G90', 'G1', axis, position, speed,
            '\nG91' if not self.absolute_moves else ''))

    def sendGCode(self, gcode):
        return self.postREST('/printer/gcode/script', json={'script': gcode})

    def disable_all_heaters(self):
        self.setExtTemp(0)
        self.setBedTemp(0)

    def zero_fan_speeds(self):
        pass

    def preheat(self, profile):
        if profile == "PLA":
            self.preHeat(self.material_preset[0].bed_temp, self.material_preset[0].hotend_temp)
        elif profile == "ABS":
            self.preHeat(self.material_preset[1].bed_temp, self.material_preset[1].hotend_temp)

    def save_settings(self):
        print('saving settings')
        return True

    def setExtTemp(self, target, toolnum=0):
        self.sendGCode('M104 T%s S%s' % (toolnum, target))

    def setBedTemp(self, target):
        self.sendGCode('M140 S%s' % target)

    def preHeat(self, bedtemp, exttemp, toolnum=0):
# these work but invoke a wait which hangs the screen until they finish.
#        self.sendGCode('M140 S%s\nM190 S%s' % (bedtemp, bedtemp))
#        self.sendGCode('M104 T%s S%s\nM109 T%s S%s' % (toolnum, exttemp, toolnum, exttemp))
        self.setBedTemp(bedtemp)
        self.setExtTemp(exttemp)

    def setZOffset(self, offset):
        self.sendGCode('SET_GCODE_OFFSET Z=%s MOVE=1' % offset)