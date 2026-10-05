"""Bounded HTTP transport and serialized, observable command execution."""
from concurrent.futures import Future
import json
import math
from queue import Queue, Full, Empty
from threading import Event, Lock, Thread
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class MoonrakerError(RuntimeError):
    """A request failed; a failed POST may already have executed on the printer."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward credentials or replay commands through redirects.
        return None


class MoonrakerClient:
    def __init__(self, url='http://127.0.0.1:7125', api_key='', timeout=5.0,
                 queue_size=32, opener=None):
        parts = urlsplit(url)
        if (parts.scheme not in ('http', 'https') or not parts.hostname
                or parts.username or parts.password or parts.query or parts.fragment):
            raise ValueError('Moonraker URL must be an HTTP(S) URL without credentials/query/fragment')
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Timeout must be finite and positive')
        if queue_size < 1:
            raise ValueError('Queue size must be positive')
        self.url = url.rstrip('/')
        self.timeout = timeout
        self.headers = {'Content-Type': 'application/json'}
        if api_key:
            self.headers['X-Api-Key'] = api_key
        self._opener = opener or build_opener(NoRedirects())
        self._queue = Queue(maxsize=queue_size)
        self._stop = Event()
        self._lock = Lock()
        self.connected = False
        self.last_error = None
        self.command_results = Queue()
        self._worker = Thread(target=self._run, name='moonraker-commands', daemon=True)
        self._worker.start()

    def request(self, method, path, payload=None):
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('Endpoint path must start with a single slash')
        if self._stop.is_set():
            raise MoonrakerError('Client is closed')
        data = None if method == 'GET' else json.dumps(payload).encode('utf-8')
        request = Request(self.url + path, data=data, headers=self.headers, method=method)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode('utf-8'))
            if not isinstance(body, dict) or 'error' in body or 'result' not in body:
                raise MoonrakerError('Invalid response or Moonraker error')
        except HTTPError as exc:
            error = MoonrakerError('Moonraker HTTP status %s' % exc.code)
        except (URLError, OSError, ValueError, MoonrakerError):
            error = MoonrakerError('Moonraker request failed (network or invalid response)')
        else:
            self.connected = True
            self.last_error = None
            return body
        self.connected = False
        self.last_error = error
        raise error

    def get(self, path):
        # Each polling attempt opens a fresh request: recovery needs no restart.
        return self.request('GET', path)

    def post(self, path, payload=None, guard=None):
        future = Future()
        with self._lock:
            if self._stop.is_set():
                future.set_exception(MoonrakerError('Client is closed'))
            else:
                try:
                    self._queue.put_nowait((future, path, payload, guard))
                except Full:
                    future.set_exception(MoonrakerError('Command queue is full'))
        if future.done():
            self.command_results.put((path, future))
        return future

    def _discard_pending(self, message):
        while True:
            try:
                future, path, _, _ = self._queue.get_nowait()
            except Empty:
                return
            if not future.done():
                future.set_exception(MoonrakerError(message))
            self.command_results.put((path, future))
            self._queue.task_done()

    def _run(self):
        while not self._stop.is_set():
            try:
                future, path, payload, guard = self._queue.get(timeout=0.1)
            except Empty:
                continue
            if self._stop.is_set():
                future.cancel()
            elif future.set_running_or_notify_cancel():
                try:
                    if guard is not None and not guard():
                        raise MoonrakerError('Printer connection changed before command execution')
                    future.set_result(self.request('POST', path, payload))
                except Exception as exc:
                    future.set_exception(exc)
                    # A timed-out POST is ambiguous. Never replay it or execute
                    # dependent commands that were queued behind it.
                    with self._lock:
                        self._discard_pending('Cancelled after preceding command failure')
            self.command_results.put((path, future))
            self._queue.task_done()

    def close(self):
        with self._lock:
            self._stop.set()
            self._discard_pending('Client is closed')
        self._worker.join(timeout=self.timeout + 1)
