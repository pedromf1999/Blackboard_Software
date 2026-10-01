"""A web address in a picture's caption works as one in a note does."""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref.items import BeePixmapItem, web_addresses


def image(view, caption, width=600, height=300):
    img = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32)
    img.fill(QtGui.QColor(90, 90, 120))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.caption = caption
    return item


def laid_out(item):
    band = item.caption_rect()
    inset = item.caption_inset()
    room = band.adjusted(inset, inset, -inset, -inset)
    return item.caption_lines(room, item.caption_size())


def point_on(item, index):
    """The middle of a letter of the caption, in the picture's own
    coordinates."""

    layout, places = laid_out(item)
    for number, place in enumerate(places):
        line = layout.lineAt(number)
        if line.textStart() <= index < line.textStart() + line.textLength():
            left = line.cursorToX(index)[0]
            right = line.cursorToX(index + 1)[0]
            return QtCore.QPointF(place.x() + (left + right) / 2,
                                  place.y() + line.y() + line.height() / 2)
    raise AssertionError(f'No letter {index}')


def ctrl_click(item, point, modifiers=Qt.KeyboardModifier.ControlModifier):
    event = MagicMock()
    event.button.return_value = Qt.MouseButton.LeftButton
    event.modifiers.return_value = modifiers
    event.pos.return_value = point
    item.mousePressEvent(event)
    return event


def test_web_addresses_are_found_as_a_note_finds_them():
    found = web_addresses('See https://example.com/a, or www.example.org.')

    assert found == [(4, 25, 'https://example.com/a'),
                     (30, 45, 'http://www.example.org')]


def test_the_address_under_the_mouse_is_found(view):
    caption = 'Inspired by https://example.com/chair today'
    item = image(view, caption)
    start = caption.index('https')

    assert item.caption_url_at(point_on(item, start + 3)) == (
        'https://example.com/chair')
    assert item.caption_url_at(point_on(item, 2)) is None
    assert item.caption_url_at(item.crop.center()) is None


def test_it_is_found_on_a_caption_wrapped_onto_more_lines(view):
    caption = ('A long caption about the chair, which wraps onto more '
               'than one line before it gets to www.example.com at the end')
    item = image(view, caption, width=250)
    layout, _ = laid_out(item)
    assert layout.lineCount() > 1

    index = caption.index('www.') + 2
    assert item.caption_url_at(point_on(item, index)) == (
        'http://www.example.com')


@patch('PyQt6.QtGui.QDesktopServices.openUrl')
def test_ctrl_click_on_it_opens_it(open_mock, view):
    caption = 'Inspired by https://example.com/chair'
    item = image(view, caption)

    event = ctrl_click(item, point_on(item, caption.index('example')))

    open_mock.assert_called_once()
    assert open_mock.call_args[0][0].toString() == (
        'https://example.com/chair')
    event.accept.assert_called_once()


@patch('beeref.selection.SelectableMixin.mousePressEvent')
@patch('PyQt6.QtGui.QDesktopServices.openUrl')
def test_a_click_without_ctrl_opens_nothing(open_mock, super_mock, view):
    caption = 'Inspired by https://example.com/chair'
    item = image(view, caption)

    ctrl_click(item, point_on(item, caption.index('example')),
               Qt.KeyboardModifier.NoModifier)

    open_mock.assert_not_called()
    super_mock.assert_called_once()


@patch('beeref.selection.SelectableMixin.mousePressEvent')
@patch('PyQt6.QtGui.QDesktopServices.openUrl')
def test_ctrl_click_on_the_words_round_it_selects_as_usual(
        open_mock, super_mock, view):
    item = image(view, 'Inspired by https://example.com/chair')

    ctrl_click(item, point_on(item, 1))

    open_mock.assert_not_called()
    super_mock.assert_called_once()


def test_the_address_is_underlined(view):
    caption = 'Inspired by https://example.com/chair, really'
    item = image(view, caption)
    layout, _ = laid_out(item)

    [part] = layout.formats()
    assert part.format.fontUnderline() is True
    assert part.start == caption.index('https')
    assert part.length == len('https://example.com/chair')


def test_words_without_an_address_are_not(view):
    item = image(view, 'Top view of the chair')
    layout, _ = laid_out(item)

    assert layout.formats() == []


@pytest.mark.parametrize('width', [120, 250, 600])
def test_the_words_still_fit_their_band(view, width):
    caption = ('See https://example.com/a-very-long-address/for-a-chair '
               'and the notes about it')
    item = image(view, caption, width=width)
    layout, places = laid_out(item)

    last = layout.lineAt(layout.lineCount() - 1)
    bottom = places[-1].y() + last.y() + last.height()
    band = item.caption_rect()
    assert bottom <= band.bottom() - item.caption_inset() + 1
    assert places[0].y() >= band.top() + item.caption_inset() - 1


@patch('PyQt6.QtGui.QDesktopServices.openUrl')
def test_ctrl_click_in_the_window_opens_it(open_mock, main_window, view,
                                           qtbot):
    main_window.resize(1000, 700)
    main_window.show()
    qtbot.waitExposed(main_window)
    caption = 'Inspired by https://example.com/chair'
    item = image(view, caption)
    view.setTransform(QtGui.QTransform())
    view.centerOn(item.sceneBoundingRect().center())

    point = view.mapFromScene(item.mapToScene(
        point_on(item, caption.index('example'))))
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.ControlModifier, point)

    open_mock.assert_called_once()
    assert open_mock.call_args[0][0].toString() == (
        'https://example.com/chair')


def test_the_caption_being_written_is_drawn_with_its_address(view):
    item = image(view, '')
    item.setSelected(True)
    view.on_action_image_caption()
    item.caption_editor.setPlainText('See www.example.com')
    picture = QtGui.QImage(800, 600, QtGui.QImage.Format.Format_ARGB32)
    painter = QtGui.QPainter(picture)
    view.scene.render(painter)
    painter.end()

    assert item.caption_editing is True
