"""What a Mac's keyboard needs: it has no Delete key, and keeps F11."""

from unittest.mock import MagicMock, patch

import pytest
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref.actions.actions import actions, with_mac_keys
from beeref.items import BeeTextItem


def test_a_mac_is_given_the_keys_only_it_needs():
    with patch('beeref.actions.actions.sys.platform', 'darwin'):
        assert with_mac_keys(['Del'], ['Backspace']) == ['Del', 'Backspace']


def test_and_windows_keeps_the_keys_it_has():
    with patch('beeref.actions.actions.sys.platform', 'win32'):
        assert with_mac_keys(['Del'], ['Backspace']) == ['Del']


def test_the_keys_a_mac_is_given_are_ones_qt_knows():
    """A key written wrongly is no key at all, and nothing says so."""

    for keys in ('Backspace', 'Meta+Ctrl+F'):
        assert not QtGui.QKeySequence(keys).isEmpty()
        assert QtGui.QKeySequence(keys).toString() == keys


@pytest.fixture
def mac_keys(main_window, view, qtbot):
    """A window whose Delete answers to Backspace, as on a Mac."""

    main_window.show()
    qtbot.waitExposed(main_window)
    view.shortcuts_hint.hide()
    action = actions['delete'].qaction
    before = action.shortcuts()
    action.setShortcuts(['Del', 'Backspace'])
    yield view
    action.setShortcuts(before)
    view.scene.clearSelection()


def test_backspace_deletes_what_is_chosen(mac_keys):
    note = BeeTextItem('to be deleted')
    mac_keys.scene.addItem(note)
    mac_keys.scene.clearSelection()
    note.setSelected(True)

    QTest.keyClick(mac_keys.viewport(), Qt.Key.Key_Backspace)

    assert note.scene() is None


def test_in_a_note_being_written_it_rubs_out_a_letter_instead(mac_keys):
    """The note keeps the key to itself, as it keeps Del."""

    note = BeeTextItem('words')
    mac_keys.scene.addItem(note)
    mac_keys.scene.clearSelection()
    note.setSelected(True)
    note.enter_edit_mode()
    cursor = note.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
    note.setTextCursor(cursor)

    QTest.keyClick(mac_keys.viewport(), Qt.Key.Key_Backspace)

    assert note.toPlainText() == 'word'
    assert note.scene() is mac_keys.scene
    note.exit_edit_mode(commit=False)


# A board the system hands over, as a Mac does for one double-clicked

def test_a_file_handed_over_goes_to_the_window_that_is_open(
        qapp, main_window):
    event = MagicMock()
    event.type.return_value = QtCore.QEvent.Type.FileOpen
    event.file.return_value = 'other.blk'
    # On the class: the application hands the file to the first window
    # it finds, and one from the test before may not be gone yet
    with patch('beeref.view.BeeGraphicsView.open_from_outside') as handed:
        assert qapp.event(event) is True

    handed.assert_called_once_with('other.blk')


def test_a_board_handed_over_asks_about_what_is_not_saved(view):
    """Opened straight away, it threw the open board away without a
    word: on a Mac every board double-clicked comes this way."""

    with patch.object(view, 'get_confirmation_unsaved_changes',
                      return_value=False) as asked, \
            patch.object(view, 'open_from_file') as opened:
        view.open_from_outside('other.blk')

    asked.assert_called_once()
    opened.assert_not_called()


def test_and_is_opened_once_that_is_settled(view):
    with patch.object(view, 'get_confirmation_unsaved_changes',
                      return_value=True), \
            patch.object(view, 'open_from_file') as opened:
        view.open_from_outside('other.blk')

    opened.assert_called_once_with('other.blk')


def test_a_picture_handed_over_is_put_on_the_board_that_is_open(view):
    with patch.object(view, 'open_from_file') as opened, \
            patch.object(view, 'do_insert_images') as inserted:
        view.open_from_outside('shot.png')

    opened.assert_not_called()
    inserted.assert_called_once_with(['shot.png'])
