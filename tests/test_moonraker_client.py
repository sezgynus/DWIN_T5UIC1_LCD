import json
from threading import Event
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from moonraker_client import MoonrakerClient, MoonrakerError


def response(body):
    value = Mock()
    value.__enter__ = Mock(return_value=value)
    value.__exit__ = Mock(return_value=False)
    value.read.return_value = json.dumps(body).encode()
    return value


class TransportTests(unittest.TestCase):
    def client(self, opener=None, **kwargs):
        client = MoonrakerClient(opener=opener or Mock(), **kwargs)
        self.addCleanup(client.close)
        return client

    def test_get_timeout_and_optional_auth(self):
        opener = Mock()
        opener.open.return_value = response({'result': {'state': 'ready'}})
        client = self.client(opener, url='http://localhost:7125', timeout=2)
        self.assertEqual(client.get('/printer/info')['result']['state'], 'ready')
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'http://localhost:7125/printer/info')
        self.assertFalse(request.has_header('X-api-key'))
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 2)

    def test_explicit_auth(self):
        opener = Mock()
        opener.open.return_value = response({'result': 'ok'})
        self.client(opener, api_key='test-key').get('/printer/info')
        self.assertEqual(opener.open.call_args.args[0].get_header('X-api-key'), 'test-key')

    def test_http_error_and_recovery(self):
        opener = Mock()
        opener.open.side_effect = [HTTPError('url', 401, 'Unauthorized', {}, None), response({'result': 'ok'})]
        client = self.client(opener)
        with self.assertRaisesRegex(MoonrakerError, '401'):
            client.get('/printer/info')
        self.assertFalse(client.connected)
        self.assertEqual(client.get('/printer/info'), {'result': 'ok'})
        self.assertTrue(client.connected)
        self.assertIsNone(client.last_error)

    def test_invalid_json_and_error_envelope(self):
        for body in (b'not json', b'[]', b'{"error":{"message":"failed"}}'):
            with self.subTest(body=body):
                opener = Mock()
                value = response({})
                value.read.return_value = body
                opener.open.return_value = value
                with self.assertRaises(MoonrakerError):
                    self.client(opener).get('/printer/info')

    def test_failed_command_is_not_replayed_and_pending_are_discarded(self):
        entered, release = Event(), Event()
        opener = Mock()
        def timeout(*args, **kwargs):
            entered.set()
            if not release.wait(2):
                raise AssertionError('test synchronization timed out')
            raise URLError('timeout')
        opener.open.side_effect = timeout
        client = self.client(opener)
        first = client.post('/printer/gcode/script', {'script': 'G28'})
        self.assertTrue(entered.wait(2))
        second = client.post('/printer/gcode/script', {'script': 'G1 Z0'})
        release.set()
        with self.assertRaises(MoonrakerError):
            first.result(2)
        with self.assertRaisesRegex(MoonrakerError, 'preceding command failure'):
            second.result(2)
        self.assertEqual(opener.open.call_count, 1)

    def test_post_returns_result(self):
        opener = Mock()
        opener.open.return_value = response({'result': 'ok'})
        client = self.client(opener)
        future = client.post('/printer/print/resume')
        self.assertEqual(future.result(2), {'result': 'ok'})
        self.assertEqual(opener.open.call_args.args[0].method, 'POST')

    def test_close_is_idempotent_and_rejects_new_commands(self):
        opener = Mock()
        client = self.client(opener)
        client.close()
        client.close()
        self.assertFalse(client._worker.is_alive())
        with self.assertRaisesRegex(MoonrakerError, 'closed'):
            client.post('/printer/print/start').result()
        opener.open.assert_not_called()

    def test_silent_immediate_rejection_does_not_report_command_error(self):
        opener = Mock()
        client = self.client(opener)
        client.close()

        future = client.post('/server/spoolman/proxy', {}, report_error=False)

        with self.assertRaisesRegex(MoonrakerError, 'closed'):
            future.result()
        self.assertTrue(client.command_results.empty())
        opener.open.assert_not_called()

    def test_invalid_configuration(self):
        for url in ('file:///tmp/socket', 'http://user:key@localhost', 'http://localhost?key=secret'):
            with self.assertRaises(ValueError):
                MoonrakerClient(url=url)
        for timeout in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                MoonrakerClient(timeout=timeout)

    def test_invalid_path_does_not_send(self):
        opener = Mock()
        client = self.client(opener)
        with self.assertRaises(ValueError):
            client.get('printer/info')
        opener.open.assert_not_called()
