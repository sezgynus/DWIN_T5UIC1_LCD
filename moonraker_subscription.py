"""Read-only Moonraker JSON-RPC subscription with reconnect and delta merging.

This transport never sends printer commands. HTTP remains the command transport;
losing a subscription cannot replay a movement or start a print.
"""
import copy
import json
import math
import socket
import time
from threading import Event, Lock, Thread
from urllib.parse import urlsplit, urlunsplit

from moonraker_client import MoonrakerError


OBJECTS = ('webhooks', 'toolhead', 'gcode_move', 'print_stats', 'virtual_sdcard',
           'pause_resume', 'extruder', 'heater_bed', 'fan', 'manual_probe')


def connect(url, timeout, headers):
    # Lazy import keeps tests hardware/network independent.
    import websocket
    try:
        return websocket.create_connection(url, timeout=timeout, header=headers,
                                           redirect_limit=0)
    except websocket.WebSocketException as exc:
        raise MoonrakerError('WebSocket connection failed') from exc


class MoonrakerSubscription:
    def __init__(self, url, api_key='', timeout=5.0, connector=connect,
                 retry_delay=1.0, autostart=True):
        parts = urlsplit(url)
        if (parts.scheme not in ('http', 'https') or not parts.hostname
                or parts.username or parts.password or parts.query or parts.fragment):
            raise ValueError('Invalid Moonraker URL')
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Timeout must be finite and positive')
        if not math.isfinite(retry_delay) or retry_delay <= 0:
            raise ValueError('Retry delay must be finite and positive')
        self.url = urlunsplit(('wss' if parts.scheme == 'https' else 'ws',
                              parts.netloc, parts.path.rstrip('/') + '/websocket', '', ''))
        self._headers = ['X-Api-Key: ' + api_key] if api_key else []
        self._api_key = api_key
        self.timeout = timeout
        self.retry_delay = retry_delay
        self._connector = connector
        self._stop = Event()
        self._lock = Lock()
        self._socket = None
        self._state = 'connecting'
        self._error = 'Moonraker subscription is connecting'
        self._status = {}
        self._objects = []
        self._settings = {}
        self._software_version = 'unknown'
        self._eventtime = None
        self._id = 0
        self._epoch = 0
        self._revision = 0
        self._file_revision = 0
        self._subscribing = False
        self._buffered = []
        self._last_receive = time.monotonic()
        self._last_ping = time.monotonic()
        self._thread = Thread(target=self._run, name='moonraker-status', daemon=True)
        if autostart:
            self._thread.start()

    def snapshot(self):
        with self._lock:
            return {'state': self._state, 'error': self._error,
                    'status': copy.deepcopy(self._status),
                    'objects': list(self._objects), 'revision': self._revision, 'epoch': self._epoch,
                    'software_version': self._software_version, 'settings': copy.deepcopy(self._settings),
                    'file_revision': self._file_revision}

    def _invalidate(self, error):
        with self._lock:
            self._state = 'disconnected'
            self._error = error
            self._status = {}
            self._objects = []
            self._settings = {}
            self._eventtime = None
            self._revision += 1
            self._epoch += 1

    def _merge(self, status, eventtime, replace=False):
        if (not isinstance(status, dict) or not isinstance(eventtime, (int, float))
                or not math.isfinite(eventtime)
                or not all(isinstance(value, dict) for value in status.values())):
            raise MoonrakerError('Invalid status notification')
        with self._lock:
            if not replace and self._eventtime is not None and eventtime < self._eventtime:
                return
            if replace:
                self._status = copy.deepcopy(status)
            else:
                for name, fields in status.items():
                    self._status.setdefault(name, {}).update(copy.deepcopy(fields))
            self._eventtime = eventtime
            self._revision += 1

    def _notification(self, message):
        method = message.get('method')
        params = message.get('params', [])
        if method == 'notify_status_update':
            if not isinstance(params, list) or len(params) != 2:
                raise MoonrakerError('Invalid status notification')
            if self._subscribing:
                self._buffered.append(params)
                if len(self._buffered) > 256:
                    raise MoonrakerError('Subscription bootstrap overflow')
            else:
                self._merge(*params)
            webhooks = params[0].get('webhooks', {}) if isinstance(params[0], dict) else {}
            if 'state' in webhooks and webhooks['state'] != 'ready':
                raise MoonrakerError('Klipper is not ready')
        elif method in ('notify_klippy_disconnected', 'notify_klippy_shutdown',
                         'notify_klippy_ready'):
            # Obtain a fresh object list and snapshot on every lifecycle epoch.
            raise MoonrakerError('Klipper lifecycle changed; resubscribing')
        elif method == 'notify_filelist_changed':
            with self._lock:
                self._file_revision += 1

    def _receive(self):
        # websocket-client exposes pong frames here, enabling idle liveness checks.
        try:
            opcode, data = self._socket.recv_data(control_frame=True)
        except Exception as exc:
            # websocket-client's timeout class is distinct from socket.timeout.
            if isinstance(exc, (socket.timeout, TimeoutError)) or type(exc).__name__ == 'WebSocketTimeoutException':
                return None
            raise MoonrakerError('WebSocket receive failed') from exc
        self._last_receive = time.monotonic()
        if opcode == 8:
            raise MoonrakerError('WebSocket closed')
        if opcode in (9, 10):
            return None
        if opcode != 1:
            raise MoonrakerError('Expected JSON text frame')
        try:
            message = json.loads(data)
        except (ValueError, UnicodeError) as exc:
            raise MoonrakerError('Invalid WebSocket JSON') from exc
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
            raise MoonrakerError('Invalid JSON-RPC envelope')
        return message

    def _rpc(self, method, params=None):
        self._id += 1
        request_id = self._id
        self._socket.send(json.dumps({'jsonrpc': '2.0', 'id': request_id,
                                      'method': method, 'params': params or {}}))
        deadline = time.monotonic() + self.timeout
        while not self._stop.is_set() and time.monotonic() < deadline:
            message = self._receive()
            if message is None:
                continue
            if 'method' in message:
                self._notification(message)
            elif message.get('id') == request_id:
                if 'error' in message or 'result' not in message:
                    raise MoonrakerError('Moonraker RPC failed: ' + method)
                return message['result']
        raise MoonrakerError('Moonraker RPC timed out: ' + method)

    def _bootstrap(self):
        identify = {'client_name': 'DWIN_T5UIC1_LCD', 'version': 'refactor',
                    'type': 'display', 'url': 'https://github.com/sezgynus/DWIN_T5UIC1_LCD'}
        if self._api_key:
            identify['api_key'] = self._api_key
        self._rpc('server.connection.identify', identify)
        info = self._rpc('server.info')
        if not isinstance(info, dict) or info.get('klippy_state') != 'ready':
            raise MoonrakerError('Klipper is not ready')
        printer_info = self._rpc('printer.info')
        if not isinstance(printer_info, dict):
            raise MoonrakerError('Invalid printer info')
        objects = self._rpc('printer.objects.list')
        if not isinstance(objects, dict) or not isinstance(objects.get('objects'), list):
            raise MoonrakerError('Invalid printer object list')
        names = objects['objects']
        if not all(isinstance(name, str) for name in names) or 'configfile' not in names:
            raise MoonrakerError('Configuration object is unavailable')
        available = [name for name in names if name in OBJECTS or
                     (name.startswith('extruder') and name[8:].isdigit())]
        config = self._rpc('printer.objects.query', {'objects': {'configfile': ['settings']}})
        try:
            settings = config['status']['configfile']['settings']
        except (KeyError, TypeError):
            raise MoonrakerError('Effective configuration is unavailable')
        if not isinstance(settings, dict):
            raise MoonrakerError('Invalid effective configuration')
        required = {'toolhead', 'gcode_move', 'print_stats', 'virtual_sdcard'}
        if not required.issubset(available):
            raise MoonrakerError('Required printer objects are unavailable')
        self._subscribing = True
        self._buffered = []
        try:
            result = self._rpc('printer.objects.subscribe',
                               {'objects': {name: None for name in available}})
            if not isinstance(result, dict):
                raise MoonrakerError('Invalid subscription response')
            self._merge(result.get('status'), result.get('eventtime'), replace=True)
            for delta in self._buffered:
                self._merge(*delta)
        finally:
            self._subscribing = False
            self._buffered = []
        with self._lock:
            if self._status.get('webhooks', {}).get('state', 'ready') != 'ready':
                raise MoonrakerError('Klipper is not ready')
            self._objects = names
            self._settings = copy.deepcopy(settings)
            self._software_version = printer_info.get('software_version', 'unknown')
            self._state = 'ready'
            self._error = None

    def _run(self):
        while not self._stop.is_set():
            try:
                connection = self._connector(self.url, self.timeout, self._headers)
                with self._lock:
                    if self._stop.is_set():
                        connection.close()
                        break
                    self._socket = connection
                connection.settimeout(min(self.timeout, 1.0))
                self._last_receive = self._last_ping = time.monotonic()
                self._bootstrap()
                while not self._stop.is_set():
                    message = self._receive()
                    if message is not None:
                        self._notification(message)
                    now = time.monotonic()
                    if now - self._last_receive > 45:
                        raise MoonrakerError('WebSocket heartbeat timed out')
                    if now - self._last_ping > 15:
                        self._socket.ping()
                        self._last_ping = now
            except Exception:
                # Do not log exception payloads: connector errors may contain headers.
                self._invalidate('Moonraker subscription unavailable')
            finally:
                with self._lock:
                    connection, self._socket = self._socket, None
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        pass
            self._stop.wait(self.retry_delay)

    def close(self):
        self._stop.set()
        with self._lock:
            connection = self._socket
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        if self._thread.is_alive():
            self._thread.join(timeout=self.timeout + 1)
        self._invalidate('Moonraker subscription is closed')
