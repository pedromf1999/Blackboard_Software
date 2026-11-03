"""Finding words everywhere, only in what is pinned, or only on the
board."""

from unittest.mock import patch

import pytest
from PyQt6 import QtGui

from beeref.items import BeePixmapItem, BeeTextItem


@pytest.fixture
def board(main_window, view, qtbot):
    """A window on screen, the board seen at 100%."""

    main_window.resize(1000, 700)
    main_window.show()
    qtbot.waitExposed(main_window)
    view.shortcuts_hint.hide()
    view.setTransform(QtGui.QTransform())
    return view


def note_at(view, y, text):
    note = BeeTextItem(text)
    view.scene.addItem(note)
    note.setPos(0, y)
    return note


def picture_at(view, y, caption):
    image = QtGui.QImage(400, 300, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor(90, 90, 120))
    item = BeePixmapItem(image)
    item.caption = caption
    view.scene.addItem(item)
    item.setPos(0, y)
    return item


def pin(view, item):
    view.scene.clearSelection()
    item.setSelected(True)
    view.on_action_pin_note()


def look_for(view, word, scope=None):
    view.on_action_find_text()
    view.find_bar.input.setText(word)
    if scope is not None:
        choose(view, scope)


def choose(view, scope):
    bar = view.find_bar
    bar.scope.setCurrentIndex(bar.scope.findData(scope))


@pytest.fixture
def oaks(board):
    """Two notes on the board and one pinned, all with the same word."""

    first = note_at(board, 0, 'oak one')
    pinned = note_at(board, 200, 'oak pinned')
    last = note_at(board, 400, 'oak two')
    pin(board, pinned)
    board.scene.clearSelection()
    return first, pinned, last


def test_the_bar_offers_the_three_scopes(board):
    bar = board.find_bar
    assert [bar.scope.itemText(i) for i in range(bar.scope.count())] == [
        'Everywhere', 'Only pinned', 'Not pinned']
    assert bar.scope.currentData() == 'all'
    assert bar.scope.isVisibleTo(bar)


def test_everywhere_finds_pinned_and_not(board, oaks):
    look_for(board, 'oak')
    board.find_bar.next_button.click()
    assert board.find_bar.count.text() == '1 of 3'


def test_only_pinned_finds_the_pinned_note_only(board, oaks):
    first, pinned, last = oaks
    look_for(board, 'oak')
    choose(board, 'pinned')

    assert pinned.isSelected() is True
    assert board.find_bar.count.text() == '1 of 1'
    board.find_bar.next_button.click()
    assert pinned.isSelected() is True
    assert first.isSelected() is False
    assert last.isSelected() is False


def test_not_pinned_leaves_the_pinned_note_out(board, oaks):
    first, pinned, last = oaks
    look_for(board, 'oak', 'board')
    assert board.find_bar.count.text() == '1 of 2'
    assert first.isSelected() is True

    board.find_bar.next_button.click()
    assert last.isSelected() is True
    board.find_bar.next_button.click()
    assert first.isSelected() is True
    assert pinned.isSelected() is False


def test_a_pinned_picture_counts_as_pinned(board):
    note = note_at(board, 0, 'oak on the board')
    picture = picture_at(board, 300, 'oak in a caption')
    pin(board, picture)
    board.scene.clearSelection()

    look_for(board, 'oak', 'pinned')
    assert picture.isSelected() is True
    assert board.find_bar.count.text() == '1 of 1'

    choose(board, 'board')
    assert note.isSelected() is True
    assert board.find_bar.count.text() == '1 of 1'


def test_choosing_a_scope_starts_from_its_first_match(board, oaks):
    first, pinned, last = oaks
    look_for(board, 'oak')
    for _ in range(3):
        board.find_bar.next_button.click()
    assert board.find_bar.count.text() == '3 of 3'

    choose(board, 'board')
    assert first.isSelected() is True
    assert board.find_bar.count.text() == '1 of 2'


def test_choosing_a_scope_with_no_word_finds_nothing_yet(board, oaks):
    board.on_action_find_text()
    board.find_bar.input.setText('')
    choose(board, 'pinned')

    assert board.text_search_scope == 'pinned'
    assert board.scene.selectedItems() == []
    assert board.find_bar.count.text() == ''


def test_choosing_a_scope_leaves_the_typing_where_it_was(board, oaks):
    look_for(board, 'oak')
    board.find_bar.input.setFocus()
    choose(board, 'pinned')
    assert board.find_bar.input.hasFocus()


def test_nothing_pinned_says_no_matches(board):
    note_at(board, 0, 'oak one')
    look_for(board, 'oak', 'pinned')
    assert board.find_bar.count.text() == 'No matches'
    assert board.scene.selectedItems() == []


def test_the_board_stays_where_it_is_for_a_pinned_match(board, oaks):
    first, pinned, last = oaks
    transform = board.transform()
    centre = board.mapToScene(board.viewport().rect().center())

    look_for(board, 'oak', 'pinned')
    assert pinned.isSelected() is True
    assert board.transform() == transform
    assert board.mapToScene(board.viewport().rect().center()) == centre
    assert board.find_bar.back_button.isEnabled() is False


def test_the_scope_stays_once_the_bar_is_closed(board, oaks):
    first, pinned, last = oaks
    look_for(board, 'oak', 'pinned')
    board.find_bar.close_bar()
    board.scene.clearSelection()

    board.on_action_find_next()
    assert pinned.isSelected() is True

    board.on_action_find_text()
    assert board.find_bar.scope.currentData() == 'pinned'


def test_a_notification_says_where_it_looked(board, oaks):
    look_for(board, 'oak', 'pinned')
    board.find_bar.close_bar()

    with patch('beeref.widgets.BeeNotification') as notification:
        board.on_action_find_next()
    assert '(only pinned)' in notification.call_args[0][1]

    board.text_search_query = 'elm'
    board.text_search_index = -1
    with patch('beeref.widgets.BeeNotification') as notification:
        board.find_next_text_match()
    assert notification.call_args[0][1] == (
        'No text matching "elm" (only pinned)')


def test_everywhere_says_nothing_of_where(board, oaks):
    board.text_search_query = 'elm'
    with patch('beeref.widgets.BeeNotification') as notification:
        board.find_next_text_match()
    assert notification.call_args[0][1] == 'No text matching "elm"'


def test_a_minimized_pinned_note_is_opened_when_found(board, oaks):
    first, pinned, last = oaks
    board.set_pinned_note_minimized(pinned, True)
    look_for(board, 'oak', 'pinned')
    assert pinned.is_minimized is False
    assert pinned.isSelected() is True


def test_a_new_board_keeps_the_scope(board, oaks):
    # It belongs to the bar, as the word does, not to a board
    look_for(board, 'oak', 'board')
    board.find_bar.close_bar()
    board.clear_scene()
    assert board.text_search_scope == 'board'
    assert board.find_bar.scope.currentData() == 'board'


def test_a_board_match_can_be_gone_back_from(board, oaks):
    first, pinned, last = oaks
    transform = board.transform()
    look_for(board, 'oak', 'board')
    assert first.isSelected() is True
    assert board.transform() != transform

    board.find_bar.back_button.click()
    assert board.transform() == transform
