"""A link's picture put away, leaving the link as a note."""

from PyQt6 import QtGui
import pytest

from beeref.actions.menu_structure import IMAGES_MENU, menu_structure
from beeref.items import BeePixmapItem, BeeTextItem


URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'


def picture(view, caption=URL, pos=(0, 0), selected=True):
    image = QtGui.QImage(200, 100, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor('red'))
    item = BeePixmapItem(image)
    item.caption = caption
    view.scene.addItem(item)
    item.setPos(*pos)
    item.setSelected(selected)
    return item


def notes(view):
    return [item for item in view.scene.items()
            if isinstance(item, BeeTextItem)]


def pictures(view):
    return [item for item in view.scene.items()
            if isinstance(item, BeePixmapItem)]


def test_the_picture_becomes_the_link(view):
    picture(view)
    view.on_action_link_as_text()
    assert pictures(view) == []
    assert [note.toPlainText() for note in notes(view)] == [URL]


def test_the_note_goes_where_the_picture_was(view):
    item = picture(view, pos=(300, 120))
    where = view.scene.itemsBoundingRect(items=[item]).center()
    view.on_action_link_as_text()
    middle = view.scene.itemsBoundingRect(items=notes(view)).center()
    assert middle.x() == pytest.approx(where.x(), abs=1)
    assert middle.y() == pytest.approx(where.y(), abs=1)


def test_the_note_is_selected_in_its_place(view):
    picture(view)
    view.on_action_link_as_text()
    assert notes(view)[0].isSelected()


def test_undo_gives_the_picture_back(view):
    item = picture(view)
    view.on_action_link_as_text()
    assert view.undo_stack.undoText() == 'Show link as text'
    view.undo_stack.undo()
    assert pictures(view) == [item]
    assert notes(view) == []
    view.undo_stack.redo()
    assert pictures(view) == []


def test_several_links_at_once_in_one_step(view):
    picture(view, pos=(0, 0))
    picture(view, 'https://github.com/rbreu/beeref', pos=(400, 0))
    view.on_action_link_as_text()
    assert sorted(note.toPlainText() for note in notes(view)) == [
        'https://github.com/rbreu/beeref', URL]
    assert view.undo_stack.count() == 1
    assert all(note.isSelected() for note in notes(view))


def test_a_picture_with_words_for_a_caption_is_left(view):
    item = picture(view, 'Inspired by https://example.com/chair')
    view.on_action_link_as_text()
    assert pictures(view) == [item]
    assert view.undo_stack.count() == 0


def test_only_the_links_among_the_pictures_change(view):
    link = picture(view, pos=(0, 0))
    plain = picture(view, 'A chair', pos=(400, 0))
    view.on_action_link_as_text()
    assert pictures(view) == [plain]
    assert link.scene() is None


def test_the_button_shows_only_on_a_link(view):
    bar = view.image_toolbar
    link = picture(view)
    bar.update_state([link])
    assert bar.as_text.isVisibleTo(bar)
    plain = picture(view, 'A chair')
    bar.update_state([plain])
    assert not bar.as_text.isVisibleTo(bar)


def test_the_button_puts_the_picture_away(view):
    item = picture(view)
    view.scene.clearSelection()
    item.setSelected(True)
    view.image_toolbar.update_state([item])
    view.image_toolbar.as_text.click()
    assert [note.toPlainText() for note in notes(view)] == [URL]


def test_it_is_in_the_images_menu():
    images = [entry for entry in menu_structure
              if isinstance(entry, dict) and entry.get('menu') == IMAGES_MENU]
    assert 'link_as_text' in images[0]['items']


def test_what_else_was_selected_stays_selected(view):
    other = BeeTextItem('other')
    view.scene.addItem(other)
    other.setSelected(True)
    picture(view)
    view.on_action_link_as_text()
    assert other.isSelected()
