"""With snapping to the grid on, what is moved or sized lands on it."""

import pytest
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref.actions.actions import actions
from beeref.items import BeePixmapItem, BeeTextItem
from . import test_snap_to_items
from .test_snap_to_items import NONE, SHIFT, drag, move


# The window on screen, as the tests of snapping to other things have it
board = test_snap_to_items.board


def picture(view, x, y, width=200, height=150):
    img = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(90, 90, 120))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def at_size(view):
    view.setTransform(QtGui.QTransform())
    view.centerOn(QtCore.QPointF(450, 300))


def snapping(view, on=True):
    if view.snap_to_grid != on:
        actions['snap_to_grid'].qaction.trigger()
    assert view.snap_to_grid is on


def is_on_grid(value, step):
    return abs(value / step - round(value / step)) < 1e-6


def test_the_switch_is_a_menu_entry_and_a_button(board):
    button = board.draw_toolbar.snap
    assert board.snap_to_grid is False
    assert button.isChecked() is False

    button.click()
    assert board.snap_to_grid is True
    assert actions['snap_to_grid'].qaction.isChecked() is True

    actions['snap_to_grid'].qaction.trigger()
    assert board.snap_to_grid is False
    assert button.isChecked() is False


def test_off_there_is_no_step(board):
    assert board.grid_snap_step() is None


def test_the_step_follows_the_zoom(board):
    snapping(board)
    at_size(board)
    near = board.grid_snap_step()
    board.setTransform(QtGui.QTransform.fromScale(0.1, 0.1))
    far = board.grid_snap_step()
    board.setTransform(QtGui.QTransform.fromScale(8, 8))
    close = board.grid_snap_step()

    assert close < near < far
    # Always what the grid shows: between half and all of its spacing
    # on the screen
    for scale, step in ((1, near), (0.1, far), (8, close)):
        assert 25 <= step * scale <= 250


def test_moved_it_lands_on_the_grid(board):
    snapping(board)
    item = picture(board, 0, 0)
    at_size(board)
    step = board.grid_snap_step()

    drag(board, item, (73, 141), modifiers=NONE)

    corner = board.scene.snap_rect(item).topLeft()
    assert is_on_grid(corner.x(), step)
    assert is_on_grid(corner.y(), step)
    assert corner == QtCore.QPointF(step, step)


def test_off_it_goes_where_the_mouse_takes_it(board):
    item = picture(board, 0, 0)
    at_size(board)

    drag(board, item, (73, 41), modifiers=NONE)

    assert item.pos().x() == pytest.approx(73, abs=1)
    assert item.pos().y() == pytest.approx(41, abs=1)


def test_with_shift_something_near_wins_over_the_grid(board):
    snapping(board)
    still = picture(board, 0, 0)
    moving = picture(board, 330, 40)
    at_size(board)

    # Its left side to within six pixels of the other's right side,
    # which is not on a grid line
    still.setPos(13, 0)
    drag(board, moving, (-111, 0), modifiers=SHIFT)

    assert board.scene.snap_rect(moving).left() == pytest.approx(
        board.scene.snap_rect(still).right())


def test_undone_a_move_onto_the_grid_goes_back(board):
    snapping(board)
    item = picture(board, 7, 9)
    at_size(board)

    drag(board, item, (73, 141), modifiers=NONE)
    board.undo_stack.undo()

    assert item.pos().x() == pytest.approx(7)
    assert item.pos().y() == pytest.approx(9)


def press_and_drag(view, start, end):
    viewport = view.viewport()
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, NONE, start)
    for step in range(1, 9):
        move(view, start + (end - start) * step / 8,
             Qt.MouseButton.LeftButton, NONE)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, NONE, end)


def test_a_side_dragged_lands_on_the_grid(board):
    snapping(board)
    note = BeeTextItem('Some words that make a note of a fair width')
    board.scene.addItem(note)
    note.setPos(0, 0)
    at_size(board)
    board.scene.clearSelection()
    note.setSelected(True)
    step = board.grid_snap_step()
    rect = note.sceneBoundingRect()
    note_rect = note.mapToScene(note.bounding_rect_unselected()).boundingRect()
    side = board.mapFromScene(QtCore.QPointF(note_rect.right() - 1,
                                             note_rect.center().y()))

    press_and_drag(board, side, side + QtCore.QPoint(61, 0))

    right = note.mapToScene(note.bounding_rect_unselected()).boundingRect(
        ).right()
    assert right != pytest.approx(rect.right())
    assert is_on_grid(right, step)


def test_a_corner_dragged_lands_on_a_grid_line(board):
    snapping(board)
    item = picture(board, 0, 0)
    at_size(board)
    board.scene.clearSelection()
    item.setSelected(True)
    step = board.grid_snap_step()
    corner = board.mapFromScene(QtCore.QPointF(199, 149))

    press_and_drag(board, corner, corner + QtCore.QPoint(70, 52))

    rect = item.sceneBoundingRect()
    bounds = item.mapToScene(item.bounding_rect_unselected()).boundingRect()
    assert bounds.topLeft() == QtCore.QPointF(0, 0)
    assert is_on_grid(bounds.right(), step) or is_on_grid(
        bounds.bottom(), step)
    assert rect.width() > 200
    # Undone, it is the size it was
    board.undo_stack.undo()
    assert item.scale() == pytest.approx(1)


def test_a_pinned_note_is_never_put_on_the_grid(board):
    snapping(board)
    note = BeeTextItem('pinned')
    board.scene.addItem(note)
    board.scene.clearSelection()
    note.setSelected(True)
    board.on_action_pin_note()

    assert note.grid_step() is None
