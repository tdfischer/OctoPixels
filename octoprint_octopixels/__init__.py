from __future__ import absolute_import
import octoprint.plugin
from enum import Enum
import time
from . import opc
import colorsys
import multiprocessing

def scaled(rgb):
    return map(lambda x: x * 255, rgb)

class PixelsState(Enum):
    Sleep = 1
    Disconnected = 2
    Idle = 3
    Printing = 4
    Error = 5

class Animator(object):
    def __init__(self):
        super(Animator, self).__init__()
        self.queue = multiprocessing.Queue()
        self.proc = multiprocessing.Process(target=self.run, args=(self.queue,))
        self.client = opc.Client('octopi.local:7890')
        self.state = PixelsState.Sleep
        self.numLEDs = 14
        self.runFlag = True
        self.frame = 0
        self.last_render = 0
        self.active_stamp = 0

    def stop(self):
        self.queue.put(False)
        self.proc.join()

    def start(self):
        self.proc.start()

    def set_state(self, new_state):
        self.queue.put(new_state)

    def touch(self):
        self.queue.put(0)

    def _touch(self):
        self.active_stamp = time.time()
        if self.state == PixelsState.Sleep:
            self.state = PixelsState.Idle

    def run(self, queue):
        self._touch()
        while self.runFlag:
            if not queue.empty():
                evt = queue.get()
                if evt is False:
                    return
                elif evt is 0:
                    self._touch()
                else:
                    self.state = evt
                    self._touch()

            if self.state == PixelsState.Printing:
                self._touch()

            idleTime = time.time() - self.active_stamp
            if idleTime >= 10:
                    self.state = PixelsState.Sleep
            self.render()

    def render(self):
        frameDelay = time.time() - self.last_render
        if frameDelay >= 0.01:
            self.frame += 1
            if self.state == PixelsState.Sleep:
                self.render_sleep()
            elif self.state == PixelsState.Disconnected:
                self.render_disconnected()
            elif self.state == PixelsState.Idle:
                self.render_idle()
            elif self.state == PixelsState.Printing:
                self.render_printing()
            elif self.state == PixelsState.Error:
                self.render_error()
            self.last_render = time.time()

    def render_sleep(self):
        pixels = [(0, 0, 0)] * self.numLEDs
        self.client.put_pixels(pixels)

    def render_idle(self):
        i = (self.frame % 510) - 255
        color = scaled(colorsys.hsv_to_rgb(190.0/255.0, max(0.1, abs(i)/255.0), 1))
        pixels = [color] * self.numLEDs
        self.client.put_pixels(pixels)

    def render_disconnected(self):
        pixels = [(255, 128, 0)] * numLEDs
        self.client.put_pixels(pixels)

    def render_error(self):
        i = self.frame % self.numLEDs
        pixels = [(128, 0, 0)] * self.numLEDs
        if i + 1 < self.numLEDs:
            pixels[i+1] = (200, 0, 0)
        pixels[i] = (255, 0, 0)
        self.client.put_pixels(pixels)

    def render_printing(self):
        i = self.frame % self.numLEDs
        pixels = [(0, 80, 0)] *self.numLEDs
        pixels[i] = (0, 255, 0)
        self.client.put_pixels(pixels)


class PixelsPlugin(octoprint.plugin.ShutdownPlugin, octoprint.plugin.StartupPlugin, octoprint.plugin.EventHandlerPlugin, octoprint.plugin.ProgressPlugin):
    def __init__(self):
        self.pixels = Animator()

    def on_shutdown(self):
        self.pixels.stop()

    def on_after_startup(self):
        self.pixels.start()
        current_state = self._printer.get_state_id()
        self.do_state(current_state)

    def do_state(self, current_state):
        if current_state == "PRINTING":
            self.pixels.set_state(PixelsState.Printing)
        elif current_state == "OPERATIONAL":
            self.pixels.set_state(PixelsState.Idle)
        elif current_state == "ERROR":
            self.pixels.set_state(PixelsState.Error)
        else:
            print "Unknown state", current_state
            self.pixels.set_state(PixelsState.Sleep)

    def on_print_progress(self, storage, path, progress):
        self._logger.info("Progress: %r", progress)

    def on_event(self, event, payload):
        self._logger.info("Event: %r -> %r", event, payload)
        if event == "PrinterStateChanged":
            self.do_state(payload['state_id'])
        if event == "ClientOpened":
            self.pixels.touch()

__plugin_name__ = "OctoPixels"
__plugin_version__ = "0.0.1"
__plugin_implementation__ = PixelsPlugin()
