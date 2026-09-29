"""What is copied is pasted where the mouse is."""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6 import QtCore, QtGui

from beeref import commands
from beeref.items import BeeGroupItem, BeePixmapItem, BeeTextItem


@pytest.fixture
def clipboard():
    """A clipboard of our own, so that the real one is left alone."""

    held = {}
    fake = MagicMock()
    fake.setMimeData.side_effect = lambda data: held.__setitem__('data', data)
    fake.mimeData.side_effect = lambda: held.get('data', QtCore.QMimeData())
    with patch('PyQt6.QtWidgets.QApplication.clipboard', return_value=fake):
        yield fake


def picture(view, x, y):
    img = QtGui.QImage(300, 200, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(90, 90, 110))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def note(view, text, x, y):
    item = BeeTextItem(text)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def a_group(view):
    """A titled group of a picture and a note, filling the view."""

    view.resize(900, 700)
    group = BeeGroupItem(title='Renders')
    commands.GroupItems(view.scene, [picture(view, 0, 0),
                                     note(view, 'a note', 400, 50)],
                        group).redo()
    view.scene.clearSelection()
    return group


def copy(view, item):
    view.scene.clearSelection()
    item.setSelected(True)
    view.on_action_copy()


def paste_with_mouse_at(view, scene_pos):
    """Paste with the mouse over a point of the board."""

    point = view.mapFromScene(scene_pos)
    with patch('PyQt6.QtGui.QCursor.pos',
               return_value=view.viewport().mapToGlobal(point)):
        view.on_action_paste()
    return view.mapToScene(point)


def pasted(view):
    return view.scene.selectedItems(user_only=True)


def centre(view, items):
    return view.scene.itemsBoundingRect(items=items).center()


def close(a, b):
    return abs(a.x() - b.x()) < 1 and abs(a.y() - b.y()) < 1


def test_a_group_is_pasted_where_the_mouse_is(view, clipboard):
    group = a_group(view)
    copy(view, group)
    # Out of the way, so that the mouse is over empty board
    group.setPos(-50000, -50000)

    for point in (QtCore.QPoint(150, 120), QtCore.QPoint(700, 520)):
        mouse = paste_with_mouse_at(view, view.mapToScene(point))
        copies = pasted(view)
        assert [type(item) for item in copies] == [BeeGroupItem]
        assert close(centre(view, copies), mouse)
        # On empty board: a group of its own, not inside anything
        assert copies[0].parentItem() is None


def test_a_group_pasted_on_a_group_goes_inside_it(view, clipboard):
    """It used to be asked to go inside itself, and jumped away."""

    group = a_group(view)
    copy(view, group)
    spot = group.mapToScene(group.rect().center())

    mouse = paste_with_mouse_at(view, spot)
    copies = pasted(view)
    assert len(copies) == 1
    assert copies[0] is not group
    assert copies[0].parentItem() is group
    assert close(centre(view, copies), mouse)


def test_a_note_pasted_on_a_group_joins_it_and_stays_in_hand(
        view, clipboard):
    group = a_group(view)
    loose = note(view, 'loose note', 0, 900)
    copy(view, loose)
    spot = group.mapToScene(group.rect().center())

    mouse = paste_with_mouse_at(view, spot)
    copies = pasted(view)
    assert len(copies) == 1
    assert copies[0].toPlainText() == 'loose note'
    assert copies[0].parentItem() is group
    assert group.isSelected() is False
    assert close(centre(view, copies), mouse)


def test_pasting_from_a_right_click_goes_where_the_click_was(
        view, clipboard):
    item = note(view, 'a note', 0, 0)
    copy(view, item)
    click = QtCore.QPoint(300, 200)
    view.show_context_menu = lambda point: view.on_action_paste()

    # The mouse is on the menu's Paste by then, somewhere else
    elsewhere = view.viewport().mapToGlobal(QtCore.QPoint(420, 330))
    with patch('PyQt6.QtGui.QCursor.pos', return_value=elsewhere):
        view.on_context_menu(click)

    assert close(centre(view, pasted(view)), view.mapToScene(click))
    assert view.context_menu_pos is None


def test_pasting_from_the_menu_bar_goes_in_the_middle(view, clipboard):
    view.resize(900, 700)
    item = note(view, 'a note', 0, 0)
    copy(view, item)
    above_the_board = view.viewport().mapToGlobal(QtCore.QPoint(300, -40))
    with patch('PyQt6.QtGui.QCursor.pos', return_value=above_the_board):
        view.on_action_paste()

    middle = view.mapToScene(view.get_view_center())
    assert close(centre(view, pasted(view)), middle)
