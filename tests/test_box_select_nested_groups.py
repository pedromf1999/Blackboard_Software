"""A selection rectangle dragged across groups with groups inside them,
pictures and notes takes up the groups, not what is in them; and
grouping never takes anything out of the group it is in."""

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref import commands
from beeref.items import BeeGroupItem, BeePixmapItem, BeeTextItem


def picture(view, x, y):
    img = QtGui.QImage(120, 90, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(90, 90, 110))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def note(view, words, x, y):
    item = BeeTextItem(words)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def grouped(view, items):
    group = BeeGroupItem()
    commands.GroupItems(view.scene, items, group).redo()
    view.scene.clearSelection()
    return group


class Board:
    """Two groups, each with a group inside, pictures and notes at each
    level, a group three deep, and a picture and a note on their own."""

    def __init__(self, view):
        view.resize(1000, 700)
        self.a1 = picture(view, 0, 0)
        self.a2 = picture(view, 150, 0)
        self.inner_a = grouped(view, [self.a1, self.a2])
        self.a3 = picture(view, 0, 150)
        self.ta = note(view, 'notes about A', 160, 160)
        self.outer_a = grouped(view, [self.inner_a, self.a3, self.ta])
        self.b1 = picture(view, 450, 20)
        self.tb = note(view, 'inside B', 450, 140)
        self.inner_b = grouped(view, [self.b1, self.tb])
        self.b2 = picture(view, 620, 160)
        self.b3 = picture(view, 640, 20)
        self.deeper_b = grouped(view, [self.b3])
        self.outer_b = grouped(view, [self.inner_b, self.b2, self.deeper_b])
        self.loose = picture(view, 300, 330)
        self.loose_note = note(view, 'loose note', 50, 340)
        view.on_action_fit_scene()
        self.everything = [self.a1, self.a2, self.a3, self.ta, self.b1,
                           self.tb, self.b2, self.b3, self.loose,
                           self.loose_note, self.inner_a, self.inner_b,
                           self.deeper_b, self.outer_a, self.outer_b]
        self.groups_of = {id(item): groups_around(item)
                          for item in self.everything}

    def nothing_taken_out(self):
        """Every item still in each of the groups it was in, in the same
        order: the new group may stand anywhere among them."""

        for item in self.everything:
            now = iter(groups_around(item))
            assert all(any(group is later for later in now)
                       for group in self.groups_of[id(item)]), item


def groups_around(item):
    found = []
    parent = item.parentItem()
    while parent is not None:
        found.append(parent)
        parent = parent.parentItem()
    return found


def drag_rectangle(view, steps):
    """From above the top left of everything to past its bottom right,
    the way a hand drags it, a little at a time."""

    area = view.mapFromScene(
        view.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))
    rect = area.boundingRect()
    start, end = rect.topLeft(), rect.bottomRight()
    QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, steps + 1):
        point = start + (end - start) * step / steps
        event = QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseMove, QtCore.QPointF(point),
            QtCore.QPointF(view.viewport().mapToGlobal(point)),
            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier)
        QtGui.QGuiApplication.sendEvent(view.viewport(), event)
    QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, end)


def selected(view):
    return set(view.scene.selectedItems(user_only=True))


# The rectangle

def test_a_rectangle_takes_up_the_groups_not_what_is_in_them(view):
    board = Board(view)
    for steps in (3, 7, 24, 25):
        view.scene.deselect_all_items()
        drag_rectangle(view, steps)
        assert selected(view) == {board.outer_a, board.outer_b,
                                  board.loose, board.loose_note}, steps


def test_select_all_takes_up_the_groups_whatever_was_chosen_before(view):
    board = Board(view)
    board.b1.setSelected(True)
    view.scene.select_all_items()
    assert selected(view) == {board.outer_a, board.outer_b,
                              board.loose, board.loose_note}


def test_the_window_hears_of_a_rectangle_once_a_move(view):
    """Not once for every item let go: it drew itself afresh each time,
    263 times for a single move on a real board."""

    Board(view)
    scene = view.scene
    heard = []
    scene.selectionChanged.connect(lambda: heard.append(1))
    # What one move of the mouse does to the selection
    scene.active_mode = scene.RUBBERBAND_MODE
    area = QtGui.QPainterPath()
    area.addRect(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))
    scene.setSelectionArea(area)
    scene.active_mode = None
    # The change itself, and the frame round several items going up,
    # which tells of its own; it was 13
    assert len(heard) <= 2


def test_picking_out_of_a_chosen_group_still_picks_out(view):
    """Chosen one after the other, the last choice stays."""

    board = Board(view)
    board.outer_b.setSelected(True)
    board.b2.setSelected(True)
    assert selected(view) == {board.b2}


# Grouping all of it

def test_grouping_what_a_rectangle_took_up_keeps_every_group(view):
    board = Board(view)
    drag_rectangle(view, 25)
    view.on_action_group_items()
    board.nothing_taken_out()
    new = board.outer_a.parentItem()
    assert new is not None and new is board.outer_b.parentItem()
    assert board.loose.parentItem() is new


def test_grouping_is_undone_back_to_every_group(view):
    board = Board(view)
    drag_rectangle(view, 25)
    view.on_action_group_items()
    view.undo_stack.undo()
    for item in board.everything:
        assert groups_around(item) == board.groups_of[id(item)], item


def test_grouping_something_from_a_group_with_something_loose(view):
    """Its group comes in whole rather than the picture coming out."""

    board = Board(view)
    board.b2.setSelected(True)
    board.loose.setSelected(True)
    view.on_action_group_items()
    board.nothing_taken_out()
    assert board.outer_b.parentItem() is board.loose.parentItem()
    assert board.outer_a.parentItem() is None


def test_grouping_from_two_groups_inside_one_meets_inside_it(view):
    board = Board(view)
    board.b1.setSelected(True)
    board.b3.setSelected(True)
    view.on_action_group_items()
    board.nothing_taken_out()
    new = board.inner_b.parentItem()
    assert new is board.deeper_b.parentItem()
    assert new.parentItem() is board.outer_b


def test_grouping_in_one_group_still_makes_a_group_inside_it(view):
    board = Board(view)
    board.a3.setSelected(True)
    board.ta.setSelected(True)
    view.on_action_group_items()
    new = board.a3.parentItem()
    assert new is board.ta.parentItem()
    assert new.parentItem() is board.outer_a


def test_gathered_for_grouping_leaves_out_what_a_chosen_group_holds(view):
    board = Board(view)
    gathered = view.scene.gathered_for_grouping(
        [board.outer_b, board.b1, board.inner_b, board.loose])
    assert gathered == [board.outer_b, board.loose]
