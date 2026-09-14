import ctypes
from ctypes import wintypes
import struct
import sys
import time
from unittest.mock import patch

import pytest
from PyQt6 import QtWidgets

from beeref import spacemouse
from beeref.spacemouse import SpaceMouseNavigator, parse_report


windows_only = pytest.mark.skipif(
    sys.platform != 'win32', reason='Raw Input is only on Windows')


def pushes(x=0, y=0, z=0):
    """A report of the cap pushed this far along each axis."""

    return (bytes([spacemouse.TRANSLATION_REPORT])
            + struct.pack('<3h', x, y, z))


@pytest.fixture
def nav(view):
    navigator = SpaceMouseNavigator(view)
    yield navigator
    navigator.timer.stop()


def in_front(view, value=True):
    """Blackboard as the window in front, or not."""

    return patch.object(type(view.window()), 'isActiveWindow',
                        return_value=value)


# --- Reading what the device sends -----------------------------------------

def test_a_push_report_gives_the_three_pushes():
    assert parse_report(pushes(120, -45, 300)) == {
        'translation': (120, -45, 300)}


def test_a_longer_report_carries_the_twists_too():
    """The Wireless and the Compact send all six axes at once."""

    data = bytes([1]) + struct.pack('<6h', 10, 20, 30, -1, -2, -3)
    assert parse_report(data) == {
        'translation': (10, 20, 30), 'rotation': (-1, -2, -3)}


def test_a_twist_report_on_its_own():
    data = bytes([2]) + struct.pack('<3h', 5, 6, 7)
    assert parse_report(data) == {'rotation': (5, 6, 7)}


def test_a_button_report_says_which_are_held():
    assert parse_report(bytes([3, 0b10, 0, 0, 0])) == {'buttons': 2}


@pytest.mark.parametrize(
    'data', [b'', bytes([1, 0, 0]), bytes([9]) + bytes(6)])
def test_a_report_not_understood_says_nothing(data):
    assert parse_report(data) == {}


# --- Moving the board -------------------------------------------------------

def test_sliding_the_cap_right_pans_right(view, nav):
    nav.on_report(pushes(x=300))
    with patch.object(view, 'pan') as pan:
        nav.apply(0.1)
    delta = pan.call_args[0][0]
    assert delta.x() > 0
    assert delta.y() == 0


def test_pulling_the_cap_towards_you_pans_down(view, nav):
    nav.on_report(pushes(y=300))
    with patch.object(view, 'pan') as pan:
        nav.apply(0.1)
    assert pan.call_args[0][0].y() > 0


def test_pushing_down_zooms_in_and_pulling_up_zooms_out(view, nav):
    with patch.object(view, 'zoom') as zoom:
        nav.on_report(pushes(z=300))
        nav.apply(0.1)
        assert zoom.call_args[0][0] > 0
        nav.on_report(pushes(z=-300))
        nav.apply(0.1)
        assert zoom.call_args[0][0] < 0


def test_the_zoom_goes_towards_the_middle_of_the_view(view, nav):
    nav.on_report(pushes(z=300))
    with patch.object(view, 'zoom') as zoom:
        nav.apply(0.1)
    anchor = zoom.call_args[0][1]
    centre = view.viewport().rect().center()
    assert (anchor.x(), anchor.y()) == (centre.x(), centre.y())


def test_a_cap_at_rest_moves_nothing(view, nav):
    """A cap let go still reads a little either side of nothing."""

    nav.on_report(pushes(5, -8, 3))
    assert nav.timer.isActive() is False
    with patch.object(view, 'pan') as pan, patch.object(view, 'zoom') as zoom:
        nav.apply(0.1)
    pan.assert_not_called()
    zoom.assert_not_called()


def test_twisting_the_cap_moves_nothing(view, nav):
    nav.on_report(bytes([2]) + struct.pack('<3h', 300, 300, 300))
    with patch.object(view, 'pan') as pan, patch.object(view, 'zoom') as zoom:
        nav.apply(0.1)
    pan.assert_not_called()
    zoom.assert_not_called()


def test_a_push_sets_the_board_moving_and_letting_go_stops_it(view, nav):
    nav.on_report(pushes(x=200))
    assert nav.timer.isActive() is True

    nav.on_report(pushes())
    with in_front(view), patch.object(view, 'pan') as pan:
        nav.step()
    pan.assert_not_called()
    assert nav.timer.isActive() is False


def test_holding_the_cap_still_keeps_the_board_moving(view, nav):
    """The device may say nothing more while the cap is held still."""

    nav.on_report(pushes(x=200))
    with patch.object(view, 'pan') as pan:
        nav.apply(0.05)
        nav.apply(0.05)
    assert pan.call_count == 2


def test_further_pushed_goes_faster(view, nav):
    with patch.object(view, 'pan') as pan:
        nav.on_report(pushes(x=100))
        nav.apply(0.1)
        light = pan.call_args[0][0].x()
        nav.on_report(pushes(x=300))
        nav.apply(0.1)
        firm = pan.call_args[0][0].x()
    assert firm > light > 0


def test_the_board_stops_when_blackboard_is_not_in_front(view, nav):
    """Windows only sends the input to the window in front, so a push
    remembered from before must not carry the board on."""

    nav.on_report(pushes(x=300))
    with in_front(view, False), patch.object(view, 'pan') as pan:
        nav.step()
    pan.assert_not_called()
    assert nav.timer.isActive() is False
    assert nav.is_pushed() is False


def test_a_late_frame_moves_no_further_than_a_short_one(view, nav):
    nav.on_report(pushes(x=300))
    nav.last_step = time.perf_counter() - 5
    with in_front(view), patch.object(view, 'pan') as pan:
        nav.step()
    late = pan.call_args[0][0].x()
    with patch.object(view, 'pan') as pan:
        nav.apply(nav.MAX_ELAPSED)
    assert late == pytest.approx(pan.call_args[0][0].x())


# --- Settings ---------------------------------------------------------------

def test_the_settings_turn_pan_and_zoom_round(view, nav, settings):
    settings.setValue('SpaceMouse/invert_pan', True)
    settings.setValue('SpaceMouse/invert_zoom', True)
    nav.on_report(pushes(x=300, z=300))
    with patch.object(view, 'pan') as pan, patch.object(view, 'zoom') as zoom:
        nav.apply(0.1)
    assert pan.call_args[0][0].x() < 0
    assert zoom.call_args[0][0] < 0


def test_the_speed_setting_scales_the_panning(view, nav, settings):
    nav.on_report(pushes(x=300))
    with patch.object(view, 'pan') as pan:
        nav.apply(0.1)
        normal = pan.call_args[0][0].x()
        settings.setValue('SpaceMouse/speed', 200)
        nav.apply(0.1)
        double = pan.call_args[0][0].x()
    assert double == pytest.approx(normal * 2)


def test_a_switch_read_back_from_the_file_is_what_was_chosen(settings):
    """An .ini file keeps true and false as words, and bool('false') is
    True: switched off, it would have come back on at the next start."""

    settings.setValue('SpaceMouse/invert_pan', 'false')
    assert settings.valueOrDefault('SpaceMouse/invert_pan') is False
    settings.setValue('SpaceMouse/invert_pan', 'true')
    assert settings.valueOrDefault('SpaceMouse/invert_pan') is True


def test_the_settings_have_a_spacemouse_tab(view):
    from beeref.widgets.settings import SettingsDialog
    dialog = SettingsDialog(view)
    tabs = dialog.findChild(QtWidgets.QTabWidget)
    names = [tabs.tabText(i) for i in range(tabs.count())]
    dialog.close()
    assert '&SpaceMouse' in names


# --- Windows ----------------------------------------------------------------

def message(kind):
    msg = wintypes.MSG()
    msg.message = kind
    return msg


def test_other_messages_pass_straight_through(nav):
    reader = spacemouse.RawInputReader(nav)
    mouse_moved = message(0x0200)
    with patch.object(reader, 'read_reports') as read:
        result = reader.nativeEventFilter(
            b'windows_generic_MSG', ctypes.addressof(mouse_moved))
    read.assert_not_called()
    assert result == (False, 0)


def test_the_devices_input_reaches_the_navigator(nav):
    reader = spacemouse.RawInputReader(nav)
    arrived = message(spacemouse.WM_INPUT)
    data = pushes(x=200)
    with patch.object(reader, 'read_reports', return_value=[data]), \
            patch.object(nav, 'on_report') as on_report:
        result = reader.nativeEventFilter(
            b'windows_generic_MSG', ctypes.addressof(arrived))
    on_report.assert_called_once_with(data)
    # Never kept back: Windows tidies the input up itself
    assert result == (False, 0)


@windows_only
def test_the_windows_structures_are_the_size_windows_expects():
    pointer = ctypes.sizeof(ctypes.c_void_p)
    assert ctypes.sizeof(spacemouse.RAWINPUTDEVICE) == 8 + pointer
    assert ctypes.sizeof(spacemouse.RAWINPUTHEADER) == 8 + 2 * pointer
    assert ctypes.sizeof(spacemouse.RAWINPUTDEVICELIST) == 2 * pointer
    assert ctypes.sizeof(spacemouse.RID_DEVICE_INFO) == 32


@windows_only
def test_looking_for_a_spacemouse_works_on_this_computer():
    assert isinstance(spacemouse.multi_axis_devices(), list)


@windows_only
def test_windows_accepts_the_request_for_the_devices_input(
        main_window, nav):
    reader = spacemouse.RawInputReader(nav)
    assert reader.register(int(main_window.winId())) is True


@windows_only
def test_nothing_listens_without_a_spacemouse(main_window):
    with patch.object(spacemouse, 'multi_axis_devices', return_value=[]), \
            patch('PyQt6.QtWidgets.QApplication.installNativeEventFilter') \
            as install:
        assert spacemouse.start(main_window) is None
    install.assert_not_called()


@windows_only
def test_a_spacemouse_found_is_listened_to(main_window):
    with patch.object(spacemouse, 'multi_axis_devices',
                      return_value=[(0x256F, 0xC635)]), \
            patch.object(spacemouse.RawInputReader, 'register',
                         return_value=True), \
            patch('PyQt6.QtWidgets.QApplication.installNativeEventFilter') \
            as install:
        reader = spacemouse.start(main_window)
    assert reader is not None
    install.assert_called_once_with(reader)
    assert reader.navigator.view is main_window.view
    reader.navigator.timer.stop()


def test_there_is_no_spacemouse_off_windows(main_window):
    with patch.object(spacemouse.sys, 'platform', 'linux'):
        assert spacemouse.start(main_window) is None
