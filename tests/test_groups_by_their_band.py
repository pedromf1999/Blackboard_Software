"""A group is taken up by its band; what is inside it, by itself."""

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref import commands
from beeref.items import BeeGroupItem, BeePixmapItem


def picture(view, x, y, width=200, height=150, shade=(90, 90, 110)):
    img = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(*shade))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def a_group(view):
    """Two pictures in a group, with room between them, on screen."""

    view.resize(900, 700)
    first = picture(view, 0, 0)
    second = picture(view, 400, 0)
    group = BeeGroupItem()
    commands.GroupItems(view.scene, [first, second], group).redo()
    view.scene.clearSelection()
    view.on_action_fit_scene()
    return group, first, second


def on_screen(view, item, point):
    return view.mapFromScene(item.mapToScene(point))


def click(view, point, modifier=Qt.KeyboardModifier.NoModifier):
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, modifier,
                     point)


def drag(view, start, end):
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


def middle_of(item):
    return item.boundingRect().center()


def selected(view):
    return view.scene.selectedItems(user_only=True)


def between(group, first, second):
    """An empty spot inside the box, between the two pictures."""

    left = group.mapFromItem(first, first.boundingRect().topRight())
    right = group.mapFromItem(second, second.boundingRect().topLeft())
    return QtCore.QPointF((left.x() + right.x()) / 2, left.y() + 60)


def test_a_click_on_something_in_a_group_picks_it_out(view):
    group, first, second = a_group(view)

    click(view, on_screen(view, first, middle_of(first)))

    assert selected(view) == [first]


def test_a_click_on_the_band_takes_up_the_group(view):
    group, first, second = a_group(view)

    click(view, on_screen(view, group, group.header_rect().center()))

    assert selected(view) == [group]


def test_the_group_is_moved_by_its_band_with_all_it_holds(view):
    group, first, second = a_group(view)
    start = on_screen(view, group, group.header_rect().center())
    before = first.scenePos()

    drag(view, start, start + QtCore.QPoint(60, 40))

    assert group.pos() != QtCore.QPointF(0, 0)
    moved = first.scenePos() - before
    assert moved.x() > 0 and moved.y() > 0


def test_something_in_a_group_is_moved_on_its_own(view):
    group, first, second = a_group(view)
    start = on_screen(view, first, middle_of(first))
    group_before = group.scenePos()
    second_before = second.scenePos()

    drag(view, start, start + QtCore.QPoint(30, 30))

    assert first.parentItem() is group
    assert group.scenePos() == group_before
    assert second.scenePos() == second_before


def test_the_empty_inside_of_a_group_takes_nothing_up(view):
    group, first, second = a_group(view)
    group.setSelected(True)

    click(view, on_screen(view, group, between(group, first, second)))

    assert selected(view) == []
    assert group.pos() == QtCore.QPointF(0, 0)


def test_a_rectangle_drawn_inside_a_group_picks_out_what_it_holds(view):
    group, first, second = a_group(view)
    start = on_screen(view, group, between(group, first, second))
    end = on_screen(view, second, middle_of(second))

    drag(view, start, end)

    assert selected(view) == [second]


def test_what_is_hidden_behind_a_group_cannot_be_clicked_through_it(view):
    group, first, second = a_group(view)
    behind = picture(view, 0, 0, 900, 700, shade=(200, 50, 50))
    behind.setPos(group.mapToScene(group.rect().topLeft()))
    behind.setZValue(group.zValue() - 10)
    view.scene.clearSelection()

    click(view, on_screen(view, group, between(group, first, second)))

    assert behind.isSelected() is False


def test_a_locked_group_is_one_piece(view):
    group, first, second = a_group(view)
    group.locked = True
    group.set_children_interactive()

    click(view, on_screen(view, first, middle_of(first)))

    assert selected(view) == [group]


def test_picking_something_out_of_a_selected_group_keeps_the_thing(view):
    group, first, second = a_group(view)
    group.setSelected(True)

    # Shift adds to what is selected
    click(view, on_screen(view, first, middle_of(first)),
          Qt.KeyboardModifier.ShiftModifier)

    assert first.isSelected() is True
    assert group.isSelected() is False


def test_choosing_a_group_lets_go_of_what_was_picked_out_of_it(view):
    group, first, second = a_group(view)
    first.setSelected(True)

    click(view, on_screen(view, group, group.header_rect().center()),
          Qt.KeyboardModifier.ShiftModifier)

    assert group.isSelected() is True
    assert first.isSelected() is False


def test_select_all_takes_the_group_rather_than_what_it_holds(view):
    """Or deleting or copying everything would do it to them twice."""

    group, first, second = a_group(view)
    loose = picture(view, 0, 600)

    view.scene.select_all_items()

    assert set(selected(view)) == {group, loose}


def test_deleting_everything_and_undoing_brings_it_all_back(view):
    group, first, second = a_group(view)
    view.scene.select_all_items()

    view.on_action_delete_items()
    assert group.scene() is None

    view.undo_stack.undo()
    assert group.scene() is view.scene
    assert set(group.bee_children()) == {first, second}
