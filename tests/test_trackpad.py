"""A trackpad, as a Mac has: two fingers move the board, a pinch zooms."""

from unittest.mock import patch

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref.items import BeeTextItem


WHERE = QtCore.QPointF(100, 100)


@pytest.fixture
def board(view):
    view.scene.addItem(BeeTextItem('something to look at'))
    return view


def scroll(view, pixels=(0, 0), angle=(0, 0),
           phase=Qt.ScrollPhase.ScrollUpdate,
           modifiers=Qt.KeyboardModifier.NoModifier):
    """What Qt hands over when a wheel turns or fingers are drawn."""

    event = QtGui.QWheelEvent(
        WHERE, QtCore.QPointF(view.viewport().mapToGlobal(WHERE.toPoint())),
        QtCore.QPoint(*pixels), QtCore.QPoint(*angle),
        Qt.MouseButton.NoButton, modifiers, phase, False)
    QtWidgets.QApplication.sendEvent(view.viewport(), event)
    return event


def gesture(view, kind, value):
    event = QtGui.QNativeGestureEvent(
        kind, QtGui.QPointingDevice.primaryPointingDevice(), 2,
        WHERE, WHERE,
        QtCore.QPointF(view.viewport().mapToGlobal(WHERE.toPoint())),
        value, QtCore.QPointF())
    QtWidgets.QApplication.sendEvent(view.viewport(), event)
    return event


def pinch(view, value):
    return gesture(view, Qt.NativeGestureType.ZoomNativeGesture, value)


# Two fingers drawn across it

def test_two_fingers_move_the_board_as_far_as_they_went(board):
    with patch.object(board, 'pan') as pan, \
            patch.object(board, 'smooth_zoom') as zoom:
        event = scroll(board, pixels=(30, -20), angle=(60, -40))

    pan.assert_called_once_with(QtCore.QPointF(-30, 20))
    zoom.assert_not_called()
    assert event.isAccepted()


def test_the_board_glides_on_after_the_fingers_lift(board):
    with patch.object(board, 'pan') as pan:
        scroll(board, pixels=(0, 12),
               phase=Qt.ScrollPhase.ScrollMomentum)

    pan.assert_called_once_with(QtCore.QPointF(0, -12))


def test_where_no_distance_is_given_it_goes_by_the_wheel_it_stands_for(
        board):
    with patch.object(board, 'pan') as pan:
        scroll(board, angle=(0, 120))

    pan.assert_called_once_with(QtCore.QPointF(0, -60))


def test_the_wheel_of_a_mouse_still_zooms(board):
    """Told apart by what a scroll goes through, which a wheel does
    not: nothing changes for a mouse, nor on Windows."""

    with patch.object(board, 'pan') as pan, \
            patch.object(board, 'smooth_zoom') as zoom:
        scroll(board, angle=(0, 120), phase=Qt.ScrollPhase.NoScrollPhase)

    # Wheel away to zoom in is the way round it starts out
    zoom.assert_called_once_with(-120, WHERE)
    pan.assert_not_called()


def test_with_shift_held_two_fingers_do_what_the_wheel_does(board):
    """Only the plain movement changes hands. Whatever a key was held
    for is still done."""

    with patch.object(board, 'pan') as pan:
        scroll(board, pixels=(0, 30), angle=(0, 120),
               modifiers=Qt.KeyboardModifier.ShiftModifier)

    pan.assert_called_once_with(QtCore.QPointF(0, 60))


# Two fingers pinched or spread

def test_spreading_two_fingers_makes_the_board_bigger(board):
    before = board.get_scale()
    event = pinch(board, 0.25)

    assert board.get_scale() == pytest.approx(before * 1.25)
    assert event.isAccepted()


def test_and_pinching_them_makes_it_smaller(board):
    # Seen large enough to begin with: nothing is made too small to see
    board.setTransform(QtGui.QTransform.fromScale(8, 8))
    before = board.get_scale()
    pinch(board, -0.2)

    assert board.get_scale() == pytest.approx(before * 0.8)


def test_a_pinch_zooms_about_the_point_under_the_fingers(board):
    with patch.object(board, 'zoom') as zoom:
        pinch(board, 0.1)

    zoom.assert_called_once_with(pytest.approx(100), WHERE)


def test_it_zooms_at_once_rather_than_over_the_next_frames(board):
    """The board has to stay under the fingers."""

    with patch.object(board, 'smooth_zoom') as smooth:
        pinch(board, 0.1)

    smooth.assert_not_called()
    assert board.pending_zoom == 0


def test_fingers_held_still_change_nothing(board):
    before = board.get_scale()
    pinch(board, 0.0)

    assert board.get_scale() == before


def test_any_other_gesture_is_left_alone(board):
    before = board.get_scale()
    event = gesture(board, Qt.NativeGestureType.RotateNativeGesture, 15.0)

    assert board.get_scale() == before
    assert board.pinch(event) is False
