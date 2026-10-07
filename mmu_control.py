"""Happy Hare state and guarded, completion-tracked MMU operations.

Gate indices stay zero based here; the LCD alone presents G1 for gate 0.
Missing telemetry remains unknown and never enables a motion operation.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import math
import time


def integer(value, default=None):
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def boolean(value):
    return value if isinstance(value, bool) else None


def text(value, default='Unknown'):
    return value if isinstance(value, str) and value else default


@dataclass(frozen=True)
class MMUState:
    epoch: int
    num_gates: int
    gate: int | None
    tool: int | None
    enabled: bool | None
    action: str
    print_state: str
    filament: str
    locked: bool | None
    gate_status: tuple
    ttg_map: tuple
    materials: tuple
    names: tuple
    temperatures: tuple
    spool_ids: tuple
    sensors: tuple
    sync_drive: bool | None
    bowden_progress: int | None
    reason: str
    spoolman_support: str

    @classmethod
    def from_snapshot(cls, snapshot):
        if snapshot.get('state') != 'ready':
            return None
        raw = snapshot.get('status', {}).get('mmu')
        if not isinstance(raw, Mapping):
            return None
        count = integer(raw.get('num_gates'))
        if count is None or not 1 <= count <= 256:
            return None
        def values(key, parse):
            seq = raw.get(key, ())
            if not isinstance(seq, (tuple, list)):
                seq = ()
            return tuple(parse(seq[i]) if i < len(seq) else None for i in range(count))
        def index(value):
            n = integer(value)
            return n if n is not None and -2 <= n < count else None
        status = text(raw.get('print_state'))
        known_states = {'initialized', 'ready', 'started', 'printing', 'complete',
                        'cancelled', 'error', 'pause_locked', 'paused', 'standby', 'idle'}
        locked = (status == 'pause_locked' if status in known_states
                  else boolean(raw.get('is_locked')))
        filament = text(raw.get('filament')).lower()
        if filament not in ('loaded', 'unloaded'):
            filament = 'unknown'
        # Never promote an intermediate/contradictory physical state to loaded/empty.
        pos = integer(raw.get('filament_pos'))
        if 'filament_pos' in raw and pos != {'loaded': 10, 'unloaded': 0}.get(filament):
            filament = 'unknown'
        progress = raw.get('bowden_progress')
        if (isinstance(progress, bool) or not isinstance(progress, (int, float))
                or not math.isfinite(progress) or not 0 <= progress <= 100):
            progress = None
        else:
            progress = round(progress)
        sensors = raw.get('sensors', {})
        if not isinstance(sensors, Mapping):
            sensors = {}
        return cls(snapshot.get('epoch', 0), count, index(raw.get('gate')),
                   index(raw.get('tool')), boolean(raw.get('enabled')),
                   text(raw.get('action')), status, filament, locked,
                   values('gate_status', lambda v: integer(v) if integer(v) in (-1, 0, 1, 2) else None),
                   values('ttg_map', index), values('gate_material', lambda v: text(v, '--')),
                   values('gate_filament_name', lambda v: text(v, '--')),
                   values('gate_temperature', lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None),
                   values('gate_spool_id', integer),
                   tuple(sorted((str(k), boolean(v)) for k, v in sensors.items())),
                   boolean(raw.get('sync_drive')), progress,
                   text(raw.get('reason_for_pause'), ''), text(raw.get('spoolman_support'), 'off'))

    @property
    def busy(self):
        return self.action.lower() != 'idle'

    @property
    def fingerprint(self):
        return (self.epoch, self.num_gates, self.gate, self.tool, self.enabled,
                self.action, self.print_state, self.filament, self.locked,
                self.gate_status, self.ttg_map)

    def tools_for_gate(self, gate):
        return tuple(i for i, mapped in enumerate(self.ttg_map) if mapped == gate)


@dataclass(frozen=True)
class MMUOperation:
    action: str
    gate: int | None
    tool: int | None
    loaded: bool | None
    fingerprint: tuple
    script: str
    label: str


class MMUSession:
    TIMEOUT = 300.0
    GATE_ACTIONS = {'select', 'load', 'change', 'unload', 'eject', 'preload', 'check'}
    RECOVERY_ACTIONS = {'recover', 'manual', 'unlock', 'resume'}

    def __init__(self, printer):
        self.printer = printer
        self.pending = None
        self.phase, self.message = 'idle', ''
        self.operation = None
        self._cursor = None

    @property
    def state(self):
        return MMUState.from_snapshot(self.printer.subscription.snapshot())

    def prepare(self, action, gate=None, tool=None, loaded=None, snapshot=None, ignore_pending=False):
        p = self.printer
        snap = p.subscription.snapshot() if snapshot is None else snapshot
        m = MMUState.from_snapshot(snap)
        if (p.connection_error or not p.state.ready or snap.get('epoch') != p.state.epoch
                or m is None or not p.mmu):
            raise ValueError('MMU unavailable')
        if self.pending is not None and not ignore_pending:
            raise ValueError('Wait for MMU operation')
        if self.phase == 'error':
            raise ValueError('Acknowledge MMU result first')
        if m.enabled is not True:
            raise ValueError('MMU disabled or unknown')
        if m.busy or p.jog_recovery_required:
            raise ValueError('MMU busy or recovery needed')
        if snap.get('status', {}).get('manual_probe', {}).get('is_active') or any(
                getattr(getattr(p, name, None), 'pending', None)
                for name in ('bed_mesh', 'screws_tilt', 'probe_wizard')):
            raise ValueError('Another operation is active')
        ps = snap.get('status', {}).get('print_stats', {}).get('state')
        if ps not in ('standby', 'complete', 'cancelled', 'error', 'paused', 'printing'):
            raise ValueError('Print state unknown')
        if ps == 'printing' or m.print_state in ('started', 'printing'):
            raise ValueError('Printing; monitoring only')
        if action not in self.RECOVERY_ACTIONS:
            if ps == 'paused' or m.print_state in ('paused', 'pause_locked'):
                raise ValueError('Use recovery during a pause')
            if m.locked is not False:
                raise ValueError('MMU lock state unknown')
        elif m.locked is None:
            raise ValueError('MMU lock state unknown')
        if action in self.GATE_ACTIONS:
            if integer(gate) is None or not 0 <= gate < m.num_gates:
                raise ValueError('Invalid gate')
            target = 'G%d' % (gate + 1)
        else:
            target = ''
        if action in ('select', 'load', 'preload', 'check', 'bypass') and m.filament != 'unloaded':
            raise ValueError('Unload filament first')
        if action in ('unload', 'unload_extruder') and m.filament != 'loaded':
            raise ValueError('Loaded filament required')
        if action == 'select':
            script, label = 'MMU_SELECT GATE=%d' % gate, 'Select ' + target
        elif action == 'load':
            if gate != m.gate or m.gate_status[gate] not in (1, 2):
                raise ValueError('Select an available gate first')
            script, label = 'MMU_LOAD', 'Load ' + target
        elif action == 'change':
            tools = m.tools_for_gate(gate)
            if not tools or m.gate_status[gate] not in (1, 2) or m.filament == 'unknown' or m.gate == -2:
                raise ValueError('Mapped available gate required')
            tool = m.tool if m.tool in tools else tools[0]
            script, label = 'MMU_CHANGE_TOOL TOOL=%d STANDALONE=1' % tool, 'Load/change T%d / %s' % (tool, target)
        elif action == 'unload':
            if gate != m.gate:
                raise ValueError('Unload the current gate')
            script, label = 'MMU_UNLOAD', 'Unload ' + target
        elif action == 'eject':
            if m.filament == 'unknown' or (m.filament == 'loaded' and gate != m.gate):
                raise ValueError('Unload current filament first')
            # FORCE explicitly ejects the spool after unloading the current gate.
            script, label = 'MMU_EJECT GATE=%d FORCE=1' % gate, 'Eject spool ' + target
        elif action in ('preload', 'check'):
            script = '%s GATE=%d' % ('MMU_PRELOAD' if action == 'preload' else 'MMU_CHECK_GATE', gate)
            label = action.title() + ' ' + target
        elif action == 'bypass':
            script, label = 'MMU_SELECT BYPASS=1', 'Select bypass'
        elif action in ('load_extruder', 'unload_extruder'):
            if m.gate != -2:
                raise ValueError('Select bypass first')
            if action == 'load_extruder' and m.filament != 'unloaded':
                raise ValueError('Unload filament first')
            script = ('MMU_LOAD' if action == 'load_extruder' else 'MMU_UNLOAD') + ' EXTRUDER_ONLY=1'
            label = action.replace('_', ' ').title()
        elif action == 'recover':
            script, label = 'MMU_RECOVER', 'Auto recover'
        elif action == 'manual':
            if integer(tool) is None or integer(gate) is None or not 0 <= tool < m.num_gates or not 0 <= gate < m.num_gates or not isinstance(loaded, bool):
                raise ValueError('Choose actual tool/gate/state')
            script = 'MMU_RECOVER TOOL=%d GATE=%d LOADED=%d' % (tool, gate, loaded)
            label = 'Set T%d / G%d %s' % (tool, gate + 1, 'loaded' if loaded else 'unloaded')
        elif action == 'unlock':
            if m.locked is not True:
                raise ValueError('MMU is not locked')
            script, label = 'MMU_UNLOCK', 'Unlock / reheat'
        elif action == 'resume':
            if ps != 'paused' or m.locked is not False or m.filament != 'loaded':
                raise ValueError('Recover and unlock first')
            script, label = 'RESUME', 'Resume print'
        else:
            raise ValueError('Unsupported MMU operation')
        return MMUOperation(action, gate, tool, loaded, m.fingerprint, script, label)

    def start(self, operation):
        fresh = self.prepare(operation.action, operation.gate, operation.tool, operation.loaded)
        if fresh != operation:
            raise ValueError('MMU changed; select again')
        self.operation = operation
        self.started = time.monotonic()
        self._cursor, _ = self.printer.subscription.responses_since(None)
        self._dispatch_operation = operation
        self.pending = self.printer.subscription.request(
            'printer.gcode.script', {'script': operation.script}, guard=self._dispatch_guard)
        self.phase, self.message = 'running', 'Waiting: ' + operation.label

    def _dispatch_guard(self):
        try:
            op = self._dispatch_operation
            return self.prepare(op.action, op.gate, op.tool, op.loaded,
                                ignore_pending=True) == op
        except ValueError:
            return False

    def _fail(self, message):
        if self.pending is not None:
            self.pending.cancel()  # Cancels a queued request; never replays motion.
        self.pending = None
        self.phase, self.message = 'error', message

    def _confirmed(self, m, status):
        op = self.operation
        if op.action == 'resume':
            return status.get('print_stats', {}).get('state') == 'printing' and m.locked is False
        if op.action == 'unlock':
            return m.locked is False
        if op.action == 'manual':
            return (m.tool == op.tool and m.gate == op.gate and
                    m.filament == ('loaded' if op.loaded else 'unloaded'))
        if op.action == 'recover':
            return m.filament != 'unknown'
        if m.locked is not False:
            return False
        if op.action == 'select': return m.gate == op.gate and m.filament == 'unloaded'
        if op.action == 'bypass': return m.gate == -2 and m.filament == 'unloaded'
        if op.action in ('load', 'change'): return m.gate == op.gate and m.filament == 'loaded' and (op.action != 'change' or m.tool == op.tool)
        if op.action in ('unload', 'unload_extruder'): return m.filament == 'unloaded'
        if op.action == 'load_extruder': return m.gate == -2 and m.filament == 'loaded'
        if op.action == 'eject': return m.gate_status[op.gate] == 0
        if op.action in ('preload', 'check'): return m.gate_status[op.gate] in (0, 1, 2) and m.filament == 'unloaded'
        return False

    def update(self):
        if self.pending is None:
            return
        p = self.printer
        m = self.state
        if p.connection_error or m is None or m.epoch != self.operation.fingerprint[0]:
            self._fail('Connection changed; check MMU')
            return
        if time.monotonic() - self.started > self.TIMEOUT:
            self._fail('Result unconfirmed; check MMU')
            return
        self._cursor, responses = p.subscription.responses_since(self._cursor)
        error = next((line for line in responses if line.startswith('!!')), None)
        if error:
            self._fail(error[2:].strip() or 'MMU command failed')
            return
        if not self.pending.done():
            return
        try:
            result = self.pending.result()
            if self.phase == 'running':
                self.pending = p.subscription.request('printer.objects.query',
                    {'objects': {'mmu': None, 'print_stats': None}})
                self.phase, self.message = 'confirming', 'Checking MMU result'
                return
            status = result['status']
            snap = p.subscription.snapshot()
            snap = dict(snap, status=dict(snap['status'], **status))
            m = MMUState.from_snapshot(snap)
            if (m is None or m.epoch != self.operation.fingerprint[0]
                    or m.enabled is not True or m.busy or not self._confirmed(m, status)):
                self._fail(m.reason if m and m.reason else 'State unconfirmed; check MMU')
                return
        except Exception:
            self._fail('Command failed; check MMU/log')
            return
        self.pending = None
        self.phase, self.message = 'complete', 'Completed: ' + self.operation.label
