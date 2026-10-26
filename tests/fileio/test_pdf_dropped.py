"""A PDF brought in as a picture comes in on white, as on paper, rather
than see-through where nothing is printed."""

import os

from PyQt6 import QtCore, QtGui

from beeref.fileio import image
from beeref.fileio.image import load_image


def drawing_pdf(path):
    """A page with one black line on it and nothing else."""

    writer = QtGui.QPdfWriter(path)
    writer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A6))
    painter = QtGui.QPainter(writer)
    painter.setPen(QtGui.QPen(QtGui.QColor('black'), 20))
    painter.drawLine(100, 100, 800, 100)
    painter.end()
    return path


def see_through(img):
    return sum(1 for x in range(0, img.width(), 10)
               for y in range(0, img.height(), 10)
               if img.pixelColor(x, y).alpha() < 255)


def test_a_dropped_pdf_comes_in_on_white(qapp, tmpdir):
    path = drawing_pdf(os.path.join(tmpdir, 'drawing.pdf'))
    img, _ = load_image(path)
    assert not img.isNull()
    assert not img.hasAlphaChannel()
    assert see_through(img) == 0
    assert img.pixelColor(img.width() - 2,
                          img.height() - 2) == QtGui.QColor('white')


def test_its_lines_are_still_there(qapp, tmpdir):
    path = drawing_pdf(os.path.join(tmpdir, 'drawing.pdf'))
    img, _ = load_image(path)
    darkest = min(img.pixelColor(x, y).lightness()
                  for x in range(img.width()) for y in range(0, 40))
    assert darkest < 100


def test_held_open_since_it_was_dropped_it_is_on_white_too(qapp, tmpdir):
    path = drawing_pdf(os.path.join(tmpdir, 'drawing.pdf'))
    with open(path, 'rb') as held:
        img, _ = load_image((path, held))
    assert see_through(img) == 0


def test_a_see_through_png_stays_see_through(qapp, tmpdir):
    img = QtGui.QImage(40, 40, QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtCore.Qt.GlobalColor.transparent)
    path = os.path.join(tmpdir, 'clear.png')
    img.save(path)
    loaded, _ = load_image(path)
    assert loaded.hasAlphaChannel()
    assert loaded.pixelColor(5, 5).alpha() == 0


def test_a_pdf_is_known_by_what_it_holds():
    assert image.is_pdf(b'%PDF-1.7\n...')
    assert image.is_pdf(b'\n\n%PDF-1.4')
    assert not image.is_pdf(b'\x89PNG\r\n')
