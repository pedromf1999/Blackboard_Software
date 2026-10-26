"""A PDF brought in as a picture comes in on white, as on paper, rather
than see-through where nothing is printed, and with twice the detail
Qt's reader gives."""

import os

from PyQt6 import QtCore, QtGui

from beeref import imagecache
from beeref.fileio import picture_from


def drawing_pdf(path):
    """A page with one black line on it and nothing else."""

    writer = QtGui.QPdfWriter(path)
    writer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A6))
    painter = QtGui.QPainter(writer)
    painter.setPen(QtGui.QPen(QtGui.QColor('black'), 20))
    painter.drawLine(100, 100, 800, 100)
    painter.end()
    return path


def dropped(source):
    item, _ = picture_from(source, QtCore.QPointF(0, 0), None)
    return item


def see_through(img):
    return sum(1 for x in range(0, img.width(), 10)
               for y in range(0, img.height(), 10)
               if img.pixelColor(x, y).alpha() < 255)


def test_a_dropped_pdf_comes_in_on_white(qapp, tmpdir):
    img = dropped(drawing_pdf(os.path.join(tmpdir, 'drawing.pdf'))
                  ).full_image()
    assert not img.isNull()
    assert not img.hasAlphaChannel()
    assert see_through(img) == 0
    assert img.pixelColor(img.width() - 2,
                          img.height() - 2) == QtGui.QColor('white')


def test_so_is_its_small_copy(qapp, tmpdir):
    item = dropped(drawing_pdf(os.path.join(tmpdir, 'drawing.pdf')))
    assert see_through(item._thumbnail) == 0


def test_it_comes_in_with_twice_the_detail(qapp, tmpdir):
    item = dropped(drawing_pdf(os.path.join(tmpdir, 'drawing.pdf')))
    points = QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A6).sizePoints()
    assert abs(item.width - 2 * points.width()) <= 2
    assert abs(item.height - 2 * points.height()) <= 2
    assert item.full_image().size() == item.image_size()


def test_its_lines_are_still_there(qapp, tmpdir):
    img = dropped(drawing_pdf(os.path.join(tmpdir, 'drawing.pdf'))
                  ).full_image()
    darkest = min(img.pixelColor(x, y).lightness()
                  for x in range(img.width()) for y in range(0, 40))
    assert darkest < 100


def test_held_open_since_it_was_dropped_it_is_on_white_too(qapp, tmpdir):
    path = drawing_pdf(os.path.join(tmpdir, 'drawing.pdf'))
    with open(path, 'rb') as held:
        item = dropped((path, held))
    assert see_through(item.full_image()) == 0


def test_a_see_through_png_stays_see_through(qapp, tmpdir):
    img = QtGui.QImage(40, 40, QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtCore.Qt.GlobalColor.transparent)
    path = os.path.join(tmpdir, 'clear.png')
    img.save(path)
    loaded = dropped(path).full_image()
    assert loaded.hasAlphaChannel()
    assert loaded.pixelColor(5, 5).alpha() == 0


def test_a_pdf_is_known_by_what_it_holds():
    assert imagecache.is_pdf(b'%PDF-1.7\n...')
    assert imagecache.is_pdf(b'\n\n%PDF-1.4')
    assert not imagecache.is_pdf(b'\x89PNG\r\n')
