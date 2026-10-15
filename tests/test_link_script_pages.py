"""Pages built by script in the browser: the product's picture from the
data they are built from, and GrabCAD's models from GrabCAD itself."""

import json
import os

from PyQt6 import QtCore, QtGui, QtNetwork
import pytest

from beeref import link_preview
from beeref.link_preview import (
    embedded_image, grabcad_model, LinkPreview, read_page)


PAGE = 'https://pt.misumi-ec.com/vona2/detail/221000091791/'


def next_data(data):
    return ('<script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(data) + '</script>')


MISUMI = {'props': {'pageProps': {
    'seriesResponse': {
        'productImageList': [
            {'url': '//uk.misumi-ec.com/linked/material/PHOTO/THK1.jpg'}],
        'specValueList': [
            {'specValueImageUrl': '//uk.misumi-ec.com/illustration/w1.jpg'}],
    },
    'partNumberResponse': {'partNumberSpecList': [
        {'specImageUrl': '//uk.misumi-ec.com/illustration/M0104.png'}]},
    'config': {'cdn': {'images': 'https://images.misumi-ec.com/x.png'}},
}}}


def test_the_product_photo_in_the_data_of_the_page():
    pictures = read_page(next_data(MISUMI), PAGE)[0]
    assert pictures[0] == (
        'https://uk.misumi-ec.com/linked/material/PHOTO/THK1.jpg')


def test_drawings_of_sizes_are_not_the_product():
    data = {'specValueList': [{'specValueImageUrl': '/a.jpg'}],
            'specImageUrl': '/b.png'}
    assert embedded_image([json.dumps(data)], PAGE) is None


@pytest.mark.parametrize('data', [
    {'logoImage': '/logo.png'},
    {'avatarImage': '/me.jpg'},
    {'productIcon': '/icon.png'},
    {'name': 'not a picture'},
    {'productImage': 'relative/without/slash.jpg'},
])
def test_no_product_picture_in_the_data(data):
    assert embedded_image([json.dumps(data)], PAGE) is None


def test_an_image_not_said_to_be_the_product_will_do():
    data = {'item': {'mainImage': 'https://cdn.example/main.webp'}}
    assert embedded_image([json.dumps(data)], PAGE) == (
        'https://cdn.example/main.webp')


def test_product_and_image_before_image_alone():
    data = {'heroImage': 'https://cdn.example/hero.jpg',
            'product': {'images': ['https://cdn.example/product.jpg']}}
    assert embedded_image([json.dumps(data)], PAGE) == (
        'https://cdn.example/product.jpg')


def test_data_that_is_not_json_is_passed_by():
    assert embedded_image(['{not json'], PAGE) is None


def test_other_json_in_the_page_is_read_too():
    html = ('<script type="application/json">'
            '{"productImage": "https://cdn.example/p.png"}</script>')
    assert read_page(html, 'https://shop.example/')[0][0] == (
        'https://cdn.example/p.png')


# GrabCAD

@pytest.mark.parametrize('url,model', [
    ('https://grabcad.com/library/sagop-rp80-200x300-vice-1',
     'sagop-rp80-200x300-vice-1'),
    ('https://grabcad.com/library/vice-1/', 'vice-1'),
    ('https://www.grabcad.com/library/vice-1', 'vice-1'),
    ('https://grabcad.com/library', None),
    ('https://grabcad.com/library/vice-1/files', None),
    ('https://grabcad.com/dashboard', None),
    ('https://example.com/library/vice-1', None),
])
def test_grabcad_model(url, model):
    assert grabcad_model(url) == model


def picture_file(folder, name, color, size):
    image = QtGui.QImage(*size, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor(color))
    path = os.path.join(folder, name)
    image.save(path)
    return QtCore.QUrl.fromLocalFile(path).toString()


def fetch(qtbot, url):
    preview = LinkPreview(url, QtNetwork.QNetworkAccessManager())
    result = {}
    preview.finished.connect(lambda image, icon, reason: result.update(
        image=image, icon=icon, reason=reason))
    preview.start()
    qtbot.waitUntil(lambda: bool(result), timeout=10000)
    return result['image'], result['icon'], result['reason']


@pytest.fixture
def grabcad_here(tmpdir, monkeypatch):
    """GrabCAD's answers, as files: the tests need no network."""

    folder = str(tmpdir)
    monkeypatch.setattr(
        link_preview, 'GRABCAD_API',
        QtCore.QUrl.fromLocalFile(folder).toString() + '/{}.json')
    return folder


def answer(folder, model, data):
    with open(os.path.join(folder, f'{model}.json'), 'w') as f:
        json.dump(data, f)


def test_a_grabcad_model_comes_with_its_larger_picture(qtbot, grabcad_here):
    os.makedirs(os.path.join(grabcad_here, 'pics'))
    card = picture_file(grabcad_here, 'pics/card.jpg', 'blue', (40, 30))
    picture_file(grabcad_here, 'pics/large.jpg', 'red', (96, 54))
    answer(grabcad_here, 'vice-1', {'preview_image': card})
    image, icon, reason = fetch(qtbot, 'https://grabcad.com/library/vice-1')
    assert reason == ''
    assert image.width() == 96


def test_a_grabcad_model_without_a_larger_picture(qtbot, grabcad_here):
    os.makedirs(os.path.join(grabcad_here, 'pics'))
    card = picture_file(grabcad_here, 'pics/card.jpg', 'blue', (40, 30))
    answer(grabcad_here, 'vice-1', {'preview_image': card})
    image, icon, reason = fetch(qtbot, 'https://grabcad.com/library/vice-1')
    assert image.width() == 40


def test_a_grabcad_model_without_a_picture_reads_the_page(qtbot,
                                                          grabcad_here):
    answer(grabcad_here, 'vice-1', {
        'preview_image': 'https://grabcad.com/screenshots/pics/'
                         'missing_small.png'})
    asked = []
    original = LinkPreview.request

    def request(self, url, then, limit, timeout):
        asked.append(url)
        if url.startswith('https://'):
            QtCore.QTimer.singleShot(
                0, lambda: self.finish(QtGui.QImage(), 'no page here'))
            return
        original(self, url, then, limit, timeout)

    monkey = pytest.MonkeyPatch()
    monkey.setattr(LinkPreview, 'request', request)
    try:
        fetch(qtbot, 'https://grabcad.com/library/vice-1')
    finally:
        monkey.undo()
    assert asked[-1] == 'https://grabcad.com/library/vice-1'
