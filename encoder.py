# Class to monitor a rotary encoder and update a value using gpiozero + LGPIOFactory.
from gpiozero import Device, RotaryEncoder
from gpiozero.pins.lgpio import LGPIOFactory
from threading import Lock

# Use LGPIO as pin factory to avoid RPi.GPIO edge detection issues
Device.pin_factory = LGPIOFactory()

class Encoder:

    def __init__(self, leftPin, rightPin, callback=None):
        self.value = 0
        self.state = '00'
        self.direction = None
        self.callback = callback
        self.lock = Lock()  # thread-safe update

        # Rotary encoder
        self.encoder = RotaryEncoder(a=leftPin, b=rightPin, max_steps=0)
        self.encoder.when_rotated = self._rotated

    def _rotated(self):
        with self.lock:
            if self.encoder.steps > 0:
                self.direction = "R"
                self.value += 1
            elif self.encoder.steps < 0:
                self.direction = "L"
                self.value -= 1

            # reset steps to zero for next rotation detection
            self.encoder.steps = 0

            # call user callback
            if self.callback is not None:
                self.callback(self.value)

    # Keep for compatibility, not used in gpiozero
    def transitionOccurred(self, channel):
        pass

    def getValue(self):
        return self.value

    def close(self):
        self.encoder.when_rotated = None
        self.callback = None
        self.encoder.close()
