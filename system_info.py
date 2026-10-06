"""Live software-stack and Raspberry Pi network information."""
import socket
import struct
from urllib.parse import urlsplit

try:
    import fcntl
except ImportError:  # pragma: no cover - Linux/Raspberry Pi runtime
    fcntl = None

SIOCGIFFLAGS = 0x8913
SIOCGIFADDR = 0x8915
IFF_UP = 0x1
IFF_LOOPBACK = 0x8


def network_info():
    """Return (status, IPv4) for the first active non-loopback IPv4 interface."""
    if fcntl is None:
        return 'Unknown', 'Unavailable'
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for _, name in socket.if_nameindex():
            encoded = name.encode('utf-8')[:15]
            request = struct.pack('256s', encoded)
            try:
                flags = struct.unpack('H', fcntl.ioctl(sock.fileno(), SIOCGIFFLAGS, request)[16:18])[0]
                if not flags & IFF_UP or flags & IFF_LOOPBACK:
                    continue
                address = socket.inet_ntoa(
                    fcntl.ioctl(sock.fileno(), SIOCGIFADDR, request)[20:24])
                return 'Online', address
            except OSError:
                continue
    finally:
        sock.close()
    return 'Offline', 'Unavailable'


def updater_version(version_info, name, full=False):
    item = version_info.get(name, {})
    if not isinstance(item, dict):
        return 'Unavailable'
    if full:
        value = item.get('full_version_string') or item.get('version')
    else:
        value = item.get('version') or item.get('full_version_string')
    return str(value) if value else 'Unavailable'
