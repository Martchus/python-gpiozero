from __future__ import division

from time import sleep
from threading import Event
from collections import deque

from RPi import GPIO
from w1thermsensor import W1ThermSensor

from .devices import GPIODeviceError, GPIODevice, GPIOThread


class InputDeviceError(GPIODeviceError):
    pass


class InputDevice(GPIODevice):
    def __init__(self, pin=None):
        super(InputDevice, self).__init__(pin)
        self._pull = GPIO.PUD_UP
        self._edge = GPIO.FALLING
        self._active_state = 0
        self._inactive_state = 1
        GPIO.setup(pin, GPIO.IN, self._pull)

    @property
    def is_active(self):
        return GPIO.input(self.pin) == self._active_state

    def wait_for_input(self):
        GPIO.wait_for_edge(self.pin, self._edge)

    def add_callback(self, callback=None, bouncetime=1000):
        if callback is None:
            raise InputDeviceError('No callback function given')
        GPIO.add_event_detect(self.pin, self._edge, callback, bouncetime)

    def remove_callback(self):
        GPIO.remove_event_detect(self.pin)


class Button(InputDevice):
    pass


class MotionSensor(InputDevice):
    def __init__(self, pin=None, queue_len=20, sample_rate=10, partial=False):
        super(MotionSensor, self).__init__(pin)
        self.sample_rate = sample_rate
        self.partial = partial
        self._queue = deque(maxlen=queue_len)
        self._queue_full = Event()
        self._queue_thread = GPIOThread(target=self._fill_queue)
        self._queue_thread.start()

    @property
    def queue_len(self):
        return self._queue.maxlen

    def _fill_queue(self):
        while (
                not self._queue_thread.stopping.wait(1 / self.sample_rate) and
                len(self._queue) < self._queue.maxlen
            ):
            self._queue.append(self.is_active)
        self._queue_full.set()
        while not self._queue_thread.stopping.wait(1 / self.sample_rate):
            self._queue.append(self.is_active)

    @property
    def motion_detected(self):
        if not self.partial:
            self._queue_full.wait()
        return sum(self._queue) > (len(self._queue) / 2)


class LightSensor(object):
    def __init__(self, pin=None, darkness_level=0.01):
        if pin is None:
            raise InputDeviceError('No GPIO pin number given')

        self._pin = pin
        self.darkness_level = darkness_level

    @property
    def pin(self):
        return self._pin

    @property
    def value(self):
        return self._get_average_light_level(5)

    def _get_light_level(self):
        time_taken = self._time_charging_light_capacitor()
        value = 100 * time_taken / self.darkness_level
        return 100 - value

    def _time_charging_light_capacitor(self):
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)
        sleep(0.1)
        GPIO.setup(self.pin, GPIO.IN)
        start_time = time()
        end_time = time()
        while (
            GPIO.input(self.pin) == GPIO.LOW and
            time() - start_time < self.darkness_level
        ):
            end_time = time()
        time_taken = end_time - start_time
        return min(time_taken, self.darkness_level)

    def _get_average_light_level(self, num):
        values = [self._get_light_level() for n in range(num)]
        average_value = sum(values) / len(values)
        return average_value


class TemperatureSensor(W1ThermSensor):
    @property
    def value(self):
        return self.get_temperature()


