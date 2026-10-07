"""Render/UART measurement helpers used by Phase 2 performance tests."""
from collections import Counter
from dataclasses import dataclass
import time


@dataclass(frozen=True)
class RenderMetrics:
    packets: int
    bytes: int
    refreshes: int
    opcodes: tuple
    duration_ms: float

    @classmethod
    def measure(cls, lcd, operation):
        frames = lcd.serial.frames
        start_index = len(frames)
        started = time.perf_counter()
        operation()
        duration_ms = (time.perf_counter() - started) * 1000.0
        emitted = frames[start_index:]
        counts = Counter(frame[1] for frame in emitted if len(frame) > 1)
        return cls(
            packets=len(emitted),
            bytes=sum(len(frame) for frame in emitted),
            refreshes=counts.get(0x3D, 0),
            opcodes=tuple(sorted(counts.items())),
            duration_ms=duration_ms,
        )

    def summary(self):
        opcode_text = ', '.join('0x%02X:%d' % item for item in self.opcodes)
        return ('%d packets / %d bytes / %.3f ms / %d refresh'
                ' | %s' % (self.packets, self.bytes, self.duration_ms,
                           self.refreshes, opcode_text))
