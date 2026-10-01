"""A group with no title has no band, and is taken up by its top edge."""

from unittest.mock import MagicMock

import pytest
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref import commands
from beeref.items import BeeGroupItem, BeePixmapItem


def picture(view, x, y, width=200, height=150):
    img = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(90, 90, 110))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def a_group(view, zoom=1):
    """Two pictures in a group, seen at the given zoom."""

    view.resize(900, 700)
    first = picture(view, 0, 0)
    second = picture(view, 400, 0)
    group = BeeGroupItem()
    commands.GroupItems(view.scene, [first, second], group).redo()
    view.scene.clearSelection()
    view.setTransform(QtGui.QTransform.fromScale(zoom, zoom))
    view.centerOn(group)
    return group


def on_screen(view, group, point):
    return view.mapFromScene(group.mapToScene(point))


def cursor_shape(view):
    return view.viewport().cursor().shape()


def hover(group, point):
    event = MagicMock()
    event.pos.return_value = point
    group.hoverMoveEvent(event)


def test_an_untitled_group_has_no_band(view):
    group = a_group(view)
    [first, _] = group.bee_children()
    top_of_items = group.mapFromItem(
        first, first.boundingRect()).boundingRect().top()

    assert group.shows_header() is False
    # Only the margin above what it holds, as on the other three sides
    assert group.rect().top() == pytest.approx(
        top_of_items - group.top_padding)


def test_the_top_edge_runs_along_the_top_of_the_box(view):
    group = a_group(view)
    edge = group.top_edge_rect()

    assert edge.top() == group.rect().top()
    assert edge.left() == group.rect().left()
    assert edge.width() == group.rect().width()


def test_the_top_edge_is_a_fixed_depth_on_the_screen(view):
    group = a_group(view, zoom=1)
    group.top_padding = 100

    assert group.top_edge_rect().height() == pytest.approx(
        BeeGroupItem.TOP_EDGE_DEPTH)

    view.setTransform(QtGui.QTransform.fromScale(2, 2))
    assert group.top_edge_rect().height() == pytest.approx(
        BeeGroupItem.TOP_EDGE_DEPTH / 2)


def test_the_top_edge_stops_at_what_the_group_holds(view):
    """Whatever is inside is picked out by itself, edge or no edge."""

    group = a_group(view, zoom=0.5)

    assert group.top_edge_rect().height() == pytest.approx(
        group.top_padding)


def test_a_thin_margin_still_leaves_an_edge_the_mouse_can_find(view):
    group = a_group(view, zoom=0.1)

    assert group.top_edge_rect().height() == pytest.approx(
        BeeGroupItem.TOP_EDGE_MIN_DEPTH / 0.1)


def test_a_tiny_group_keeps_half_its_box_for_what_it_holds(view):
    group = a_group(view, zoom=0.001)

    assert group.top_edge_rect().height() == pytest.approx(
        group.rect().height() / 2)


def test_the_group_answers_on_its_top_edge_only(view):
    group = a_group(view)
    edge = group.top_edge_rect()

    assert group.contains(edge.center()) is True
    below = QtCore.QPointF(edge.center().x(), edge.bottom() + 2)
    assert group.contains(below) is False


def test_a_titled_group_is_taken_up_by_its_band_instead(view):
    group = a_group(view)
    group.title = 'Lid Latch'

    assert group.grab_rect() == group.header_rect()
    assert group.on_top_edge(group.header_rect().center()) is False


def test_the_hand_shows_on_the_top_edge(view):
    group = a_group(view)

    hover(group, group.top_edge_rect().center())

    assert cursor_shape(view) == Qt.CursorShape.OpenHandCursor


def test_the_hand_goes_once_the_mouse_leaves_the_edge(view):
    group = a_group(view)
    hover(group, group.top_edge_rect().center())

    group.hoverLeaveEvent(MagicMock())

    assert cursor_shape(view) == Qt.CursorShape.ArrowCursor


def test_no_hand_over_a_titled_band(view):
    """Only where nothing shows that the group can be taken up."""

    group = a_group(view)
    group.title = 'Lid Latch'

    hover(group, group.header_rect().center())

    assert cursor_shape(view) != Qt.CursorShape.OpenHandCursor


def test_the_corner_handles_keep_their_own_cursors(view):
    group = a_group(view)
    group.setSelected(True)
    corner = group.rect().topLeft()

    assert group.on_top_edge(corner) is False
    hover(group, corner)

    assert cursor_shape(view) != Qt.CursorShape.OpenHandCursor


def test_the_hand_closes_while_the_group_is_held(view):
    group = a_group(view)
    start = on_screen(view, group, group.top_edge_rect().center())

    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    assert cursor_shape(view) == Qt.CursorShape.ClosedHandCursor

    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, start)
    assert cursor_shape(view) == Qt.CursorShape.OpenHandCursor


def test_dragging_the_top_edge_moves_the_group(view):
    group = a_group(view)
    [first, _] = group.bee_children()
    before = first.scenePos()
    start = on_screen(view, group, group.top_edge_rect().center())
    end = start + QtCore.QPoint(60, 40)

    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 6):
        point = start + (end - start) * step / 5
        event = QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseMove, QtCore.QPointF(point),
            QtCore.QPointF(view.viewport().mapToGlobal(point)),
            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier)
        QtGui.QGuiApplication.sendEvent(view.viewport(), event)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, end)

    moved = first.scenePos() - before
    assert moved.x() == pytest.approx(60)
    assert moved.y() == pytest.approx(40)
    assert group.isSelected() is True


def test_a_title_written_on_the_top_edge_brings_its_band(view):
    group = a_group(view)
    [first, _] = group.bee_children()
    before = first.scenePos()
    bottom = group.rect().bottom()

    edge = group.mapToScene(group.top_edge_rect().center())
    assert view.scene.title_double_clicked(group, edge) is True
    group.title_editor.setPlainText('Lid Latch')
    group.exit_title_edit_mode()

    assert group.title == 'Lid Latch'
    assert group.shows_header() is True
    # Above what the group holds, which stays where it was
    assert first.scenePos() == before
    assert group.rect().bottom() == pytest.approx(bottom)
