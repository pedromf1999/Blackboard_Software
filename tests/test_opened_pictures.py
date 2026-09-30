"""Pictures kept compressed, and opened only as far as they are seen."""

import os
from unittest.mock import MagicMock, patch

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtTest import QTest

from beeref import fileio, imagecache
from beeref.items import BeePixmapItem


def picture(width=2000, height=1000):
    """A photograph-like picture: colours changing across it."""

    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    painter = QtGui.QPainter(image)
    gradient = QtGui.QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0, QtGui.QColor(200, 40, 40))
    gradient.setColorAt(1, QtGui.QColor(40, 40, 200))
    painter.fillRect(image.rect(), gradient)
    painter.end()
    return image


def compressed(image, fmt='JPG'):
    data = QtCore.QByteArray()
    buffer = QtCore.QBuffer(data)
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, fmt, quality=90)
    return data.data()


def read_from_file(image, fmt='JPG'):
    """An item as a board file gives it: from compressed bytes."""

    item = BeePixmapItem(QtGui.QImage())
    item.pixmap_from_bytes(compressed(image, fmt))
    return item


def painter_at(scale):
    painter = MagicMock()
    painter.combinedTransform.return_value = QtGui.QTransform.fromScale(
        scale, scale)
    painter.device.return_value.devicePixelRatioF.return_value = 1
    return painter


@pytest.fixture(autouse=True)
def empty_store():
    imagecache.opened_pictures().clear()
    yield
    imagecache.opened_pictures().pool.waitForDone()
    imagecache.opened_pictures().clear()


def test_a_picture_is_halved_as_far_as_it_is_seen(qapp):
    assert imagecache.level_for(2) == 0
    assert imagecache.level_for(1) == 0
    assert imagecache.level_for(0.6) == 0
    assert imagecache.level_for(0.5) == 1
    assert imagecache.level_for(0.3) == 1
    assert imagecache.level_for(0.2) == 2
    assert imagecache.level_for(0.1) == 3
    assert imagecache.level_size(QtCore.QSize(2001, 1000), 3) == (
        QtCore.QSize(251, 125))


def test_a_picture_opens_at_the_size_asked_for(qapp):
    data = compressed(picture())
    assert imagecache.image_size(data) == QtCore.QSize(2000, 1000)
    assert imagecache.image_format(data) == 'jpg'
    small = imagecache.open_image(data, QtCore.QSize(250, 125))
    assert small.size() == QtCore.QSize(250, 125)
    assert imagecache.open_image(data).size() == QtCore.QSize(2000, 1000)
    scaled = imagecache.open_image(picture(), QtCore.QSize(100, 50))
    assert scaled.size() == QtCore.QSize(100, 50)


def test_read_from_a_file_only_a_small_copy_is_opened(qapp):
    item = read_from_file(picture())

    assert item._source is None
    assert item._encoded is not None
    assert max(item._thumbnail.width(), item._thumbnail.height()) == (
        imagecache.THUMBNAIL_SIDE)
    assert item.image_size() == QtCore.QSize(2000, 1000)
    assert item.crop == QtCore.QRectF(0, 0, 2000, 1000)
    # Opened whole when asked for whole
    assert item.pixmap().size() == QtCore.QSize(2000, 1000)


def test_bytes_that_are_no_picture_make_no_picture(qapp):
    item = read_from_file(picture())
    item.pixmap_from_bytes(b'not a picture')

    assert item.is_null() is True
    assert item.image_size() == QtCore.QSize(0, 0)


def test_saved_again_it_is_the_same_bytes_untouched(qapp, settings):
    data = compressed(picture())
    item = BeePixmapItem(QtGui.QImage())
    item.pixmap_from_bytes(data)

    assert item.pixmap_to_bytes() == (data, 'jpg')
    # Asked for as something else, it is opened and stored that way
    settings.setValue('Items/image_storage_format', 'png')
    again, fmt = item.pixmap_to_bytes()
    assert fmt == 'png'
    assert imagecache.image_format(again) == 'png'


def test_a_cropped_or_grey_export_is_made_from_the_picture(qapp):
    item = read_from_file(picture())
    item.crop = QtCore.QRectF(0, 0, 500, 400)
    item.grayscale = True

    data, _ = item.pixmap_to_bytes(apply_grayscale=True, apply_crop=True)
    image = QtGui.QImage.fromData(data)
    assert image.size() == QtCore.QSize(500, 400)
    assert image.allGray() is True


def test_a_pasted_picture_is_let_go_once_it_is_stored(qapp):
    item = BeePixmapItem(picture())
    assert item._source is not None

    data, fmt = item.pixmap_to_bytes()
    item.stored_as(data, fmt)
    assert item._source is None
    assert item.pixmap_to_bytes() == (data, fmt)


def test_saving_a_board_lets_go_of_its_pasted_pictures(view, tmp_path):
    item = BeePixmapItem(picture())
    view.scene.addItem(item)
    filename = str(tmp_path / 'board.blk')

    fileio.save_bee(filename, view.scene, create_new=True)
    assert item._source is None
    assert item._encoded is not None

    view.scene.clear()
    fileio.load_bee(filename, view.scene)
    view.scene.add_queued_items()
    [opened] = view.scene.items_by_type('pixmap')
    assert opened._source is None
    assert opened.image_size() == QtCore.QSize(2000, 1000)
    # And written again as it was read, without being opened
    assert opened.pixmap_to_bytes()[0] == item._encoded


def test_pictures_brought_in_from_files_are_compressed_straight_away(
        view, tmp_path):
    path = str(tmp_path / 'photo.jpg')
    picture().save(path, quality=90)
    worker = MagicMock(canceled=False)

    fileio.load_images([path], QtCore.QPointF(0, 0), view.scene, worker)
    view.scene.add_queued_items()
    [item] = view.scene.items_by_type('pixmap')
    assert item._source is None
    assert item._encoded is not None
    assert item.image_size() == QtCore.QSize(2000, 1000)


def test_a_copy_shares_the_picture(qapp):
    item = read_from_file(picture())
    copy = item.create_copy()

    assert copy._encoded is item._encoded
    assert copy.image_size() == item.image_size()
    assert copy.image_key != item.image_key


def test_drawn_small_it_draws_the_small_copy(qapp):
    item = read_from_file(picture())
    painter = painter_at(0.05)
    item.paint(painter, None, None)

    drawn = painter.drawPixmap.call_args[0][1]
    assert drawn.size() == item._thumbnail.size()
    assert imagecache.opened_pictures().entries == {}


def test_a_picture_of_the_board_opens_it_straight_away(qapp):
    item = read_from_file(picture())
    painter = painter_at(0.3)
    # No window to draw in: an export, or a file's thumbnail
    item.paint(painter, None, None)

    drawn = painter.drawPixmap.call_args[0][1]
    assert drawn.size() == QtCore.QSize(1000, 500)
    assert item.painted == (item.image_key, 1, False)
    assert imagecache.opened(item.painted) is not None


def test_in_the_window_it_is_opened_in_the_background(view):
    item = read_from_file(picture())
    view.scene.addItem(item)
    painter = painter_at(0.3)
    item.paint(painter, None, view.viewport())

    # Meanwhile the small copy stands in
    assert painter.drawPixmap.call_args[0][1].size() == (
        item._thumbnail.size())
    store = imagecache.opened_pictures()
    store.pool.waitForDone()
    QTest.qWait(50)
    assert imagecache.opened((item.image_key, 1, False)) is not None

    item.paint(painter, None, view.viewport())
    assert painter.drawPixmap.call_args[0][1].size() == (
        QtCore.QSize(1000, 500))


def test_a_grey_picture_is_opened_grey(qapp):
    item = read_from_file(picture())
    item.grayscale = True
    painter = painter_at(0.3)
    item.paint(painter, None, None)

    drawn = painter.drawPixmap.call_args[0][1]
    assert drawn.toImage().allGray() is True


def test_the_store_lets_go_of_the_oldest_past_its_budget(qapp):
    store = imagecache.opened_pictures()
    image = picture(1000, 1000)
    # Four million bytes each, against a budget of six megabytes
    with patch('beeref.imagecache.BUDGET', 6 * 2 ** 20), \
            patch('beeref.imagecache.time.monotonic') as clock:
        clock.return_value = 100
        store.put((1, 0, False), image)
        store.put((2, 0, False), image)
        store.put((3, 0, False), image)
        # Over budget, but everything was seen a moment ago
        assert len(store.entries) == 3
        clock.return_value = 120
        store.get((3, 0, False))
        store.put((4, 0, False), image)

    # The oldest went; the two seen a moment ago stayed
    assert list(store.entries) == [(3, 0, False), (4, 0, False)]
    assert store.total == 2 * 1000 * 1000 * 4


def test_what_is_in_view_is_kept_and_the_rest_let_go(qapp):
    store = imagecache.opened_pictures()
    image = picture(100, 100)
    with patch('beeref.imagecache.time.monotonic') as clock:
        clock.return_value = 100
        store.put((1, 2, False), image)
        store.put((1, 3, False), image)
        store.put((2, 0, False), image)
        clock.return_value = 100 + imagecache.KEEP_SECONDS + 1
        store.trim({1: (1, 2, False)})

    assert list(store.entries) == [(1, 2, False)]
    assert store.best(1, False) is not None
    assert store.best(2, False) is None


def test_the_view_lets_go_of_pictures_out_of_sight(view):
    view.resize(800, 600)
    seen = read_from_file(picture())
    gone = read_from_file(picture())
    view.scene.addItem(seen)
    view.scene.addItem(gone)
    gone.setPos(100000, 100000)
    view.centerOn(seen)
    for item in (seen, gone):
        item.paint(painter_at(0.3), None, None)

    later = imagecache.time.monotonic() + imagecache.KEEP_SECONDS + 60
    with patch('beeref.imagecache.time.monotonic', return_value=later):
        view.trim_opened_pictures()
    assert imagecache.opened(seen.painted) is not None
    assert imagecache.opened(gone.painted) is None


def test_a_new_board_lets_go_of_everything(view):
    item = read_from_file(picture())
    item.paint(painter_at(0.3), None, None)
    view.clear_scene()

    assert imagecache.opened_pictures().entries == {}


def test_the_eyedropper_reads_what_is_on_screen(view):
    item = read_from_file(picture())
    view.scene.addItem(item)
    item.paint(painter_at(0.3), None, None)

    color = item.sample_color_at(QtCore.QPointF(10, 10))
    assert color.red() > 150
    assert color.blue() < 90


def test_a_changed_picture_forgets_what_was_opened_of_it(qapp):
    item = read_from_file(picture())
    item.paint(painter_at(0.3), None, None)
    name = item.painted

    item.setPixmap(QtGui.QPixmap.fromImage(picture(300, 300)))
    assert imagecache.opened(name) is None
    assert item.image_size() == QtCore.QSize(300, 300)


def test_png_pictures_keep_their_transparency(qapp):
    image = QtGui.QImage(600, 600, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor(0, 0, 0, 0))
    item = read_from_file(image, fmt='PNG')

    assert item.pixmap_to_bytes()[1] == 'png'
    assert item.full_image().hasAlphaChannel() is True
    assert os.path.splitext(
        item.get_filename_for_export('png', 1))[1] == '.png'


def test_copied_to_the_clipboard_it_goes_whole(qapp):
    item = read_from_file(picture())
    mimedata = QtCore.QMimeData()
    item.add_to_mimedata(mimedata)

    assert mimedata.imageData().size() == QtCore.QSize(2000, 1000)


def test_no_picture_draws_nothing_and_does_not_fail(qapp):
    item = BeePixmapItem(QtGui.QImage())
    item.paint(painter_at(0.3), None, None)
    assert isinstance(item.drawn_pixmap(), QtGui.QPixmap)
    assert QtWidgets.QApplication.instance() is not None
