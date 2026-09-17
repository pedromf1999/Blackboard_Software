"""Web addresses in notes are underlined."""

import re

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref.items import BeeTextItem


def note(view, text):
    item = BeeTextItem(text)
    view.scene.addItem(item)
    item.setPos(0, 0)
    return item


def span(item, start, end):
    """Where a stretch of the first line starts and ends, left to right."""

    block = item.document().begin()
    layout = block.layout()
    line = layout.lineForTextPosition(start)
    x = layout.position().x()
    return (x + line.cursorToX(start)[0], x + line.cursorToX(end)[0])


def test_an_address_is_underlined_from_end_to_end(view):
    item = note(view, 'see https://example.com/page here')
    [(line, _thickness, _color)] = item.url_underlines()
    start = len('see ')
    end = start + len('https://example.com/page')
    assert (line.x1(), line.x2()) == span(item, start, end)


def test_an_address_starting_with_www_is_underlined(view):
    item = note(view, 'www.example.com')
    assert len(item.url_underlines()) == 1


def test_the_punctuation_after_an_address_is_not_underlined(view):
    item = note(view, 'go to www.example.com.')
    [(line, _thickness, _color)] = item.url_underlines()
    start = len('go to ')
    assert line.x2() == span(item, start, start + len('www.example.com'))[1]


def test_text_without_an_address_is_not_underlined(view):
    item = note(view, 'nothing to see here.com')
    assert item.url_underlines() == []


def test_every_address_is_underlined(view):
    item = note(view, 'www.one.com and\nhttp://two.org')
    assert len(item.url_underlines()) == 2


def test_the_underline_sits_under_the_letters(view):
    item = note(view, 'www.example.com')
    [(line, _thickness, _color)] = item.url_underlines()
    layout = item.document().begin().layout()
    baseline = (layout.position().y() + layout.lineAt(0).y()
                + layout.lineAt(0).ascent())
    assert line.y1() == line.y2()
    assert line.y1() > baseline


def test_bigger_letters_get_a_bigger_underline(view):
    small = note(view, 'www.example.com')
    big = note(view, 'www.example.com')
    cursor = QtGui.QTextCursor(big.document())
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    fmt = QtGui.QTextCharFormat()
    fmt.setFontPointSize(40)
    cursor.mergeCharFormat(fmt)
    assert big.url_underlines()[0][1] > small.url_underlines()[0][1]


def test_the_underline_is_the_colour_of_the_letters(view):
    item = note(view, 'go to www.example.com')
    cursor = QtGui.QTextCursor(item.document())
    cursor.setPosition(len('go to '))
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End,
                        QtGui.QTextCursor.MoveMode.KeepAnchor)
    item.setTextCursor(cursor)
    item.apply_highlight(QtGui.QColor(255, 255, 255))

    [(_line, _thickness, color)] = item.url_underlines()
    letters = item.text_color_over(QtGui.QColor(255, 255, 255))
    assert color.rgba() == letters.rgba()
    assert color.rgba() != QtGui.QColor(item.defaultTextColor()).rgba()


def test_words_typed_after_an_address_are_not_underlined(view):
    item = note(view, 'www.example.com')
    item.enter_edit_mode()
    cursor = item.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
    item.setTextCursor(cursor)
    before = item.url_underlines()[0][0].x2()

    for char in ' more':
        event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress,
                                Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier,
                                char)
        item.keyPressEvent(event)
    assert item.toPlainText() == 'www.example.com more'
    assert item.url_underlines()[0][0].x2() == before


def test_the_underline_is_not_saved_as_formatting(view):
    item = note(view, 'www.example.com')
    html = item.get_extra_save_data()['html']
    assert 'underline' not in html


ZOOM = 4


def render(item):
    rect = QtCore.QRectF(0, 0, item.boundingRect().right(),
                         item.boundingRect().bottom())
    image = QtGui.QImage(int(rect.width() * ZOOM), int(rect.height() * ZOOM),
                         QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor(255, 0, 255))
    painter = QtGui.QPainter(image)
    item.scene().render(painter, QtCore.QRectF(image.rect()), rect,
                        Qt.AspectRatioMode.IgnoreAspectRatio)
    painter.end()
    return image


def box_pixels_along(image, item, line):
    """How many pixels along the underline show only the box."""

    y = int(line.y1() * ZOOM)
    box = item.box_color.rgba()
    return sum(1 for x in range(int(line.x1() * ZOOM) + 2,
                                int(line.x2() * ZOOM) - 2)
               if image.pixel(x, y) == box)


def test_the_underline_is_drawn(view):
    item = note(view, 'www.example.com')
    item.setSelected(False)
    [(line, _thickness, _color)] = item.url_underlines()
    assert box_pixels_along(render(item), item, line) == 0


def test_plain_words_have_gaps_where_the_underline_would_be(view):
    """The check above would pass on letters alone without this."""

    item = note(view, 'www.example.com')
    item.setSelected(False)
    [(line, _thickness, _color)] = item.url_underlines()
    # A pattern that finds nothing, so the same words go undrawn under
    item.URL_RE = re.compile('(?!)')
    assert item.url_underlines() == []
    assert box_pixels_along(render(item), item, line) > 0
