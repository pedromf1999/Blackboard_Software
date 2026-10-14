"""The icon of the site a link's picture came from, in its corner."""

import os

from PyQt6 import QtCore, QtGui, QtNetwork
import pytest

from beeref import fileio
from beeref.items import BeePixmapItem
from beeref.link_preview import (
    icon_from, icon_urls, LinkPreview, read_page)


def square(color='red', side=40):
    image = QtGui.QImage(side, side, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor(color))
    return image


def picture_item(view, width=400, height=200):
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor('black'))
    item = BeePixmapItem(image)
    view.scene.addItem(item)
    return item


def file_url(tmpdir, name, data):
    path = os.path.join(str(tmpdir), name)
    with open(path, 'wb') as f:
        f.write(data)
    return QtCore.QUrl.fromLocalFile(path).toString()


def png(image):
    data = QtCore.QByteArray()
    buffer = QtCore.QBuffer(data)
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    return bytes(data)


def fetch(qtbot, url):
    preview = LinkPreview(url, QtNetwork.QNetworkAccessManager())
    result = {}
    preview.finished.connect(
        lambda image, icon, reason: result.update(
            image=image, icon=icon, reason=reason))
    preview.start()
    qtbot.waitUntil(lambda: bool(result), timeout=15000)
    return result['image'], result['icon'], result['reason']


# Which icon

def icons(*links):
    return read_page(''.join(links), 'https://x.com/page')[1]


def test_a_sharp_tab_icon_first():
    assert icons(
        '<link rel="icon" sizes="16x16" href="/16.png">',
        '<link rel="icon" sizes="96x96" href="/96.png">',
        '<link rel="apple-touch-icon" href="/apple.png">',
    )[0] == 'https://x.com/96.png'


def test_a_drawn_tab_icon_counts_as_sharp():
    assert icons(
        '<link rel="apple-touch-icon" href="/apple.png">',
        '<link rel="icon" type="image/svg+xml" href="/icon.svg">',
    )[0] == 'https://x.com/icon.svg'


def test_the_phone_icon_before_a_small_tab_icon():
    assert icons(
        '<link rel="shortcut icon" href="/favicon.png">',
        '<link rel="apple-touch-icon" sizes="180x180" href="/apple.png">',
    ) == ['https://x.com/apple.png', 'https://x.com/favicon.png',
          'https://x.com/favicon.ico']


def test_favicon_ico_when_the_page_names_none():
    assert icons('<title>x</title>') == ['https://x.com/favicon.ico']


def test_each_place_once():
    assert icon_urls(
        [('icon', '/favicon.ico', '', ''), ('icon', '/favicon.ico', '', '')],
        'https://x.com/') == ['https://x.com/favicon.ico']


# Reading an icon

def test_icon_from_a_png():
    assert icon_from(png(square(side=32))).width() == 32


def test_icon_from_an_ico_with_several_sizes(tmpdir):
    path = os.path.join(str(tmpdir), 'favicon.ico')
    writer = QtGui.QImageWriter(path, b'ico')
    assert writer.write(square(side=48))
    with open(path, 'rb') as f:
        assert icon_from(f.read()).width() == 48


def test_icon_from_a_drawing_is_read_large():
    svg = (b'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">'
           b'<rect width="32" height="32" fill="red"/></svg>')
    assert icon_from(svg).width() == 256


def test_icon_from_something_else():
    assert icon_from(b'<html>not an icon</html>').isNull()


# Fetching it with the picture

def test_fetch_brings_the_icon(qtbot, tmpdir):
    picture = file_url(tmpdir, 'p.png', png(square('orange', 60)))
    icon = file_url(tmpdir, 'i.png', png(square('blue', 32)))
    page = file_url(tmpdir, 'page.html', (
        f'<meta property="og:image" content="{picture}">'
        f'<link rel="icon" href="{icon}">').encode())
    image, got, reason = fetch(qtbot, page)
    assert reason == ''
    assert image.width() == 60
    assert got.width() == 32


def test_fetch_tries_the_next_icon(qtbot, tmpdir):
    """A site's own address for its icon is sometimes wrong: one
    answered with a web page instead."""

    picture = file_url(tmpdir, 'p.png', png(square('orange', 60)))
    broken = file_url(tmpdir, 'broken.svg', b'<html>oops</html>')
    good = file_url(tmpdir, 'good.png', png(square('blue', 24)))
    page = file_url(tmpdir, 'page.html', (
        f'<meta property="og:image" content="{picture}">'
        f'<link rel="icon" type="image/svg+xml" href="{broken}">'
        f'<link rel="apple-touch-icon" href="{good}">').encode())
    image, got, reason = fetch(qtbot, page)
    assert got.width() == 24


def test_fetch_without_an_icon_still_brings_the_picture(qtbot, tmpdir):
    picture = file_url(tmpdir, 'p.png', png(square('orange', 60)))
    missing = QtCore.QUrl.fromLocalFile(
        os.path.join(str(tmpdir), 'missing.png')).toString()
    page = file_url(tmpdir, 'page.html', (
        f'<meta property="og:image" content="{picture}">'
        f'<link rel="icon" href="{missing}">').encode())
    image, got, reason = fetch(qtbot, page)
    assert image.width() == 60
    assert got.isNull()
    assert reason == ''


# On the picture

def test_no_icon_at_first(view):
    item = picture_item(view)
    assert item.link_icon.isNull()
    assert item.link_icon_rect() is None
    assert 'link_icon' not in item.get_extra_save_data()


def test_a_big_icon_is_kept_small(view):
    item = picture_item(view)
    item.link_icon = square(side=512)
    assert item.link_icon.width() == BeePixmapItem.LINK_ICON_KEPT


def test_the_icon_sits_in_the_top_left_corner(view):
    item = picture_item(view, 400, 200)
    item.link_icon = square()
    tile = item.link_icon_rect()
    assert tile.left() == pytest.approx(200 * item.LINK_ICON_INSET_FRACTION)
    assert tile.top() == pytest.approx(200 * item.LINK_ICON_INSET_FRACTION)
    assert tile.width() == pytest.approx(200 * item.LINK_ICON_FRACTION)


def test_the_icon_follows_a_crop(view):
    item = picture_item(view, 400, 200)
    item.link_icon = square()
    item.crop = QtCore.QRectF(100, 50, 200, 100)
    tile = item.link_icon_rect()
    assert tile.left() > 100
    assert tile.top() > 50


def render(view, item):
    rect = item.sceneBoundingRect()
    image = QtGui.QImage(int(rect.width()), int(rect.height()),
                         QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor('grey'))
    painter = QtGui.QPainter(image)
    view.scene.render(painter, QtCore.QRectF(image.rect()), rect)
    painter.end()
    return image


def test_the_icon_is_drawn(view):
    item = picture_item(view, 400, 200)
    item.link_icon = square('blue')
    image = render(view, item)
    # The middle of the tile is the icon, blue on the black picture
    tile = item.link_icon_rect()
    assert image.pixelColor(int(tile.center().x()),
                            int(tile.center().y())).blue() > 200


def test_a_flipped_picture_keeps_its_icon_top_left(view):
    """Never mirrored: still where a reader looks first."""

    item = picture_item(view, 400, 200)
    half = QtGui.QImage(40, 40, QtGui.QImage.Format.Format_ARGB32)
    half.fill(QtGui.QColor('blue'))
    for x in range(20, 40):
        for y in range(40):
            half.setPixelColor(x, y, QtGui.QColor('red'))
    item.link_icon = half
    item.do_flip()
    image = render(view, item)
    tile = item.link_icon_rect()
    left = image.pixelColor(int(tile.center().x() - tile.width() / 5),
                            int(tile.center().y()))
    right = image.pixelColor(int(tile.center().x() + tile.width() / 5),
                             int(tile.center().y()))
    assert left.blue() > 200
    assert right.red() > 200


def test_a_copy_has_the_icon(view):
    item = picture_item(view)
    item.link_icon = square()
    assert item.create_copy().link_icon.width() == 40


def test_the_icon_is_saved_and_read_back(view, tmpdir):
    item = picture_item(view)
    item.caption = 'https://x.com'
    item.link_icon = square('blue', 48)
    path = os.path.join(str(tmpdir), 'icon.blk')
    fileio.save_bee(path, view.scene, create_new=True)
    view.scene.clear()
    fileio.load_bee(path, view.scene)
    view.scene.add_queued_items()
    back = list(view.scene.items_by_type('pixmap'))[0]
    assert back.link_icon.width() == 48
    assert back.link_icon.pixelColor(10, 10) == QtGui.QColor('blue')


def test_a_picture_saved_before_icons_has_none(view):
    clone = picture_item(view)
    BeePixmapItem.create_from_data(item=clone, data={'caption': 'x'})
    assert clone.link_icon.isNull()
