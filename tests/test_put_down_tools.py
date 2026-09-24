"""The task list and table buttons wait for a click to say where."""

from unittest.mock import patch

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref import constants
from beeref.assets import BeeAssets
from beeref.items import BeePixmapItem, BeeTextItem


def click_board(view, scene_point):
    view.resize(800, 600)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier,
                     view.mapFromScene(scene_point))


def notes(view):
    return [item for item in view.scene.items()
            if isinstance(item, BeeTextItem)]


def centre(item):
    return item.mapToScene(item.center)


def test_the_task_list_button_waits_for_a_click(view):
    view.draw_toolbar.insert_tasks.click()

    assert view.draw_tool == constants.TASKS_TOOL
    assert view.draw_toolbar.insert_tasks.isChecked() is True
    assert notes(view) == []


def test_the_cursor_shows_what_the_click_will_put_down(view):
    view.draw_toolbar.insert_tasks.click()
    assert view.tool_cursor() is BeeAssets().cursor_tool('tasks')

    view.draw_toolbar.insert_table.click()
    assert view.tool_cursor() is BeeAssets().cursor_tool('table')


def test_the_task_list_goes_where_the_board_is_clicked(view):
    view.draw_toolbar.insert_tasks.click()
    point = QtCore.QPointF(120, 80)

    click_board(view, point)

    [item] = notes(view)
    assert item.has_tasks() is True
    assert item.edit_mode is True
    assert (centre(item) - point).manhattanLength() < 2


def test_the_tool_steps_aside_once_it_is_used(view):
    view.draw_toolbar.insert_tasks.click()

    click_board(view, QtCore.QPointF(0, 0))

    assert view.draw_tool is None
    assert view.draw_toolbar.insert_tasks.isChecked() is False


def test_the_table_goes_where_the_board_is_clicked(view):
    view.draw_toolbar.insert_table.click()
    assert view.draw_tool == constants.TABLE_TOOL
    point = QtCore.QPointF(-60, 40)

    click_board(view, point)

    item = view.scene.item_with_table()
    assert item is not None
    assert item.edit_mode is True
    # The table starts where the board was clicked and grows from there,
    # down and to the right, rather than covering what was clicked on
    box = item.sceneBoundingRect()
    assert box.contains(point)
    assert point.x() < box.center().x()
    assert point.y() < box.center().y()
    assert view.draw_tool is None


def test_clicking_on_a_group_puts_it_in_the_group(view):
    img = QtGui.QImage(300, 200, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(60, 60, 60))
    picture = BeePixmapItem(img)
    view.scene.addItem(picture)
    picture.setSelected(True)
    view.on_action_group_items()
    group = picture.parentItem()
    view.scene.clearSelection()

    view.draw_toolbar.insert_tasks.click()
    click_board(view, group.mapToScene(group.rect().center()))

    [item] = notes(view)
    assert item.parentItem() is group


def test_the_table_button_fills_the_note_being_written(view):
    """While a note is open, its table goes in at the text cursor."""

    view.on_action_insert_text()
    item = view.scene.edit_item

    view.draw_toolbar.insert_table.click()

    assert item.current_table() is not None
    assert view.draw_tool is None
    assert view.draw_toolbar.insert_table.isChecked() is False


def test_escape_puts_the_tool_away(view):
    view.draw_toolbar.insert_table.click()

    view.escape()

    assert view.draw_tool is None
    assert view.draw_toolbar.insert_table.isChecked() is False


def test_the_keyboard_still_puts_one_under_the_mouse(view):
    """The mouse is on the board already, so there is nothing to ask."""

    view.resize(800, 600)
    point = QtCore.QPointF(30, 20)
    with patch('PyQt6.QtGui.QCursor.pos', return_value=view.mapToGlobal(
            view.mapFromScene(point))):
        view.on_action_insert_tasks()

    [item] = notes(view)
    assert item.has_tasks() is True
    assert view.draw_tool is None
