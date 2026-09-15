import ctypes
from ctypes import wintypes
import struct
import sys
import time
from unittest.mock import MagicMock, patch

import pytest
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt

from beeref import spacemouse
from beeref.spacemouse import SpaceMouseNavigator, parse_report


windows_only = pytest.mark.skipif(
    sys.platform != 'win32', reason='Raw Input is only on Windows')

# One frame of the navigator's timer, in seconds
FRAME = SpaceMouseNavigator.INTERVAL / 1000


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


def held(nav, **axes):
    """The cap pushed, and held long enough for the board to catch up."""

    nav.on_report(pushes(**axes))
    nav.follow(10)


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
    held(nav, x=300)
    with patch.object(view, 'pan') as pan:
        nav.apply(0.1)
    delta = pan.call_args[0][0]
    assert delta.x() > 0
    assert delta.y() == 0


def test_pulling_the_cap_towards_you_pans_down(view, nav):
    held(nav, y=300)
    with patch.object(view, 'pan') as pan:
        nav.apply(0.1)
    assert pan.call_args[0][0].y() > 0


def test_pushing_down_zooms_in_and_pulling_up_zooms_out(view, nav):
    with patch.object(view, 'zoom') as zoom:
        held(nav, z=300)
        nav.apply(0.1)
        assert zoom.call_args[0][0] > 0
        held(nav, z=-300)
        nav.apply(0.1)
        assert zoom.call_args[0][0] < 0


def test_the_zoom_goes_towards_the_middle_of_the_view(view, nav):
    held(nav, z=300)
    with patch.object(view, 'zoom') as zoom:
        nav.apply(0.1)
    anchor = zoom.call_args[0][1]
    centre = view.viewport().rect().center()
    assert (anchor.x(), anchor.y()) == (centre.x(), centre.y())


def test_a_cap_at_rest_moves_nothing(view, nav):
    """A cap let go still reads a little either side of nothing."""

    held(nav, x=5, y=-8, z=3)
    assert nav.is_moving() is False
    assert nav.timer.isActive() is False
    with patch.object(view, 'pan') as pan, patch.object(view, 'zoom') as zoom:
        nav.apply(0.1)
    pan.assert_not_called()
    zoom.assert_not_called()


def test_twisting_the_cap_moves_nothing(view, nav):
    nav.on_report(bytes([2]) + struct.pack('<3h', 300, 300, 300))
    nav.follow(10)
    with patch.object(view, 'pan') as pan, patch.object(view, 'zoom') as zoom:
        nav.apply(0.1)
    pan.assert_not_called()
    zoom.assert_not_called()


def test_holding_the_cap_still_keeps_the_board_moving(view, nav):
    """The device may say nothing more while the cap is held still."""

    held(nav, x=200)
    with patch.object(view, 'pan') as pan:
        nav.apply(0.05)
        nav.apply(0.05)
    assert pan.call_count == 2


def test_further_pushed_goes_faster(view, nav):
    with patch.object(view, 'pan') as pan:
        held(nav, x=100)
        nav.apply(0.1)
        light = pan.call_args[0][0].x()
        held(nav, x=300)
        nav.apply(0.1)
        firm = pan.call_args[0][0].x()
    assert firm > light > 0


# --- Smoothly ---------------------------------------------------------------

def test_the_board_eases_into_moving_rather_than_jumping(nav):
    nav.on_report(pushes(x=300))
    target = nav.target[0]

    speeds = []
    for _ in range(5):
        nav.follow(FRAME)
        speeds.append(nav.velocity[0])
    assert 0 < speeds[0] < target / 2
    assert speeds == sorted(speeds)
    assert speeds[-1] < target


def test_letting_go_eases_to_a_stop_and_then_stops(view, nav):
    held(nav, x=300)
    nav.on_report(pushes())

    # Still gliding, slower each frame, rather than stopped dead
    nav.last_step = time.perf_counter() - FRAME
    with in_front(view), patch.object(view, 'pan') as pan:
        nav.step()
    assert pan.called
    assert 0 < nav.velocity[0] < nav.share(300)
    assert nav.timer.isActive() is True

    nav.follow(10)
    with in_front(view), patch.object(view, 'pan') as pan:
        nav.step()
    pan.assert_not_called()
    assert nav.timer.isActive() is False


def test_a_trembling_cap_zooms_smoothly(nav):
    """A cap held down reads a little more or less from one report to
    the next. Used as it came, the zoom sped up and slowed down by
    nearly double from one frame to the next."""

    assert nav.share(300) / nav.share(220) > 1.5
    speeds = []
    for reading in [300, 220] * 40:
        nav.on_report(pushes(z=reading))
        nav.follow(FRAME)
        speeds.append(nav.velocity[2])
    settled = speeds[-20:]
    assert max(settled) / min(settled) < 1.15


def test_crossing_the_dead_zone_starts_nothing_with_a_jump(nav):
    """A light touch comes and goes across it."""

    assert nav.share(nav.DEAD_ZONE + 1) == pytest.approx(0, abs=1e-4)


def test_the_timer_keeps_to_the_millisecond(nav):
    """Windows' coarse timer fires after 15 or 31 ms by turns."""

    assert nav.timer.timerType() == Qt.TimerType.PreciseTimer


def test_the_board_stops_when_blackboard_is_not_in_front(view, nav):
    """Windows only sends the input to the window in front, so a push
    remembered from before must not carry the board on."""

    held(nav, x=300)
    with in_front(view, False), patch.object(view, 'pan') as pan:
        nav.step()
    pan.assert_not_called()
    assert nav.timer.isActive() is False
    assert nav.is_moving() is False


def test_a_late_frame_moves_no_further_than_a_short_one(view, nav):
    held(nav, x=300)
    nav.last_step = time.perf_counter() - 5
    with in_front(view), patch.object(view, 'pan') as pan:
        nav.step()
    late = pan.call_args[0][0].x()
    with patch.object(view, 'pan') as pan:
        nav.apply(nav.MAX_ELAPSED)
    assert late == pytest.approx(pan.call_args[0][0].x())


# --- The mouse wheel alongside it -------------------------------------------

def wheel_turn(view):
    event = MagicMock()
    event.angleDelta.return_value = QtCore.QPointF(0.0, 40.0)
    event.position.return_value = QtCore.QPointF(10.0, 20.0)
    event.modifiers.return_value = Qt.KeyboardModifier.NoModifier
    view.wheelEvent(event)
    return event


def test_the_wheel_is_left_alone_while_the_spacemouse_moves_the_board(
        view, nav):
    """3DxWare can turn a push of the cap into wheel turns as well, and
    zooming by those notches on top of the glide made it jump."""

    held(nav, z=300)
    with patch.object(view, 'smooth_zoom') as zoomed:
        event = wheel_turn(view)
    zoomed.assert_not_called()
    event.accept.assert_called_once_with()


def test_the_wheel_works_again_once_the_board_has_stopped(view, nav):
    held(nav, z=300)
    held(nav)
    with patch.object(view, 'smooth_zoom') as zoomed:
        wheel_turn(view)
    zoomed.assert_called_once()


def test_the_wheel_works_with_no_spacemouse_at_all(view):
    with patch.object(view, 'smooth_zoom') as zoomed:
        wheel_turn(view)
    zoomed.assert_called_once()


# --- Settings ---------------------------------------------------------------

def test_the_settings_turn_pan_and_zoom_round(view, nav, settings):
    settings.setValue('SpaceMouse/invert_pan', True)
    settings.setValue('SpaceMouse/invert_zoom', True)
    held(nav, x=300, z=300)
    with patch.object(view, 'pan') as pan, patch.object(view, 'zoom') as zoom:
        nav.apply(0.1)
    assert pan.call_args[0][0].x() < 0
    assert zoom.call_args[0][0] < 0


def test_the_speed_setting_scales_the_panning(view, nav, settings):
    held(nav, x=300)
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


def tab_names(dialog):
    tabs = dialog.findChild(QtWidgets.QTabWidget)
    return [tabs.tabText(i) for i in range(tabs.count())]


def test_its_settings_are_with_keyboard_and_mouse_not_the_general_ones(
        view):
    """A SpaceMouse is a way of moving round the board, like the wheel."""

    from beeref.widgets.controls import ControlsDialog
    from beeref.widgets.settings import SettingsDialog
    controls = ControlsDialog(view)
    general = SettingsDialog(view)
    try:
        assert '&SpaceMouse' in tab_names(controls)
        assert '&SpaceMouse' not in tab_names(general)
    finally:
        controls.close()
        general.close()


def test_keyboard_and_mouse_restore_defaults_puts_it_back(view, settings):
    from beeref.widgets.controls import ControlsDialog
    from beeref.widgets.controls.spacemouse import SpaceMouseSpeedWidget
    settings.setValue('SpaceMouse/speed', 250)
    settings.setValue('SpaceMouse/invert_pan', True)
    dialog = ControlsDialog(view)
    assert dialog.findChild(SpaceMouseSpeedWidget).input.value() == 250

    with patch('PyQt6.QtWidgets.QMessageBox.question',
               return_value=QtWidgets.QMessageBox.StandardButton.Yes), \
            patch('PyQt6.QtGui.QAction.setShortcuts'):
        dialog.on_restore_defaults()
    assert settings.valueOrDefault('SpaceMouse/speed') == 100
    assert settings.valueOrDefault('SpaceMouse/invert_pan') is False
    # And the tab shows it, not what it said before
    assert dialog.findChild(SpaceMouseSpeedWidget).input.value() == 100
    dialog.close()


def test_the_general_restore_defaults_leaves_it_alone(settings):
    settings.setValue('SpaceMouse/speed', 250)
    settings.setValue('Items/arrange_gap', 40)
    settings.restore_defaults()
    assert settings.valueOrDefault('SpaceMouse/speed') == 250
    assert settings.valueOrDefault('Items/arrange_gap') == 0


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
