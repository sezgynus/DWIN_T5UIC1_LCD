"""UI command result tracking; transport acceptance is not physical completion."""
import time


class CommandFeedback:
    def __init__(self, future, label, epoch, expected=None, confirmation_timeout=300.0):
        self.future, self.label, self.epoch, self.expected = future, label, epoch, expected
        self.confirmation_timeout = float(confirmation_timeout)
        if self.confirmation_timeout <= 0:
            raise ValueError('Confirmation timeout must be positive')
        self.started = time.monotonic()
        self.phase = 'waiting'
        self.message = 'Waiting: ' + label

    def update(self, state, unavailable=False):
        if self.phase != 'waiting':
            return self.phase
        if unavailable or not state.ready or state.epoch != self.epoch:
            self.phase, self.message = 'error', 'Connection changed; check printer'
        elif self.future.done():
            if self.future.cancelled():
                self.phase, self.message = 'error', 'Command cancelled; check printer'
            elif self.future.exception():
                self.phase, self.message = 'error', 'Command failed; check log'
            elif self.expected is None or self.expected():
                self.phase, self.message = 'accepted', 'Accepted: ' + self.label
            elif time.monotonic() - self.started > self.confirmation_timeout:
                self.phase, self.message = 'error', 'State unconfirmed; check printer'
        if (self.phase == 'waiting' and self.expected is None
                and time.monotonic() - self.started > 30):
            self.future.cancel()
            self.phase, self.message = 'error', 'Result unconfirmed; check printer'
        return self.phase
