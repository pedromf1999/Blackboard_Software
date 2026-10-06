"""Dragged with Shift held, things snap against each other."""

import pytest
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref import commands
from beeref.items import BeeGroupItem, BeePixmapItem, BeeTextItem


SHIFT = Qt.KeyboardModifier.ShiftModifier
NONE = Qt.KeyboardModifier.NoModifier


@pytest.fixture
def board(main_window, view, qtbot):
    main_window.resize(1000, 700)
    main_window.show()
    qtbot.waitExposed(main_window)
    view.shortcuts_hint.hide()
    return view


def picture(view, x, y, width=200, height=150):
    img = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(90, 90, 120))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def at_size(view):
    """The board seen at its own size, from its top left corner."""

    view.setTransform(QtGui.QTransform())
    view.centerOn(QtCore.QPointF(450, 300))


def move(view, point, buttons, modifiers):
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove, QtCore.QPointF(point),
        QtCore.QPointF(view.viewport().mapToGlobal(point)),
        Qt.MouseButton.NoButton, buttons, modifiers)
    QtGui.QGuiApplication.sendEvent(view.viewport(), event)


def drag(view, item, by, modifiers=SHIFT, release=True):
    """Drag an item by its middle, this far on the screen."""

    start = view.mapFromScene(item.sceneBoundingRect().center())
    end = start + QtCore.QPoint(*by)
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton, NONE, start)
    for step in range(1, 9):
        move(view, start + (end - start) * step / 8,
             Qt.MouseButton.LeftButton, modifiers)
    if release:
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton,
                           modifiers, end)


def edges(view, item):
    return view.scene.snap_rect(item)


def test_close_enough_it_comes_up_against_the_other(board):
    still = picture(board, 0, 0)
    moving = picture(board, 300, 40)
    at_size(board)

    # Its left side to within six pixels of the other's right side
    drag(board, moving, (-94, 0))

    assert edges(board, moving).left() == pytest.approx(
        edges(board, still).right())


def test_without_shift_it_goes_where_the_mouse_takes_it(board):
    still = picture(board, 0, 0)
    moving = picture(board, 300, 40)
    at_size(board)

    drag(board, moving, (-94, 0), modifiers=NONE)

    assert edges(board, moving).left() == pytest.approx(206, abs=1)
    assert edges(board, moving).left() != pytest.approx(
        edges(board, still).right())


def test_too_far_away_it_is_left_alone(board):
    picture(board, 0, 0)
    moving = picture(board, 300, 40)
    at_size(board)

    drag(board, moving, (-60, 0))

    assert edges(board, moving).left() == pytest.approx(240, abs=1)


def test_side_by_side_their_tops_line_up(board):
    still = picture(board, 0, 0)
    moving = picture(board, 300, 40)
    at_size(board)

    drag(board, moving, (-96, -36))

    assert edges(board, moving).left() == pytest.approx(
        edges(board, still).right())
    assert edges(board, moving).top() == pytest.approx(
        edges(board, still).top())


def test_one_under_another_their_sides_line_up(board):
    still = picture(board, 0, 0)
    moving = picture(board, 6, 300)
    at_size(board)

    drag(board, moving, (0, -146))

    assert edges(board, moving).top() == pytest.approx(
        edges(board, still).bottom())
    assert edges(board, moving).left() == pytest.approx(
        edges(board, still).left())


def test_a_caption_counts_as_part_of_the_picture(board):
    still = picture(board, 0, 0)
    still.caption = 'Joint detail'
    moving = picture(board, 0, 400)
    at_size(board)
    bottom = edges(board, still).bottom()
    assert bottom > still.sceneBoundingRect().top() + 150

    gap = edges(board, moving).top() - bottom
    drag(board, moving, (0, -round(gap) + 5))

    assert edges(board, moving).top() == pytest.approx(bottom)


def test_notes_and_groups_snap_too(board):
    note = BeeTextItem('a note')
    note.title = 'Title'
    board.scene.addItem(note)
    note.setPos(0, 0)
    first = picture(board, 400, 0)
    second = picture(board, 650, 0)
    group = BeeGroupItem()
    commands.GroupItems(board.scene, [first, second], group).redo()
    board.scene.clearSelection()
    at_size(board)

    gap = edges(board, group).left() - edges(board, note).right()
    drag(board, note, (round(gap) - 4, 0))

    assert edges(board, note).right() == pytest.approx(
        edges(board, group).left())


def test_lines_show_what_it_snapped_to_while_it_is_dragged(board):
    picture(board, 0, 0)
    moving = picture(board, 300, 40)
    at_size(board)

    drag(board, moving, (-94, 0), release=False)
    assert board.scene.snap_guides

    QTest.mouseRelease(board.viewport(), Qt.MouseButton.LeftButton, SHIFT,
                       board.mapFromScene(moving.sceneBoundingRect().center()))
    assert board.scene.snap_guides == []


def test_undone_it_goes_back_exactly_where_it_was(board):
    picture(board, 0, 0)
    moving = picture(board, 300, 40)
    at_size(board)
    before = moving.pos()

    drag(board, moving, (-94, 0))
    assert moving.pos() != before
    board.undo_stack.undo()

    assert moving.pos().x() == pytest.approx(before.x())
    assert moving.pos().y() == pytest.approx(before.y())
    board.undo_stack.redo()
    assert edges(board, moving).left() == pytest.approx(200)


def test_the_reach_is_on_the_screen_whatever_the_zoom(board):
    still = picture(board, 0, 0)
    moving = picture(board, 300, 40)
    board.setTransform(QtGui.QTransform.fromScale(0.5, 0.5))
    board.centerOn(QtCore.QPointF(300, 100))

    # 100 units away is 50 pixels: dragged 46 pixels, 4 are left
    drag(board, moving, (-46, 0))

    assert edges(board, moving).left() == pytest.approx(
        edges(board, still).right())


def test_several_chosen_snap_as_one(board):
    still = picture(board, 0, 0)
    first = picture(board, 300, 0)
    second = picture(board, 300, 200)
    at_size(board)
    board.scene.clearSelection()
    first.setSelected(True)
    second.setSelected(True)

    drag(board, first, (-94, 0))

    assert edges(board, first).left() == pytest.approx(
        edges(board, still).right())
    assert edges(board, second).left() == pytest.approx(
        edges(board, still).right())
