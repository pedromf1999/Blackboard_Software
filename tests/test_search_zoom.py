"""What Find goes to is brought to the same size on screen, whatever it
is: the size of its letters decides, not how long the word is."""

from PyQt6 import QtGui
import pytest

from beeref import commands
from beeref.items import BeeGroupItem, BeePixmapItem, BeeTextItem


def found(view, item, query):
    view.resize(1000, 700)
    view.scene.clearSelection()
    view.text_search_query = query
    view.zoom_to_match(item)


def line_on_screen(view, item, query):
    return item.search_line_height(query) * view.get_scale()


def note(view, words, scale=1):
    item = BeeTextItem(words)
    view.scene.addItem(item)
    item.setScale(scale)
    return item


def picture(view, caption, width=1200, height=900):
    img = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(90, 90, 110))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.caption = caption
    return item


def titled_group(view, title):
    first = note(view, 'one')
    second = note(view, 'two')
    second.setPos(900, 300)
    group = BeeGroupItem()
    commands.GroupItems(view.scene, [first, second], group).redo()
    group.title = title
    return group


def test_a_short_word_and_a_longer_one_come_to_the_same_size(view):
    """A share of the window for the word's width put the letters of a
    short word close enough to fill it."""

    item = note(view, 'PCB and a considerably longer word')
    found(view, item, 'PCB')
    short = view.get_scale()
    found(view, item, 'considerably')
    assert view.get_scale() == pytest.approx(short)
    assert line_on_screen(view, item, 'PCB') == pytest.approx(
        view.MATCH_LINE_PIXELS, abs=1)


def test_the_word_is_in_the_middle_of_the_window(view):
    item = note(view, 'aaaa bbbb cccc dddd target')
    found(view, item, 'target')
    word = item.search_rect('target')
    middle = view.mapFromScene(word.center())
    assert abs(middle.x() - view.viewport().width() / 2) < 3
    assert abs(middle.y() - view.viewport().height() / 2) < 3


@pytest.mark.parametrize('scale', [0.01, 1, 400])
def test_at_any_scale_of_the_note_the_letters_come_to_that_size(view, scale):
    item = note(view, 'the quick brown fox', scale=scale)
    found(view, item, 'brown')
    assert line_on_screen(view, item, 'brown') == pytest.approx(
        view.MATCH_LINE_PIXELS, abs=1)


def test_a_note_written_large_is_not_gone_to_any_closer(view):
    """Bigger letters on the board, the same letters on screen."""

    item = note(view, 'plain and big')
    cursor = item.textCursor()
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    fmt = QtGui.QTextCharFormat()
    fmt.setFontPointSize(60)
    cursor.mergeCharFormat(fmt)
    found(view, item, 'big')
    assert item.search_rect('big').height() * view.get_scale() == (
        pytest.approx(view.MATCH_LINE_PIXELS, abs=1))


def test_words_too_long_for_that_size_are_all_kept_in_sight(view):
    words = 'a very long sentence that goes on ' * 8
    item = note(view, words.strip())
    query = words.strip()[:200]
    found(view, item, query)
    word = item.search_rect(query)
    seen = view.mapToScene(view.viewport().rect()).boundingRect()
    assert word.width() <= seen.width() * view.MATCH_MOST_OF_WINDOW + 1
    assert line_on_screen(view, item, query) < view.MATCH_LINE_PIXELS


def test_a_caption_is_brought_to_a_size_to_read(view):
    """Its band is the width of the picture: fifteen per cent of the
    window for that left its letters a few pixels tall."""

    item = picture(view, 'Top view of the latch')
    found(view, item, 'latch')
    assert line_on_screen(view, item, 'latch') == pytest.approx(
        view.MATCH_LINE_PIXELS, abs=1)


def test_a_caption_of_many_lines_is_measured_by_one(view):
    item = picture(view, 'many words that wrap round ' * 40, 600, 400)
    found(view, item, 'wrap')
    # All of it may not fit, but a line of it must not shrink with it
    # further than the window asks
    height = item.search_rect('wrap').height()
    seen = view.mapToScene(view.viewport().rect()).boundingRect()
    assert height <= seen.height() * view.MATCH_MOST_OF_WINDOW + 1


def test_a_group_title_is_brought_to_a_size_to_read(view):
    group = titled_group(view, 'Lid Latch')
    found(view, group, 'Latch')
    assert line_on_screen(view, group, 'Latch') == pytest.approx(
        view.MATCH_LINE_PIXELS, abs=1)


def test_a_note_title_is_measured_by_the_title(view):
    item = note(view, 'nothing to see in the words')
    item.title = 'Heading'
    assert item.search_line_height('heading') == pytest.approx(
        item.title_search_line_height())
    found(view, item, 'heading')
    assert line_on_screen(view, item, 'heading') == pytest.approx(
        view.MATCH_LINE_PIXELS, abs=1)


def test_a_group_scaled_takes_what_is_in_it_with_it(view):
    group = titled_group(view, 'Lid Latch')
    inside = group.bee_children()[0]
    before = inside.search_line_height('one')
    group.setScale(3)
    assert inside.search_line_height('one') == pytest.approx(3 * before)
