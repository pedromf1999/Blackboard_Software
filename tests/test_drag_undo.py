"""Dragging things about, then undoing and redoing it.

Each test drags the way the board does -- Qt moves what is selected,
then letting go records it -- and checks that undo puts every item, and
every group's box, back exactly where it was, and redo exactly where
the drag left it.
"""

from unittest.mock import MagicMock, patch

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref.items import BeePixmapItem


def image(view, x, y):
    img = QtGui.QImage(100, 80, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor('red'))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def group(view, items):
    view.scene.deselect_all_items()
    for item in items:
        item.setSelected(True)
    before = set(view.scene.items_by_type('group'))
    view.on_action_group_items()
    made = [g for g in view.scene.items_by_type('group') if g not in before]
    view.scene.deselect_all_items()
    return made[0]


def drag(view, dx, dy, alt=False):
    """Move what is selected as Qt does, then let go as the board does."""

    scene = view.scene
    movable = QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable
    for item in scene.selectedItems():
        if not item.flags() & movable:
            continue
        parent, carried = item.parentItem(), False
        while parent is not None:
            if parent.isSelected() and parent.flags() & movable:
                carried = True
            parent = parent.parentItem()
        if not carried:
            item.moveBy(dx, dy)

    scene.active_mode = scene.MOVE_MODE
    scene.event_start = QtCore.QPointF(0, 0)
    event = MagicMock()
    event.scenePos.return_value = QtCore.QPointF(dx, dy)
    event.button.return_value = Qt.MouseButton.LeftButton
    event.modifiers.return_value = (Qt.KeyboardModifier.AltModifier if alt
                                    else Qt.KeyboardModifier.NoModifier)
    # Qt's own part of letting go only takes a real event, and does
    # nothing that matters to what is recorded
    with patch.object(QtWidgets.QGraphicsScene, 'mouseReleaseEvent',
                      lambda self, e: None):
        scene.mouseReleaseEvent(event)


def where(view):
    """Where everything is: each item's place and group, each box."""

    state = {}
    for item in view.scene.items():
        if not hasattr(item, 'save_id'):
            continue
        parent = item.parentItem()
        pos = item.scenePos()
        box = item.rect() if getattr(item, 'TYPE', None) == 'group' else None
        state[id(item)] = (round(pos.x(), 3), round(pos.y(), 3),
                           id(parent) if parent is not None else None,
                           box)
    return state


def undo_and_redo(view, before, after):
    view.undo_stack.undo()
    assert where(view) == before
    view.undo_stack.redo()
    assert where(view) == after


def test_a_group_and_an_item_in_it_selected_together_come_back(view):
    """Qt moves the item with its group. Recorded as moved on its own as
    well, undo took it back twice and left it out of place."""

    b, c = image(view, 300, 0), image(view, 450, 0)
    g = group(view, [b, c])
    view.scene.enter_group(g, b)
    b.setSelected(True)
    g.setSelected(True)
    before = where(view)

    drag(view, 100, 100)
    after = where(view)
    assert b.scenePos() == QtCore.QPointF(400, 100)

    view.undo_stack.undo()
    assert b.scenePos() == QtCore.QPointF(300, 0)
    assert where(view) == before
    view.undo_stack.redo()
    assert where(view) == after


def test_the_box_an_item_was_dragged_out_of_goes_back_to_its_size(view):
    """Dragged past the edge, the item stays in its group and the box
    grows to follow; undo put the item back but left the box grown."""

    b, c = image(view, 300, 0), image(view, 450, 0)
    g = group(view, [b, c])
    view.scene.enter_group(g, b)
    box = g.rect()
    before = where(view)

    drag(view, 0, 400)
    after = where(view)
    assert g.rect().height() > box.height()

    view.undo_stack.undo()
    assert g.rect() == box
    assert where(view) == before
    view.undo_stack.redo()
    assert where(view) == after


def test_taking_an_item_out_with_alt_comes_back(view):
    b, c = image(view, 300, 0), image(view, 450, 0)
    g = group(view, [b, c])
    view.scene.enter_group(g, b)
    before = where(view)

    drag(view, 0, 300, alt=True)
    after = where(view)
    assert b.parentItem() is None

    undo_and_redo(view, before, after)
    view.undo_stack.undo()
    assert b.parentItem() is g


def test_a_drop_into_a_group_still_joins_it_and_comes_back(view):
    """How the drop works is unchanged: only undo and redo are."""

    a = image(view, 0, 0)
    g = group(view, [image(view, 300, 0), image(view, 450, 0)])
    view.scene.deselect_all_items()
    a.setSelected(True)
    before = where(view)

    drag(view, 320, 10)
    after = where(view)
    assert a.parentItem() is g

    undo_and_redo(view, before, after)


def test_a_group_dropped_onto_another_still_goes_in_and_comes_back(view):
    g1 = group(view, [image(view, 0, 0), image(view, 150, 0)])
    g2 = group(view, [image(view, 600, 0), image(view, 750, 0)])
    view.scene.deselect_all_items()
    g1.setSelected(True)
    before = where(view)

    drag(view, 620, 10)
    after = where(view)
    assert g1.parentItem() is g2

    undo_and_redo(view, before, after)


def test_a_drag_is_still_one_step_to_undo(view):
    a = image(view, 0, 0)
    view.scene.deselect_all_items()
    a.setSelected(True)
    depth = view.undo_stack.index()

    drag(view, 50, 0)
    assert view.undo_stack.index() == depth + 1


def test_the_items_a_drag_moved_leave_out_those_their_group_carried(view):
    b, c = image(view, 300, 0), image(view, 450, 0)
    g = group(view, [b, c])
    view.scene.enter_group(g, b)
    b.setSelected(True)
    g.setSelected(True)

    moved = view.scene.moved_by_drag(view.scene.selectedItems())
    assert g in moved
    assert b not in moved
