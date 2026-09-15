# This file is part of BeeRef.
#
# BeeRef is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BeeRef is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BeeRef.  If not, see <https://www.gnu.org/licenses/>.

"""Moving around the board with a 3Dconnexion SpaceMouse.

A SpaceMouse is a cap that can be pushed, pulled and twisted in every
direction. On a flat board only three of those movements mean anything:
sliding the cap sideways or forwards and back pans, and pushing it down
or pulling it up zooms. Twisting and tilting are left alone.

It is read the way Blender reads one on Windows: as a raw HID device,
through Windows' own Raw Input. That needs no Python package and no
3Dconnexion SDK, and works whether or not their 3DxWare driver is
installed. Only RawInputReader and the functions beside it talk to
Windows. Reading a report and turning it into movement is plain Python,
so it can be tested on a machine with no SpaceMouse at all.
"""

import ctypes
from ctypes import wintypes
from functools import lru_cache
import logging
import math
import struct
import sys
import time

from PyQt6 import QtCore, QtWidgets

from beeref.config import BeeSettings


logger = logging.getLogger(__name__)


# The report numbers a SpaceMouse sends its news under
TRANSLATION_REPORT = 1
ROTATION_REPORT = 2
BUTTONS_REPORT = 3


def parse_report(data):
    """What one report from the device says.

    A dict holding any of ``translation`` (x, y, z), ``rotation`` (the
    same three, twisted) and ``buttons`` (one bit per button held), or
    an empty one for a report this does not understand.

    Axes as the device gives them: x to the right, y towards the person
    holding it, z pushed down. Older models send the pushes and the
    twists as separate reports; newer ones, the Wireless and the Compact
    among them, put all six axes in one longer report.
    """

    if not data:
        return {}
    report_id = data[0]
    if report_id == TRANSLATION_REPORT and len(data) >= 7:
        result = {'translation': struct.unpack_from('<3h', data, 1)}
        if len(data) >= 13:
            result['rotation'] = struct.unpack_from('<3h', data, 7)
        return result
    if report_id == ROTATION_REPORT and len(data) >= 7:
        return {'rotation': struct.unpack_from('<3h', data, 1)}
    if report_id == BUTTONS_REPORT and len(data) >= 2:
        return {'buttons': int.from_bytes(data[1:5], 'little')}
    return {}


class SpaceMouseNavigator(QtCore.QObject):
    """Pans and zooms the view for as long as the cap is pushed.

    The device says where the cap is, not how far it has moved, and a
    cap held still may say nothing more until it moves again. So where
    the cap was last seen is kept, and the board is moved on a timer by
    the time that has really passed.

    What the device reports is not steady, though: a cap held down reads
    a few units more or less from one report to the next, and a light
    touch comes and goes across the dead zone. Used as it arrived, that
    made the zoom stutter and jump. So the board's speed follows the cap
    rather than copying it, catching up over a fraction of a second, and
    eases into moving and out of it instead of starting and stopping
    dead.
    """

    INTERVAL = 16
    # A cap at rest still reads a little either side of nothing
    DEAD_ZONE = 12
    # About as far as a cap reads when pushed all the way
    FULL_PUSH = 350
    # Screen pixels a second, pushed all the way, at a speed of 100%
    PAN_SPEED = 1600
    # How many times closer the board comes in a second, pushed all the way
    ZOOM_PER_SECOND = 3.0
    # How long the speed takes to come most of the way to where the cap
    # is: long enough to smooth over a noisy report and an unsteady hand,
    # short enough that the board does not seem to drag behind
    FOLLOW_TIME = 0.08
    # A speed this much of a full push is taken as stopped, so easing to
    # a halt comes to an end
    STOPPED = 0.002
    # A frame that comes very late moves no further than this much time
    # would, so a stall does not throw the board across the screen
    MAX_ELAPSED = 0.1
    # How many reports go into the log, so a device that behaves oddly
    # on someone else's desk can be worked out from what it sent
    REPORTS_LOGGED = 30
    # How many ignored wheel turns go into the log; see ignore_wheel
    WHEEL_TURNS_LOGGED = 5

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        # Asked by the view before it acts on a wheel turn
        view.spacemouse = self
        self.settings = BeeSettings()
        # Where the cap is, as a share of a full push along each axis,
        # and the speed the board moves at, following it
        self.target = [0.0, 0.0, 0.0]
        self.velocity = [0.0, 0.0, 0.0]
        self.last_step = None
        self.reports_logged = 0
        self.wheel_turns_logged = 0
        self.timer = QtCore.QTimer(self)
        # To the millisecond: the coarse timer Windows gives otherwise
        # fires after 15 or 31 milliseconds by turns, and the board
        # moved unevenly with it
        self.timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
        self.timer.setInterval(self.INTERVAL)
        self.timer.timeout.connect(self.step)

    def on_report(self, data):
        if self.reports_logged < self.REPORTS_LOGGED:
            self.reports_logged += 1
            logger.info(f'SpaceMouse report: {data.hex(" ")}')
        report = parse_report(data)
        if 'buttons' in report:
            logger.debug(f'SpaceMouse buttons held: {report["buttons"]:b}')
        if 'translation' not in report:
            return
        self.target = [self.share(value) for value in report['translation']]
        if self.is_moving() and not self.timer.isActive():
            self.last_step = time.perf_counter()
            self.timer.start()

    def is_moving(self):
        """Whether the cap is pushed, or the board still easing to a stop."""

        return (any(self.target)
                or any(abs(speed) > self.STOPPED for speed in self.velocity))

    def stop(self):
        self.target = [0.0, 0.0, 0.0]
        self.velocity = [0.0, 0.0, 0.0]
        self.timer.stop()

    def step(self):
        """One frame of movement, by the clock."""

        now = time.perf_counter()
        elapsed = 0 if self.last_step is None else now - self.last_step
        elapsed = min(elapsed, self.MAX_ELAPSED)
        self.last_step = now
        if not self.view.window().isActiveWindow():
            # Blackboard is no longer the window in front, and so no
            # longer hears the device: a push remembered from before
            # must not keep the board moving
            self.stop()
            return
        self.follow(elapsed)
        if not self.is_moving():
            self.stop()
            return
        self.apply(elapsed)

    def follow(self, elapsed):
        """Bring the board's speed towards the cap, for this much time."""

        catch_up = 1 - math.exp(-elapsed / self.FOLLOW_TIME)
        for axis, target in enumerate(self.target):
            current = self.velocity[axis]
            speed = current + (target - current) * catch_up
            if not target and abs(speed) <= self.STOPPED:
                speed = 0.0
            self.velocity[axis] = speed

    def share(self, value):
        """How much of a full push this is, from -1 to 1.

        Squared past the dead zone, so a light touch moves slowly enough
        to aim with while a firm push still covers ground. Nothing at the
        edge of the dead zone, so crossing it starts nothing with a jump.
        """

        size = abs(value) - self.DEAD_ZONE
        if size <= 0:
            return 0.0
        share = min(size / (self.FULL_PUSH - self.DEAD_ZONE), 1.0)
        return math.copysign(share * share, value)

    def movement(self, elapsed):
        """The pan across, the pan down and the zoom step for this long."""

        speed = self.settings.valueOrDefault('SpaceMouse/speed') / 100
        pan_sign = (-1 if self.settings.valueOrDefault(
            'SpaceMouse/invert_pan') else 1)
        zoom_sign = (-1 if self.settings.valueOrDefault(
            'SpaceMouse/invert_zoom') else 1)
        x, y, z = self.velocity

        # The cap pushed right looks further right, and pulled towards
        # you looks further down the board, as a camera would move
        distance = self.PAN_SPEED * speed * elapsed * pan_sign

        # Pushed down brings the board closer. The view's zoom step d
        # scales it by 1 + d/1000, so the step is worked back from the
        # factor wanted for this much time.
        zoom = 0
        if z:
            factor = self.ZOOM_PER_SECOND ** (abs(z) * speed * elapsed)
            zoom = math.copysign((factor - 1) * 1000, z) * zoom_sign
        return x * distance, y * distance, zoom

    def apply(self, elapsed):
        dx, dy, zoom = self.movement(elapsed)
        if dx or dy:
            self.view.pan(QtCore.QPointF(dx, dy))
        if zoom:
            self.view.zoom(
                zoom, QtCore.QPointF(self.view.viewport().rect().center()))

    def ignore_wheel(self):
        """Note a wheel turn the view left alone while the board moved.

        3DxWare can turn a push of the cap into turns of the mouse wheel
        as well. Zooming by those notches on top of the gliding zoom
        makes it jump, so the view ignores the wheel while the SpaceMouse
        is moving the board. The first few go into the log, so a driver
        doing it can be spotted from there.
        """

        if self.wheel_turns_logged < self.WHEEL_TURNS_LOGGED:
            self.wheel_turns_logged += 1
            logger.info('Ignored a mouse wheel turn while the SpaceMouse '
                        'was moving the board')


# --- Windows ---------------------------------------------------------------

WM_INPUT = 0x00FF
RIM_TYPEHID = 2
RID_INPUT = 0x10000003
RIDI_DEVICEINFO = 0x2000000B
# What a SpaceMouse calls itself to Windows: a multi-axis controller, on
# the generic desktop page. Every 3Dconnexion model says the same.
USAGE_PAGE = 0x01
USAGE = 0x08
# The Raw Input calls return this, as an unsigned int, when they fail
UINT_ERROR = 0xFFFFFFFF


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [('usUsagePage', wintypes.USHORT),
                ('usUsage', wintypes.USHORT),
                ('dwFlags', wintypes.DWORD),
                ('hwndTarget', wintypes.HWND)]


class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [('hDevice', wintypes.HANDLE),
                ('dwType', wintypes.DWORD)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [('dwType', wintypes.DWORD),
                ('dwSize', wintypes.DWORD),
                ('hDevice', wintypes.HANDLE),
                ('wParam', wintypes.WPARAM)]


class RAWHID(ctypes.Structure):
    """The start of a HID input; its reports follow straight after."""

    _fields_ = [('dwSizeHid', wintypes.DWORD),
                ('dwCount', wintypes.DWORD)]


class RID_DEVICE_INFO_HID(ctypes.Structure):
    _fields_ = [('dwVendorId', wintypes.DWORD),
                ('dwProductId', wintypes.DWORD),
                ('dwVersionNumber', wintypes.DWORD),
                ('usUsagePage', wintypes.USHORT),
                ('usUsage', wintypes.USHORT)]


class RID_DEVICE_INFO_UNION(ctypes.Union):
    # The keyboard's variant is the largest, and so sets the size
    _fields_ = [('hid', RID_DEVICE_INFO_HID),
                ('keyboard', wintypes.DWORD * 6)]


class RID_DEVICE_INFO(ctypes.Structure):
    _anonymous_ = ('info',)
    _fields_ = [('cbSize', wintypes.DWORD),
                ('dwType', wintypes.DWORD),
                ('info', RID_DEVICE_INFO_UNION)]


@lru_cache(maxsize=None)
def user32():
    """Windows' user32, with the Raw Input calls typed for 64 bits."""

    api = ctypes.WinDLL('user32', use_last_error=True)
    api.RegisterRawInputDevices.argtypes = [
        ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT]
    api.RegisterRawInputDevices.restype = wintypes.BOOL
    api.GetRawInputDeviceList.argtypes = [
        ctypes.POINTER(RAWINPUTDEVICELIST),
        ctypes.POINTER(wintypes.UINT), wintypes.UINT]
    api.GetRawInputDeviceList.restype = wintypes.UINT
    api.GetRawInputDeviceInfoW.argtypes = [
        wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p,
        ctypes.POINTER(wintypes.UINT)]
    api.GetRawInputDeviceInfoW.restype = wintypes.UINT
    api.GetRawInputData.argtypes = [
        wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p,
        ctypes.POINTER(wintypes.UINT), wintypes.UINT]
    api.GetRawInputData.restype = wintypes.UINT
    return api


def multi_axis_devices():
    """The (vendor, product) of every SpaceMouse plugged in."""

    api = user32()
    count = wintypes.UINT(0)
    entry_size = ctypes.sizeof(RAWINPUTDEVICELIST)
    if api.GetRawInputDeviceList(
            None, ctypes.byref(count), entry_size) == UINT_ERROR:
        return []
    entries = (RAWINPUTDEVICELIST * count.value)()
    got = api.GetRawInputDeviceList(entries, ctypes.byref(count), entry_size)
    if got == UINT_ERROR:
        return []

    found = []
    for entry in entries[:got]:
        if entry.dwType != RIM_TYPEHID:
            continue
        info = RID_DEVICE_INFO()
        info.cbSize = ctypes.sizeof(RID_DEVICE_INFO)
        size = wintypes.UINT(info.cbSize)
        if api.GetRawInputDeviceInfoW(
                entry.hDevice, RIDI_DEVICEINFO,
                ctypes.byref(info), ctypes.byref(size)) == UINT_ERROR:
            continue
        if (info.hid.usUsagePage, info.hid.usUsage) == (USAGE_PAGE, USAGE):
            found.append((info.hid.dwVendorId, info.hid.dwProductId))
    return found


class RawInputReader(QtCore.QAbstractNativeEventFilter):
    """Passes on what the SpaceMouse sends Windows to the navigator."""

    def __init__(self, navigator):
        super().__init__()
        self.navigator = navigator

    def register(self, hwnd):
        """Ask Windows to send the device's input to this window.

        Only while Blackboard is the window in front: a push meant for
        another program leaves the board where it is.
        """

        device = RAWINPUTDEVICE(USAGE_PAGE, USAGE, 0, hwnd)
        return bool(user32().RegisterRawInputDevices(
            ctypes.byref(device), 1, ctypes.sizeof(device)))

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) != b'windows_generic_MSG':
            return False, 0
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_INPUT:
            for report in self.read_reports(msg.lParam):
                self.navigator.on_report(report)
        # Never kept back: Windows expects to tidy up the input itself
        return False, 0

    def read_reports(self, handle):
        """The reports carried by one WM_INPUT message."""

        api = user32()
        header_size = ctypes.sizeof(RAWINPUTHEADER)
        size = wintypes.UINT(0)
        if api.GetRawInputData(handle, RID_INPUT, None,
                               ctypes.byref(size), header_size) != 0:
            return []
        buffer = ctypes.create_string_buffer(size.value)
        if api.GetRawInputData(handle, RID_INPUT, buffer,
                               ctypes.byref(size), header_size) != size.value:
            return []
        header = RAWINPUTHEADER.from_buffer(buffer)
        if header.dwType != RIM_TYPEHID:
            return []
        hid = RAWHID.from_buffer(buffer, header_size)
        start = header_size + ctypes.sizeof(RAWHID)
        length = hid.dwSizeHid
        raw = buffer.raw
        return [raw[start + i * length:start + (i + 1) * length]
                for i in range(hid.dwCount)]


def start(window):
    """Listen for a SpaceMouse on the main window, if one is plugged in.

    Returns the reader, which has to be held on to for as long as it is
    wanted, or None when there is nothing to listen to: not Windows, or
    no device found. Looked for once, at start, so a SpaceMouse plugged
    in later is found the next time Blackboard opens.
    """

    if sys.platform != 'win32':
        return None
    try:
        devices = multi_axis_devices()
    except OSError:
        logger.exception('Could not look for a SpaceMouse')
        return None
    if not devices:
        logger.debug('No SpaceMouse plugged in')
        return None

    names = ', '.join(f'{vendor:04x}:{product:04x}'
                      for vendor, product in devices)
    logger.info(f'SpaceMouse found ({names})')
    reader = RawInputReader(SpaceMouseNavigator(window.view))
    if not reader.register(int(window.winId())):
        logger.warning('Could not listen to the SpaceMouse: '
                       f'Windows error {ctypes.get_last_error()}')
        return None
    QtWidgets.QApplication.instance().installNativeEventFilter(reader)
    return reader
