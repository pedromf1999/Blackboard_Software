"""Every pinned note shows its words and its title at the same sizes."""

import pytest
from PyQt6 import QtCore, QtGui

from beeref.items import BeeTextItem
from . import test_pinned_notes
from .test_pinned_notes import note_at, pin, zoom_to


# The window with a picture on its board, as the other pinned note tests
# have it
board = test_pinned_notes.board


def written_at(note, size):
    """All of a note's words made this big, in points."""

    cursor = QtGui.QTextCursor(note.document())
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    fmt = QtGui.QTextCharFormat()
    fmt.setFontPointSize(size)
    cursor.mergeCharFormat(fmt)


def on_screen(note, size):
    """How big letters of this many points in the note show."""

    return size * note.scale()


def test_words_written_at_any_size_show_at_one(board):
    small = note_at(board, QtCore.QPoint(100, 100), 'small words')
    big = note_at(board, QtCore.QPoint(100, 200), 'big words')
    written_at(small, 7)
    written_at(big, 40)
    big.setScale(2.5)
    zoom_to(board, 0.4)

    pin(board, small)
    pin(board, big)

    assert on_screen(small, small.usual_point_size()) == pytest.approx(
        on_screen(big, big.usual_point_size()))


def test_the_size_most_of_the_words_are_written_at_is_the_one(board):
    note = note_at(board, QtCore.QPoint(100, 100),
                   'Heading\nand a good many more words under it')
    cursor = QtGui.QTextCursor(note.document())
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock,
                        QtGui.QTextCursor.MoveMode.KeepAnchor)
    fmt = QtGui.QTextCharFormat()
    fmt.setFontPointSize(30)
    cursor.mergeCharFormat(fmt)

    plain = note_at(board, QtCore.QPoint(100, 300), 'just words')
    assert note.usual_point_size() == pytest.approx(
        plain.usual_point_size())


def test_titles_show_at_one_size_too(board):
    first = note_at(board, QtCore.QPoint(100, 100), 'one')
    second = note_at(board, QtCore.QPoint(100, 250), 'two')
    first.title = 'First'
    second.title = 'Second'
    second.set_title_size(60)
    written_at(first, 20)

    pin(board, first)
    pin(board, second)

    assert on_screen(first, first.title_size()) == pytest.approx(
        on_screen(second, second.title_size()))
    # The usual step above the words under it
    assert first.title_size() == pytest.approx(
        first.usual_point_size() * BeeTextItem.TITLE_SIZE_FRACTION)


def test_unpinned_the_title_has_its_own_size_again(board):
    note = note_at(board, QtCore.QPoint(100, 100), 'words')
    note.title = 'Title'
    note.set_title_size(60)
    pin(board, note)
    assert note.title_size() != pytest.approx(60)

    pin(board, note)

    assert note.title_size() == pytest.approx(60)


def test_made_bigger_while_pinned_it_shows_at_the_same_size(board):
    note = note_at(board, QtCore.QPoint(100, 100), 'words')
    pin(board, note)
    before = on_screen(note, note.usual_point_size())

    written_at(note, 36)
    board.place_pinned_notes()

    assert on_screen(note, note.usual_point_size()) == pytest.approx(before)


def test_a_title_cannot_be_sized_while_pinned(board):
    note = note_at(board, QtCore.QPoint(100, 100), 'words')
    note.title = 'Title'
    note.set_title_size(30)
    pin(board, note)
    board.scene.clearSelection()
    note.setSelected(True)
    board.on_action_text_title()

    board.scale_band_being_written(1.5)

    assert note.stored_title_size() == pytest.approx(30)


def test_a_board_from_before_brings_its_pinned_notes_to_size(board):
    old = BeeTextItem('words', pin={'order': 0, 'minimized': False})
    old.setScale(2.7)
    board.scene.addItem(old)
    board.place_pinned_notes()

    assert old.scale() == pytest.approx(board.pinned_scale(old))


def test_the_size_on_the_board_is_saved_with_it(board, tmp_path):
    from beeref import fileio

    note = note_at(board, QtCore.QPoint(100, 100), 'words')
    note.setScale(2.5)
    pin(board, note)
    filename = str(tmp_path / 'board.blk')
    fileio.save_bee(filename, board.scene, create_new=True)
    board.scene.clear()
    fileio.load_bee(filename, board.scene)
    board.scene.add_queued_items()
    board.place_pinned_notes()
    [opened] = board.scene.pinned_notes()

    pin(board, opened)

    assert opened.scale() == pytest.approx(2.5)


# The size, set in the settings -- the test settings, in a folder of
# their own; see conftest

def test_the_size_is_a_setting(board, settings):
    note = note_at(board, QtCore.QPoint(100, 100), 'words')
    pin(board, note)
    assert on_screen(note, note.usual_point_size()) == pytest.approx(9)

    settings.setValue('Items/pinned_text_size', 14)

    assert on_screen(note, note.usual_point_size()) == pytest.approx(14)
    assert on_screen(note, note.title_size()) == pytest.approx(
        14 * BeeTextItem.TITLE_SIZE_FRACTION)


def test_restoring_the_defaults_brings_it_back(board, settings):
    note = note_at(board, QtCore.QPoint(100, 100), 'words')
    pin(board, note)
    settings.setValue('Items/pinned_text_size', 20)

    settings.restore_defaults()

    assert on_screen(note, note.usual_point_size()) == pytest.approx(9)


def test_a_size_out_of_reason_is_not_taken(board, settings):
    settings.setValue('Items/pinned_text_size', 500)

    assert settings.valueOrDefault('Items/pinned_text_size') == 9


def test_the_settings_window_offers_it(board, settings):
    from beeref.widgets.settings import PinnedTextSizeWidget

    widget = PinnedTextSizeWidget()
    assert widget.input.value() == 9
    assert widget.input.suffix() == ' pt'

    widget.input.setValue(12)

    assert settings.valueOrDefault('Items/pinned_text_size') == 12


# No buttons to size what cannot be sized

def test_a_pinned_note_has_no_buttons_to_size_its_words(board):
    toolbar = board.text_toolbar
    note = note_at(board, QtCore.QPoint(100, 100), 'words')
    board.scene.clearSelection()
    note.setSelected(True)
    board.update_text_toolbar()
    assert toolbar.smaller.isVisibleTo(toolbar) is True
    assert toolbar.bigger.isVisibleTo(toolbar) is True
    wide = toolbar.width()

    pin(board, note)
    board.scene.clearSelection()
    note.setSelected(True)
    board.update_text_toolbar()

    assert toolbar.smaller.isVisibleTo(toolbar) is False
    assert toolbar.bigger.isVisibleTo(toolbar) is False
    assert toolbar.width() < wide


def test_a_note_on_the_board_has_them_again(board):
    toolbar = board.text_toolbar
    pinned = note_at(board, QtCore.QPoint(100, 100), 'pinned')
    pin(board, pinned)
    board.scene.clearSelection()
    pinned.setSelected(True)
    board.update_text_toolbar()
    loose = note_at(board, QtCore.QPoint(100, 300), 'loose')

    board.scene.clearSelection()
    loose.setSelected(True)
    board.update_text_toolbar()

    assert toolbar.smaller.isVisibleTo(toolbar) is True
    assert toolbar.bigger.isVisibleTo(toolbar) is True
