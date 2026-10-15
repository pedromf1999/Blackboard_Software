"""Google Images links, and pictures copied as their own address."""

import base64
import os
from unittest.mock import patch

from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets
import pytest

from beeref import link_preview
from beeref.items import BeePixmapItem, BeeTextItem
from beeref.link_preview import google_image, image_in, LinkPreview


IMGRES = ('https://www.google.com/imgres?imgurl=https%3A%2F%2Fexample.com'
          '%2Fchair.jpg&imgrefurl=https%3A%2F%2Fexample.com%2Fchairs'
          '&tbnid=abc&docid=xyz')


def test_a_google_images_link():
    assert google_image(IMGRES) == ('https://example.com/chair.jpg',
                                    'https://example.com/chairs')


def test_a_google_images_link_on_another_google():
    assert google_image(IMGRES.replace('google.com', 'google.pt'))[0] == (
        'https://example.com/chair.jpg')


def test_a_google_images_link_without_its_page():
    url = 'https://www.google.com/imgres?imgurl=https://example.com/a.png'
    assert google_image(url) == ('https://example.com/a.png', None)


@pytest.mark.parametrize('url', [
    'https://www.google.com/search?q=chair&udm=2',
    'https://www.google.com/imgres?imgrefurl=https://example.com',
    'https://www.google.com/imgres?imgurl=javascript:alert(1)',
    'https://example.com/imgres?imgurl=https://example.com/a.png',
    'https://notgoogle.com/imgres?imgurl=https://example.com/a.png',
])
def test_not_a_google_images_link(url):
    assert google_image(url) is None


def jpeg_data_url(width=30, height=20):
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('red'))
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'JPEG')
    return 'data:image/jpeg;base64,' + base64.b64encode(
        bytes(buffer.data())).decode()


def test_a_picture_written_as_its_address():
    assert image_in(jpeg_data_url()).width() == 30


def test_a_picture_address_broken_over_lines():
    url = jpeg_data_url()
    head, tail = url[:60], url[60:]
    assert image_in(head + '\n' + tail).width() == 30


@pytest.mark.parametrize('text', [
    '', None, 'hello', 'data:image/png;base64,!!!',
    'data:text/plain;base64,aGVsbG8=', 'data:image/png;base64,aGVsbG8='])
def test_not_a_picture_address(text):
    assert image_in(text).isNull()


class Clipboard:
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


def test_pasting_a_picture_address_pastes_the_picture(view):
    paste(view, jpeg_data_url(40, 20))
    items = view.scene.items()
    assert len(items) == 1
    assert isinstance(items[0], BeePixmapItem)
    assert items[0].image_size().width() == 40
    assert view.undo_stack.undoText() == 'Paste image'


def test_pasting_other_text_still_makes_a_note(view):
    paste(view, 'data: not a picture')
    assert isinstance(view.scene.items()[0], BeeTextItem)


def png_url(tmpdir, name='chair.png'):
    image = QtGui.QImage(64, 48, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('orange'))
    path = os.path.join(str(tmpdir), name)
    image.save(path)
    return QtCore.QUrl.fromLocalFile(path).toString()


def fetch(qtbot, preview):
    result = {}
    preview.finished.connect(lambda image, icon, reason: result.update(
        image=image, icon=icon, reason=reason))
    preview.start()
    qtbot.waitUntil(lambda: bool(result), timeout=10000)
    return result['image'], result['icon'], result['reason']


def test_the_picture_is_fetched_without_the_google_page(qtbot, tmpdir,
                                                        monkeypatch):
    picture = png_url(tmpdir)
    monkeypatch.setattr(link_preview, 'google_image',
                        lambda url: (picture, None))
    preview = LinkPreview(IMGRES, QtNetwork.QNetworkAccessManager())
    image, icon, reason = fetch(qtbot, preview)
    assert reason == ''
    assert image.width() == 64
    assert preview.caption == IMGRES


def test_the_caption_is_the_page_the_picture_is_on(qtbot):
    asked = []

    def request(self, url, then, limit, timeout):
        asked.append(url)

    with patch.object(LinkPreview, 'request', request):
        preview = LinkPreview(IMGRES, QtNetwork.QNetworkAccessManager())
        preview.start()
    assert preview.caption == 'https://example.com/chairs'
    assert asked == ['https://example.com/chair.jpg',
                     'https://example.com/favicon.ico']


def test_the_preview_takes_its_caption(view, qtbot, tmpdir, monkeypatch):
    picture = png_url(tmpdir)
    monkeypatch.setattr(link_preview, 'google_image',
                        lambda url: (picture, None))
    view.paste_link(IMGRES, IMGRES, QtCore.QPointF(0, 0))
    qtbot.waitUntil(
        lambda: any(isinstance(item, BeePixmapItem)
                    for item in view.scene.items()), timeout=10000)
    picture_item = [item for item in view.scene.items()
                    if isinstance(item, BeePixmapItem)][0]
    assert picture_item.caption == IMGRES
