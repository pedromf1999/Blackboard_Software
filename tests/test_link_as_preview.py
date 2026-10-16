"""A note that is a link, shown as the picture its page offers."""

import os
from unittest.mock import patch

from PyQt6 import QtCore, QtGui
import pytest

from beeref.actions.menu_structure import TEXT_MENU, menu_structure
from beeref.items import BeePixmapItem, BeeTextItem


def linked_page(tmpdir):
    image = QtGui.QImage(40, 20, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('orange'))
    image_path = os.path.join(str(tmpdir), 'picture.png')
    image.save(image_path)
    image_url = QtCore.QUrl.fromLocalFile(image_path).toString()
    page_path = os.path.join(str(tmpdir), 'page.html')
    with open(page_path, 'w', encoding='utf-8') as f:
        f.write(f'<meta property="og:image" content="{image_url}">')
    # Encoded: the folder's name has a space in it, and a link with a
    # space would be words rather than a link
    return bytes(QtCore.QUrl.fromLocalFile(page_path).toEncoded()).decode()


def note(view, text, pos=(0, 0)):
    item = BeeTextItem(text)
    view.scene.addItem(item)
    item.setPos(*pos)
    item.setSelected(True)
    return item


def pictures(view):
    return [item for item in view.scene.items()
            if isinstance(item, BeePixmapItem)]


def notes(view):
    return [item for item in view.scene.items()
            if isinstance(item, BeeTextItem)]


@pytest.fixture
def file_links(monkeypatch):
    """Take file addresses as links, so that the tests need no network."""

    from beeref import link_preview
    monkeypatch.setattr(link_preview, 'LINK_RE', link_preview.re.compile(
        r'^(?:https?://|www\.|file:///)\S+$', link_preview.re.IGNORECASE))


def test_a_link_note_becomes_its_picture(view, qtbot, tmpdir, file_links):
    url = linked_page(tmpdir)
    note(view, url)
    view.on_action_link_as_preview()
    qtbot.waitUntil(lambda: bool(pictures(view)), timeout=10000)
    assert notes(view) == []
    assert pictures(view)[0].caption == url


def test_undo_gives_the_note_back(view, qtbot, tmpdir, file_links):
    url = linked_page(tmpdir)
    item = note(view, url)
    view.on_action_link_as_preview()
    qtbot.waitUntil(lambda: bool(pictures(view)), timeout=10000)
    view.undo_stack.undo()
    assert notes(view) == [item]
    assert pictures(view) == []


def test_there_and_back_again(view, qtbot, tmpdir, file_links):
    url = linked_page(tmpdir)
    note(view, url)
    view.on_action_link_as_preview()
    qtbot.waitUntil(lambda: bool(pictures(view)), timeout=10000)
    view.on_action_link_as_text()
    assert [item.toPlainText() for item in notes(view)] == [url]
    view.on_action_link_as_preview()
    qtbot.waitUntil(lambda: bool(pictures(view)), timeout=10000)
    assert notes(view) == []


def test_a_note_being_written_is_settled_first(view, qtbot, tmpdir,
                                               file_links):
    url = linked_page(tmpdir)
    item = note(view, url)
    item.enter_edit_mode()
    view.on_action_link_as_preview()
    assert item.edit_mode is False
    qtbot.waitUntil(lambda: bool(pictures(view)), timeout=10000)
    assert pictures(view)[0].caption == url


def test_which_notes_are_links(view):
    plain = note(view, 'just words')
    sentence = note(view, 'see https://example.com', pos=(0, 100))
    link = note(view, 'https://example.com', pos=(0, 200))
    titled = note(view, 'https://example.com/b', pos=(0, 300))
    titled.title = 'Chair'
    assert view.selected_link_notes() == [link]
    assert plain.isSelected() and sentence.isSelected()


def test_a_pinned_note_is_a_link_to_show_too(view):
    # Its picture takes its place in the tab; see test_pin_pictures.py
    item = note(view, 'https://example.com')
    with patch.object(BeeTextItem, 'is_pinned', True):
        assert view.selected_link_notes() == [item]


def test_nothing_happens_without_a_link(view):
    note(view, 'just words')
    view.on_action_link_as_preview()
    assert view.link_previews == []


def test_the_button_shows_only_on_a_link(view):
    bar = view.text_toolbar
    item = note(view, 'https://example.com')
    view.update_text_toolbar()
    assert bar.as_preview.isVisibleTo(bar)
    item.setPlainText('just words')
    view.update_text_toolbar()
    assert not bar.as_preview.isVisibleTo(bar)


def test_it_is_in_the_text_menu():
    text = [entry for entry in menu_structure
            if isinstance(entry, dict) and entry.get('menu') == TEXT_MENU]
    assert 'link_as_preview' in text[0]['items']
