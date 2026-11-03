"""A link shown as a card: the square middle of its picture, and beside
it what the page is called and its address, as a list of saved links
shows them."""

import json
import os

from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets
import pytest

from beeref import commands, link_preview
from beeref.items import BeePixmapItem, BeeTextItem
from beeref.link_preview import (
    clean_title, file_title, LinkPreview, read_page, short_address,
    site_name)
from tests.test_link_pdf import LocalServer


URL = 'https://pt.misumi-ec.com/vona2/detail/110300014930/'


def card(view=None, size=(300, 200), url=URL, title='Pinos de posicionamento',
         color='red', as_card=True, selected=True):
    image = QtGui.QImage(*size, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor(color))
    item = BeePixmapItem(image)
    item.caption = url
    item.link_title = title
    item.link_card = as_card
    if view is not None:
        view.scene.addItem(item)
        item.setSelected(selected)
    return item


# The title, from the page

def page(head):
    return f'<html><head>{head}</head><body>Hello</body></html>'


def test_the_title_offered_for_links_comes_first():
    html = page('<title>MISUMI | Pinos | Comprar online</title>'
                '<meta property="og:title" content="Pinos de posicionamento">')
    assert read_page(html, URL)[2] == 'Pinos de posicionamento'


def test_twitter_title_when_there_is_no_open_graph_one():
    html = page('<title>Shop</title>'
                '<meta name="twitter:title" content="Dobradiça inox">')
    assert read_page(html, URL)[2] == 'Dobradiça inox'


def test_the_page_title_otherwise_on_one_line():
    html = page('<title>\n  Cadeira   ODGER &amp; braços\n</title>')
    assert read_page(html, URL)[2] == 'Cadeira ODGER & braços'


def test_only_the_first_title_in_the_page():
    html = page('<title>The page</title>'
                '<svg><title>An icon</title></svg>')
    assert read_page(html, URL)[2] == 'The page'


def test_no_title_at_all():
    assert read_page(page('<meta charset="utf-8">'), URL)[2] == ''


def test_a_title_too_long_is_cut_short():
    title = clean_title('word ' * 200)
    assert len(title) <= link_preview.MAX_TITLE + 1
    assert title.endswith('…')


def test_the_site_and_the_address_as_a_card_shows_them():
    assert site_name('https://www.ikea.com/pt/pt/p/odger') == 'ikea.com'
    assert site_name('not a link') == ''
    assert short_address('https://www.youtube.com/watch?v=abc') == (
        'youtube.com/watch?v=abc')
    assert short_address('http://example.com/') == 'example.com'
    assert file_title('https://www.ti.com/lit/ds/lm317%20v2.pdf') == (
        'lm317 v2.pdf')


def fetch(qtbot, url):
    preview = LinkPreview(url, QtNetwork.QNetworkAccessManager())
    result = {}
    preview.finished.connect(lambda image, icon, reason: result.update(
        image=image, reason=reason))
    preview.start()
    qtbot.waitUntil(lambda: bool(result), timeout=10000)
    return preview, result


def local(tmpdir, name):
    return QtCore.QUrl.fromLocalFile(os.path.join(str(tmpdir), name))


def picture_file(tmpdir, name='picture.png'):
    image = QtGui.QImage(40, 20, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('orange'))
    image.save(os.path.join(str(tmpdir), name))
    return local(tmpdir, name).toString()


def test_a_page_brings_its_title_with_its_picture(qtbot, tmpdir):
    with open(os.path.join(str(tmpdir), 'page.html'), 'w',
              encoding='utf-8') as f:
        f.write(page(f'<meta property="og:image" '
                     f'content="{picture_file(tmpdir)}">'
                     '<title>Cadeira ODGER</title>'))
    preview, result = fetch(qtbot, local(tmpdir, 'page.html').toString())
    assert result['reason'] == ''
    assert preview.title == 'Cadeira ODGER'


def test_a_picture_linked_to_is_called_by_its_file(qtbot, tmpdir):
    data = QtCore.QByteArray()
    buffer = QtCore.QBuffer(data)
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image = QtGui.QImage(40, 20, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('orange'))
    image.save(buffer, 'PNG')
    server = LocalServer('image/png', bytes(data))
    preview, result = fetch(qtbot, server.url('/photos/chair-oak.png'))
    assert not result['image'].isNull()
    assert preview.title == 'chair-oak.png'


def make_pdf(path, title=''):
    writer = QtGui.QPdfWriter(path)
    writer.setTitle(title)
    painter = QtGui.QPainter(writer)
    painter.fillRect(QtCore.QRect(200, 300, 195, 240), QtGui.QColor('red'))
    painter.end()


def test_a_pdf_is_called_by_its_own_title(qtbot, tmpdir):
    make_pdf(os.path.join(str(tmpdir), 'lm317.pdf'), 'LM317 datasheet')
    preview, result = fetch(qtbot, local(tmpdir, 'lm317.pdf').toString())
    assert not result['image'].isNull()
    assert preview.title == 'LM317 datasheet'


def test_a_pdf_without_a_title_by_its_file(qtbot, tmpdir):
    make_pdf(os.path.join(str(tmpdir), 'lm317.pdf'))
    preview, result = fetch(qtbot, local(tmpdir, 'lm317.pdf').toString())
    assert preview.title == 'lm317.pdf'


def test_a_grabcad_model_is_called_by_its_name(qtbot, tmpdir, monkeypatch):
    folder = local(tmpdir, '').toString().rstrip('/')
    monkeypatch.setattr(link_preview, 'GRABCAD_API', folder + '/{}.json')
    with open(os.path.join(str(tmpdir), 'vice-1.json'), 'w') as f:
        json.dump({'preview_image': picture_file(tmpdir),
                   'name': 'Machine vice 80 mm'}, f)
    preview, result = fetch(qtbot, 'https://grabcad.com/library/vice-1')
    assert preview.title == 'Machine vice 80 mm'


# What the card looks like and how it behaves

def test_the_card_is_the_square_and_the_band_beside_it():
    item = card(size=(300, 200))
    square = item.card_picture_rect()
    assert square == QtCore.QRectF(50, 0, 200, 200)
    ratio = item.CARD_BAND_RATIO
    assert item.bounding_rect_unselected() == QtCore.QRectF(
        50, 0, 200 * (1 + ratio), 200)
    assert item.framed_rect() == item.bounding_rect_unselected()
    assert item.pin_rect() == item.bounding_rect_unselected()


def test_cards_the_same_height_are_the_same_width():
    wide = card(size=(900, 300))
    tall = card(size=(300, 900))
    assert wide.card_rect().size() == tall.card_rect().size()


def test_the_square_is_taken_from_what_the_crop_leaves():
    item = card(size=(300, 200))
    item.crop = QtCore.QRectF(0, 0, 100, 150)
    assert item.card_picture_rect() == QtCore.QRectF(0, 25, 100, 100)


def test_the_whole_picture_while_it_is_cropped():
    item = card(size=(300, 200))
    item.crop_mode = True
    assert not item.shows_card()
    assert item.bounding_rect_unselected().width() > 300


def test_a_card_has_no_caption_band_under_it():
    item = card()
    assert not item.shows_caption()
    assert item.caption_height() == 0
    item.link_card = False
    assert item.shows_caption()


def test_ctrl_clicking_anywhere_on_the_card_is_the_link():
    item = card(size=(300, 200))
    assert item.caption_url_at(QtCore.QPointF(60, 10)) == URL
    assert item.caption_url_at(QtCore.QPointF(600, 190)) == URL
    assert item.caption_url_at(QtCore.QPointF(10, 10)) is None


def test_a_card_has_no_caption_to_write():
    item = card()
    item.enter_caption_edit_mode()
    assert item.caption_editor is None
    assert not item.caption_editing


def test_without_a_title_the_card_is_called_by_its_site():
    item = card(title='', url='https://www.ikea.com/pt/pt/p/odger-80359955/')
    assert item.card_title() == 'ikea.com'


def test_its_title_is_found_and_named():
    item = card()
    assert 'Pinos de posicionamento' in item.search_text()
    assert URL in item.search_text()
    assert item.get_default_name() == 'Pinos de posicionamento'
    assert item.pin_label_text() == 'Pinos de posicionamento'
    assert item.text_for_other_programs() == (
        f'Pinos de posicionamento\n\n{URL}')


def test_a_picture_without_a_title_reads_as_it_did():
    item = card(title='', as_card=False)
    assert item.search_text() == URL
    assert item.text_for_other_programs() == URL
    assert item.get_default_name() == 'Image'


def drawn(item, size=(800, 200)):
    """The card painted at its own size, on black."""

    image = QtGui.QImage(*size, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('black'))
    painter = QtGui.QPainter(image)
    rect = item.bounding_rect_unselected()
    painter.translate(-rect.left(), -rect.top())
    if item.flip() == -1:
        painter.translate(rect.left() + rect.right(), 0)
        painter.scale(-1, 1)
    item.paint(painter, QtWidgets.QStyleOptionGraphicsItem(), None)
    painter.end()
    return image


def test_the_picture_is_on_the_left_and_the_band_on_the_right(view):
    item = card(view, size=(300, 200), selected=False)
    image = drawn(item)
    assert image.pixelColor(100, 100) == QtGui.QColor('red')
    assert image.pixelColor(700, 190) == item.caption_color


def test_the_title_is_written_in_the_band(view):
    item = card(view, size=(300, 200), selected=False)
    image = drawn(item)
    band = image.copy(200, 0, 600, 200)
    light = sum(1 for x in range(0, 600, 2) for y in range(0, 200, 2)
                if band.pixelColor(x, y).lightness() > 200)
    assert light > 50


def test_a_flipped_card_keeps_its_words_readable(view):
    """The picture goes to the other side, the words do not mirror:
    the same title painted flipped reads the same left to right."""

    item = card(view, size=(300, 200), selected=False)
    plain = drawn(item)
    item.do_flip()
    flipped = drawn(item)
    assert flipped.pixelColor(700, 100) == QtGui.QColor('red')
    # The first light pixel of the title, from the band's left edge:
    # where the words start, which a mirror would put at the far end

    def first_light(image, left, right):
        for x in range(left, right):
            for y in range(20, 180):
                if image.pixelColor(x, y).lightness() > 200:
                    return x - left
        return None

    assert first_light(plain, 200, 800) == pytest.approx(
        first_light(flipped, 0, 600), abs=3)


# Saved and opened again

def test_saved_with_the_card_and_the_title():
    data = card().get_extra_save_data()
    assert data['link_card'] is True
    assert data['link_title'] == 'Pinos de posicionamento'


def test_a_picture_that_is_not_a_card_saves_as_before():
    data = card(title='', as_card=False).get_extra_save_data()
    assert 'link_card' not in data
    assert 'link_title' not in data


def test_opened_again_as_a_card():
    data = card().get_extra_save_data()
    item = BeePixmapItem.create_from_data(item=card(as_card=False, title=''),
                                          data=data)
    assert item.link_card
    assert item.link_title == 'Pinos de posicionamento'


def test_a_board_from_before_opens_its_links_as_pictures():
    data = card(title='', as_card=False).get_extra_save_data()
    item = BeePixmapItem.create_from_data(item=card(as_card=False, title=''),
                                          data=data)
    assert not item.link_card
    assert item.link_title == ''


def test_a_copy_is_a_card_too(view):
    item = card(view)
    copy = item.create_copy()
    assert copy.link_card
    assert copy.link_title == item.link_title


def test_through_a_file_and_back(view, tmpdir):
    item = card(view, selected=False)
    item.setPos(40, 60)
    path = os.path.join(str(tmpdir), 'cards.blk')
    view.do_save(path, create_new=True)
    view.worker.wait()
    QtWidgets.QApplication.processEvents()
    view.undo_stack.setClean()
    view.clear_scene()
    view.open_from_file(path)
    view.worker.wait()
    QtWidgets.QApplication.processEvents()
    items = [i for i in view.scene.items() if isinstance(i, BeePixmapItem)]
    assert len(items) == 1
    assert items[0].link_card
    assert items[0].link_title == 'Pinos de posicionamento'


# Pasted, and switched between card and picture

def pictures(view):
    return [item for item in view.scene.items()
            if isinstance(item, BeePixmapItem)]


def test_a_pasted_link_comes_in_as_a_card(view, qtbot, tmpdir):
    with open(os.path.join(str(tmpdir), 'page.html'), 'w',
              encoding='utf-8') as f:
        f.write(page(f'<meta property="og:image" '
                     f'content="{picture_file(tmpdir)}">'
                     '<title>Cadeira ODGER</title>'))
    url = local(tmpdir, 'page.html').toString()
    view.paste_link(url, url, QtCore.QPointF(10, 10))
    qtbot.waitUntil(lambda: bool(pictures(view)), timeout=10000)
    item = pictures(view)[0]
    assert item.link_card
    assert item.link_title == 'Cadeira ODGER'
    height = item.mapRectToScene(item.card_rect()).height()
    assert height * view.get_scale() == pytest.approx(view.NEW_CARD_HEIGHT)


def test_a_card_opens_into_its_whole_picture(view):
    item = card(view, size=(300, 200))
    corner = item.mapToScene(item.bounding_rect_unselected().topLeft())
    view.on_action_link_as_picture()
    assert not item.link_card
    assert view.undo_stack.undoText() == 'Show link as picture'
    assert item.scale() == pytest.approx(view.picture_scale(item))
    # From where the card was
    moved = item.mapToScene(item.bounding_rect_unselected().topLeft())
    assert moved.x() == pytest.approx(corner.x())
    assert moved.y() == pytest.approx(corner.y())


def test_and_back_into_a_card(view):
    item = card(view, as_card=False)
    view.on_action_link_as_card()
    assert item.link_card
    assert view.undo_stack.undoText() == 'Show link as card'
    height = item.mapRectToScene(item.card_rect()).height()
    assert height * view.get_scale() == pytest.approx(view.NEW_CARD_HEIGHT)


def test_undo_puts_back_the_card_where_it_was(view):
    item = card(view)
    item.setPos(30, 40)
    item.setScale(0.5)
    view.on_action_link_as_picture()
    view.undo_stack.undo()
    assert item.link_card
    assert item.scale() == 0.5
    assert item.pos() == QtCore.QPointF(30, 40)


def test_redo_does_what_was_done_whatever_the_zoom_now(view):
    item = card(view)
    view.on_action_link_as_picture()
    scale = item.scale()
    view.undo_stack.undo()
    view.scale(3, 3)
    view.undo_stack.redo()
    assert item.scale() == scale


def test_the_button_makes_cards_of_them_all_unless_they_all_are(view):
    first = card(view)
    second = card(view, as_card=False)
    view.on_action_link_card()
    assert first.link_card and second.link_card
    assert view.undo_stack.count() == 1
    view.on_action_link_card()
    assert not first.link_card and not second.link_card


def test_a_picture_that_is_not_a_link_is_left(view):
    item = card(view, url='Our chair, in oak', as_card=False)
    view.on_action_link_as_card()
    assert not item.link_card
    assert view.undo_stack.count() == 0


def test_the_command_alone_keeps_the_corner():
    item = card(as_card=False)
    corner = item.mapToParent(item.bounding_rect_unselected().topLeft())
    command = commands.ShowLinkAsCard([item], True, lambda item: 0.25)
    command.redo()
    moved = item.mapToParent(item.bounding_rect_unselected().topLeft())
    assert item.scale() == 0.25
    assert moved.x() == pytest.approx(corner.x())
    assert moved.y() == pytest.approx(corner.y())


def test_the_buttons_say_what_a_press_would_do(view):
    item = card(view)
    view.update_image_toolbar()
    toolbar = view.image_toolbar
    assert not toolbar.as_card.isHidden()
    assert toolbar.as_card.isChecked()
    assert toolbar.as_card.toolTip() == 'Show the whole picture'
    assert not toolbar.caption.isEnabled()
    item.link_card = False
    view.update_image_toolbar()
    assert not toolbar.as_card.isChecked()
    assert toolbar.as_card.toolTip() == 'Show as a card'
    assert toolbar.caption.isEnabled()


def test_no_card_button_on_a_picture_that_is_not_a_link(view):
    card(view, url='', as_card=False)
    view.update_image_toolbar()
    assert view.image_toolbar.as_card.isHidden()


def test_a_card_goes_back_to_a_note_like_the_picture_did(view):
    card(view)
    view.on_action_link_as_text()
    notes = [item for item in view.scene.items()
             if isinstance(item, BeeTextItem)]
    assert [note.toPlainText() for note in notes] == [URL]
