"""A web address pasted on its own comes in as the picture its page
offers, with the address as its caption."""

import os
from unittest.mock import patch

from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets
import pytest

from beeref.items import BeePixmapItem, BeeTextItem
from beeref.link_preview import (
    link_in, LinkPreview, page_text, preview_image_url)


def page(tmpdir, head, name='page.html'):
    path = os.path.join(str(tmpdir), name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'<html><head>{head}</head><body>Hello</body></html>')
    return QtCore.QUrl.fromLocalFile(path).toString()


def picture(tmpdir, name='picture.png', size=(40, 20)):
    path = os.path.join(str(tmpdir), name)
    image = QtGui.QImage(*size, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('orange'))
    image.save(path)
    return QtCore.QUrl.fromLocalFile(path).toString()


def fetch(qtbot, url):
    manager = QtNetwork.QNetworkAccessManager()
    preview = LinkPreview(url, manager)
    result = {}
    preview.finished.connect(
        lambda image, icon, reason: result.update(
            image=image, reason=reason))
    preview.start()
    qtbot.waitUntil(lambda: bool(result), timeout=10000)
    return result['image'], result['reason']


class Clipboard:
    """Stands in for the computer's clipboard, which another program
    may be holding while the tests run."""

    def __init__(self, text):
        self.data = QtCore.QMimeData()
        self.data.setText(text)

    def mimeData(self):
        return self.data

    def image(self):
        return QtGui.QImage()

    def text(self):
        return self.data.text()


def paste(view, text):
    with patch.object(QtWidgets.QApplication, 'clipboard',
                      return_value=Clipboard(text)):
        view.on_action_paste()


# What counts as a link

@pytest.mark.parametrize('text,expected', [
    ('https://example.com/chair', 'https://example.com/chair'),
    ('  http://example.com \n', 'http://example.com'),
    ('www.example.pt/a', 'https://www.example.pt/a'),
    ('WWW.example.pt', 'https://WWW.example.pt'),
])
def test_link_in_a_link_on_its_own(text, expected):
    assert link_in(text) == expected


@pytest.mark.parametrize('text', [
    '', None, 'see https://example.com', 'https://a.com https://b.com',
    'ftp://example.com', 'example.com', 'https://example.com\nmore words'])
def test_link_in_anything_else(text):
    assert link_in(text) is None


# Finding the picture in the page

def test_preview_image_open_graph():
    html = '<meta property="og:image" content="https://x.com/a.jpg">'
    assert preview_image_url(html, 'https://x.com/p') == 'https://x.com/a.jpg'


def test_preview_image_relative_to_the_page():
    html = '<meta property="og:image" content="/img/a.jpg">'
    assert preview_image_url(html, 'https://x.com/shop/p') == (
        'https://x.com/img/a.jpg')


def test_preview_image_twitter():
    html = '<meta name="twitter:image" content="https://x.com/t.png">'
    assert preview_image_url(html, 'https://x.com') == 'https://x.com/t.png'


def test_preview_image_link_image_src():
    html = '<link rel="image_src" href="https://x.com/s.png">'
    assert preview_image_url(html, 'https://x.com') == 'https://x.com/s.png'


def test_preview_image_best_first():
    html = ('<meta name="twitter:image" content="https://x.com/t.png">'
            '<meta property="og:image" content="http://x.com/o.png">'
            '<meta property="og:image:secure_url" '
            'content="https://x.com/s.png">')
    assert preview_image_url(html, 'https://x.com') == 'https://x.com/s.png'


def test_preview_image_with_escaped_address():
    html = ('<meta property="og:image" '
            'content="https://x.com/a.jpg?w=1&amp;h=2">')
    assert preview_image_url(html, 'https://x.com') == (
        'https://x.com/a.jpg?w=1&h=2')


def test_preview_image_none():
    assert preview_image_url('<title>Nothing</title>', 'https://x.com') is None


def test_page_text_charset_from_the_header():
    assert page_text('ação'.encode('latin-1'),
                     'text/html; charset=ISO-8859-1') == 'ação'


def test_page_text_charset_from_the_page():
    data = '<meta charset="iso-8859-1"><p>ação'.encode('latin-1')
    assert page_text(data, 'text/html').endswith('ação')


def test_page_text_unknown_charset():
    assert page_text('ação'.encode('utf-8'), 'text/html; charset=nonsense') \
        == 'ação'


# Fetching

def test_fetch_the_picture(qtbot, tmpdir):
    image_url = picture(tmpdir)
    url = page(tmpdir, f'<meta property="og:image" content="{image_url}">')
    image, reason = fetch(qtbot, url)
    assert reason == ''
    assert (image.width(), image.height()) == (40, 20)


def test_fetch_a_page_without_a_picture(qtbot, tmpdir):
    image, reason = fetch(qtbot, page(tmpdir, '<title>Nothing</title>'))
    assert image.isNull()
    assert reason == 'The page offers no picture'


def test_fetch_a_picture_that_is_not_one(qtbot, tmpdir):
    path = os.path.join(str(tmpdir), 'broken.png')
    with open(path, 'wb') as f:
        f.write(b'not a picture')
    broken = QtCore.QUrl.fromLocalFile(path).toString()
    url = page(tmpdir, f'<meta property="og:image" content="{broken}">')
    image, reason = fetch(qtbot, url)
    assert image.isNull()
    assert reason == 'The picture could not be read'


def test_fetch_a_page_that_is_not_there(qtbot, tmpdir):
    missing = QtCore.QUrl.fromLocalFile(
        os.path.join(str(tmpdir), 'missing.html')).toString()
    image, reason = fetch(qtbot, missing)
    assert image.isNull()
    assert reason


def test_cancelled_fetch_says_nothing(qtbot, tmpdir):
    manager = QtNetwork.QNetworkAccessManager()
    preview = LinkPreview(page(tmpdir, '<title>x</title>'), manager)
    said = []
    preview.finished.connect(lambda *args: said.append(args))
    preview.start()
    preview.cancel()
    qtbot.wait(300)
    assert said == []


# Pasting

def test_paste_a_link_fetches_its_preview(view):
    with patch.object(view, 'paste_link') as paste_link:
        paste(view, 'https://example.com/chair')
    paste_link.assert_called_once()
    assert paste_link.call_args[0][:2] == (
        'https://example.com/chair', 'https://example.com/chair')


def test_paste_a_link_as_text_when_turned_off(view, settings):
    settings.setValue('Items/link_previews', False)
    with patch.object(view, 'paste_link') as paste_link:
        paste(view, 'https://example.com/chair')
    paste_link.assert_not_called()
    items = view.scene.items()
    assert len(items) == 1
    assert items[0].toPlainText() == 'https://example.com/chair'


def test_paste_words_with_a_link_as_text(view):
    with patch.object(view, 'paste_link') as paste_link:
        paste(view, 'see https://example.com/chair')
    paste_link.assert_not_called()
    assert view.scene.items()[0].toPlainText() == (
        'see https://example.com/chair')


def linked_page(tmpdir):
    image_url = picture(tmpdir)
    return page(tmpdir, f'<meta property="og:image" content="{image_url}">')


def pictures(view):
    return [item for item in view.scene.items()
            if isinstance(item, BeePixmapItem)]


def notes(view):
    return [item for item in view.scene.items()
            if isinstance(item, BeeTextItem)]


def test_the_link_is_on_the_board_at_once(view, tmpdir):
    url = linked_page(tmpdir)
    view.paste_link(url, url, QtCore.QPointF(10, 10))
    assert [note.toPlainText() for note in notes(view)] == [url]
    assert pictures(view) == []


def test_preview_takes_the_place_of_the_note(view, qtbot, tmpdir):
    url = linked_page(tmpdir)
    view.paste_link(url, url, QtCore.QPointF(10, 10))
    qtbot.waitUntil(lambda: bool(pictures(view)), timeout=10000)
    assert notes(view) == []
    assert pictures(view)[0].caption == url
    assert view.link_previews == []
    assert view.undo_stack.undoText() == 'Show link preview'


def test_undo_gives_the_note_back_then_takes_it_off(view, qtbot, tmpdir):
    url = linked_page(tmpdir)
    view.paste_link(url, url, QtCore.QPointF(10, 10))
    qtbot.waitUntil(lambda: bool(pictures(view)), timeout=10000)
    view.undo_stack.undo()
    assert pictures(view) == []
    assert [note.toPlainText() for note in notes(view)] == [url]
    view.undo_stack.undo()
    assert view.scene.items() == []
    view.undo_stack.redo()
    view.undo_stack.redo()
    assert len(pictures(view)) == 1
    assert notes(view) == []


def test_preview_goes_where_the_note_is_now(view, qtbot, tmpdir):
    url = linked_page(tmpdir)
    view.paste_link(url, url, QtCore.QPointF(10, 10))
    note = notes(view)[0]
    note.moveBy(300, 200)
    where = view.scene.itemsBoundingRect(items=[note]).center()
    qtbot.waitUntil(lambda: bool(pictures(view)), timeout=10000)
    # The picture itself, without the caption under it
    middle = view.scene.itemsBoundingRect(items=pictures(view)).center()
    assert middle.x() == pytest.approx(where.x(), abs=1)
    assert middle.y() == pytest.approx(where.y(), abs=1)


def test_a_note_written_in_is_left(view, qtbot, tmpdir):
    url = linked_page(tmpdir)
    view.paste_link(url, url, QtCore.QPointF(10, 10))
    note = notes(view)[0]
    note.setPlainText(url + ' the chair we liked')
    qtbot.waitUntil(lambda: view.link_previews == [], timeout=10000)
    assert pictures(view) == []
    assert notes(view) == [note]


def test_a_note_being_written_in_is_left(view, qtbot, tmpdir):
    url = linked_page(tmpdir)
    view.paste_link(url, url, QtCore.QPointF(10, 10))
    note = notes(view)[0]
    note.enter_edit_mode()
    qtbot.waitUntil(lambda: view.link_previews == [], timeout=10000)
    assert pictures(view) == []
    # Left writing, its cursor would go on blinking after the window
    # of this test has gone, looking for it
    note.exit_edit_mode(commit=False)


def test_a_note_undone_meanwhile_stays_gone(view, qtbot, tmpdir):
    url = linked_page(tmpdir)
    view.paste_link(url, url, QtCore.QPointF(10, 10))
    view.undo_stack.undo()
    qtbot.waitUntil(lambda: view.link_previews == [], timeout=10000)
    assert view.scene.items() == []


def test_what_else_is_selected_stays_selected(view, qtbot, tmpdir):
    url = linked_page(tmpdir)
    view.paste_link(url, url, QtCore.QPointF(10, 10))
    other = BeeTextItem('other')
    view.scene.addItem(other)
    view.scene.deselect_all_items()
    other.setSelected(True)
    qtbot.waitUntil(lambda: bool(pictures(view)), timeout=10000)
    assert other.isSelected()
    assert not pictures(view)[0].isSelected()


def test_no_preview_leaves_the_note(view, qtbot, tmpdir):
    url = page(tmpdir, '<title>Nothing</title>')
    view.paste_link(url, 'www.example.pt', QtCore.QPointF(10, 10))
    qtbot.waitUntil(lambda: view.link_previews == [], timeout=10000)
    assert [note.toPlainText() for note in notes(view)] == ['www.example.pt']
    assert view.undo_stack.count() == 1


def test_closing_the_board_forgets_previews_on_the_way(view, qtbot, tmpdir):
    url = linked_page(tmpdir)
    view.paste_link(url, url, QtCore.QPointF(10, 10))
    view.clear_scene()
    qtbot.wait(500)
    assert view.scene.items() == []
    assert view.link_previews == []
