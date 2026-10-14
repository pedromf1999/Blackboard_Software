"""The size buttons beside a picture make the picture bigger or smaller."""

from PyQt6 import QtCore, QtGui
import pytest

from beeref.actions.menu_structure import IMAGES_MENU, menu_structure
from beeref.items import BeePixmapItem, BeeTextItem


def image(view, width=200, height=100, pos=(0, 0)):
    img = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtGui.QColor('red'))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setPos(*pos)
    item.setSelected(True)
    return item


def test_bigger_makes_the_picture_bigger(view):
    item = image(view)
    view.on_action_size_increase()
    assert item.scale() == pytest.approx(1.1)


def test_smaller_makes_the_picture_smaller(view):
    item = image(view)
    view.on_action_size_decrease()
    assert item.scale() == pytest.approx(1 / 1.1)


def test_the_picture_grows_about_its_middle(view):
    item = image(view, pos=(50, 80))
    middle = item.sceneBoundingRect().center()
    for _ in range(3):
        view.on_action_size_increase()
    assert item.sceneBoundingRect().center().x() == pytest.approx(middle.x())
    assert item.sceneBoundingRect().center().y() == pytest.approx(middle.y())


def test_each_press_is_one_step_to_undo(view):
    item = image(view)
    view.on_action_size_increase()
    view.on_action_size_increase()
    assert view.undo_stack.count() == 2
    view.undo_stack.undo()
    view.undo_stack.undo()
    assert item.scale() == pytest.approx(1)
    assert item.pos() == QtCore.QPointF(0, 0)


def test_several_pictures_grow_together(view):
    """About the middle of all of them, so they keep their places
    relative to each other, as dragging a corner does."""

    first = image(view, pos=(0, 0))
    second = image(view, pos=(300, 0))
    gap = second.pos().x() - first.pos().x()
    view.on_action_size_increase()
    assert first.scale() == pytest.approx(1.1)
    assert second.scale() == pytest.approx(1.1)
    assert second.pos().x() - first.pos().x() == pytest.approx(gap * 1.1)


def test_the_contour_stays_as_it_was(view):
    item = image(view)
    view.on_action_image_outline()
    width = item.outline_width
    view.on_action_size_increase()
    assert item.outline_width == width


def test_a_picture_and_a_note_both_grow(view):
    item = image(view)
    note = BeeTextItem('words')
    view.scene.addItem(note)
    note.setSelected(True)
    size = note.largest_point_size()
    view.on_action_size_increase()
    assert item.scale() == pytest.approx(1.1)
    assert note.largest_point_size() > size


def test_nothing_selected_records_nothing(view):
    image(view).setSelected(False)
    view.on_action_size_increase()
    assert view.undo_stack.count() == 0


def test_the_buttons_say_they_size_the_picture(view):
    item = image(view)
    view.image_toolbar.update_state([item])
    assert view.image_toolbar.thicker.isEnabled() is True
    assert view.image_toolbar.thicker.toolTip() == 'Bigger image (Ctrl++)'
    assert view.image_toolbar.thinner.toolTip() == 'Smaller image (Ctrl+-)'


def test_the_contour_width_is_in_the_images_menu():
    images = [entry for entry in menu_structure
              if isinstance(entry, dict) and entry.get('menu') == IMAGES_MENU]
    assert 'image_outline_thinner' in images[0]['items']
    assert 'image_outline_thicker' in images[0]['items']


def test_the_menu_thickens_and_thins_the_contour(view):
    item = image(view)
    view.on_action_image_outline()
    width = item.outline_width
    view.on_action_image_outline_thicker()
    assert item.outline_width > width
    view.on_action_image_outline_thinner()
    assert item.outline_width == pytest.approx(width)
    assert item.scale() == 1
