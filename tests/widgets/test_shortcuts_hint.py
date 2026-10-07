from unittest.mock import patch

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt

from beeref import constants
from beeref.widgets.shortcuts_hint import ShortcutsHint


def test_shown_on_startup(view):
    assert view.shortcuts_hint.isVisible() is True


def test_lists_the_shortcuts(view):
    keys = [keys for keys, what in ShortcutsHint.SHORTCUTS]
    assert 'Ctrl + J' in keys
    assert 'Ctrl + T' in keys
    assert 'Ctrl + G' in keys
    assert 'Alt + drag' in keys
    assert 'Ctrl + P' in keys
    # Every shortcut says what it does
    assert all(what for keys, what in ShortcutsHint.SHORTCUTS)


def test_the_hint_says_what_the_shortcuts_do_now(view):
    """Ctrl+Shift+T became the task list and Alt+T the table in 9.1."""

    said = dict(ShortcutsHint.SHORTCUTS)
    assert said['Ctrl + Shift + T'] == 'Add a task list'
    assert said['Alt + T'] == 'Add a table'


def labels(hint):
    return [label.text() for label in hint.findChildren(QtWidgets.QLabel)]


def test_on_a_mac_the_keys_go_by_the_names_on_its_keyboard(view):
    """Qt hands what is Ctrl on Windows to the Command key of a Mac."""

    with patch('beeref.widgets.shortcuts_hint.sys.platform', 'darwin'):
        said = labels(ShortcutsHint(view))
    assert '<b>Cmd + Shift + T</b>' in said
    assert '<b>Option + drag</b>' in said
    assert not any('Ctrl' in text or 'Alt' in text for text in said)


def test_and_on_windows_by_the_names_they_always_had(view):
    with patch('beeref.widgets.shortcuts_hint.sys.platform', 'win32'):
        said = labels(ShortcutsHint(view))
    assert '<b>Ctrl + Shift + T</b>' in said
    assert '<b>Alt + drag</b>' in said


def test_closing_hides_it(view):
    hint = view.shortcuts_hint
    hint.on_close_clicked()
    assert hint.isVisible() is False


def test_closing_does_not_stop_it_returning(view, settings):
    """Closing is for now; the checkbox is for good."""

    hint = view.shortcuts_hint
    hint.on_close_clicked()
    assert hint.wanted_on_startup() is True


def test_dont_show_again(view, settings):
    hint = view.shortcuts_hint
    hint.on_hide_changed(Qt.CheckState.Checked.value)
    assert hint.wanted_on_startup() is False

    hint.on_hide_changed(Qt.CheckState.Unchecked.value)
    assert hint.wanted_on_startup() is True


def test_not_shown_when_switched_off(view, settings):
    settings.setValue(ShortcutsHint.SETTINGS_KEY, False)
    hint = ShortcutsHint(view)
    hint.show_if_wanted()
    assert hint.isVisible() is False


def test_sits_in_the_bottom_left(view):
    view.resize(800, 600)
    hint = view.shortcuts_hint
    hint.reposition()
    assert hint.x() == hint.MARGIN
    assert hint.y() + hint.height() + hint.MARGIN == view.height()


def test_shows_the_version(view):
    """Which build this is has to be readable without opening a dialog."""

    labels = view.shortcuts_hint.findChildren(QtWidgets.QLabel)
    assert any(constants.VERSION in label.text() for label in labels)


def test_help_brings_it_back_after_closing(view):
    """Closing the card must not put the shortcuts out of reach."""

    hint = view.shortcuts_hint
    hint.on_close_clicked()
    assert hint.isVisible() is False

    with patch('beeref.widgets.HelpDialog'):
        view.on_action_help()
    assert hint.isVisible() is True


def test_help_brings_it_back_even_when_switched_off(view):
    """The checkbox governs the startup greeting, not asking for help."""

    hint = view.shortcuts_hint
    hint.hide_box.setChecked(True)
    hint.on_close_clicked()
    assert hint.wanted_on_startup() is False

    with patch('beeref.widgets.HelpDialog'):
        view.on_action_help()
    assert hint.isVisible() is True


def test_checkbox_remembers_what_was_chosen(view):
    """Reopening the card must not show the box unticked when it is on."""

    view.shortcuts_hint.hide_box.setChecked(True)
    fresh = ShortcutsHint(view)
    assert fresh.hide_box.isChecked() is True
