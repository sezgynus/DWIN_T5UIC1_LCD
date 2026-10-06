import socket
import unittest
from unittest.mock import Mock, patch

import system_info


class SystemInfoTests(unittest.TestCase):
    def test_updater_version_prefers_full_git_description(self):
        versions = {'KlipperDWIN': {
            'version': 'v0.4.0-2',
            'full_version_string': 'v0.4.0-2-g1234abcd',
        }}
        self.assertEqual(
            system_info.updater_version(versions, 'KlipperDWIN', full=True),
            'v0.4.0-2-g1234abcd')

    def test_updater_version_handles_missing_component(self):
        self.assertEqual(system_info.updater_version({}, 'mainsail'), 'Unavailable')

    @patch.object(system_info.socket, 'if_nameindex', return_value=[(1, 'lo'), (2, 'eth0')])
    @patch.object(system_info.fcntl, 'ioctl')
    def test_network_info_selects_active_non_loopback_ipv4(self, ioctl, _interfaces):
        def response(_fd, request, packed):
            name = packed.split(b'\\0', 1)[0]
            if request == system_info.SIOCGIFFLAGS:
                flags = (system_info.IFF_UP | system_info.IFF_LOOPBACK
                         if name == b'lo' else system_info.IFF_UP)
                return b'\\0' * 16 + flags.to_bytes(2, 'little') + b'\\0' * 238
            if request == system_info.SIOCGIFADDR:
                return b'\\0' * 20 + socket.inet_aton('192.168.1.50') + b'\\0' * 232
            raise AssertionError(request)
        ioctl.side_effect = response
        self.assertEqual(system_info.network_info(), ('Online', '192.168.1.50'))


if __name__ == '__main__':
    unittest.main()
