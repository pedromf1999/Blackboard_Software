"""Taking a highlight off: the no-colour button in its colour dialog."""

from unittest.mock import patch

from PyQt6 import QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref.items import BeeTextItem
from beeref.widgets.color_dialog import layout_holding


YELLOW = QtGui.QColor(255, 255, 0)


def format_at(item, position):
    cursor = QtGui.QTextCursor(item.document())
    cursor.setPosition(position)
    return cursor.charFormat()


def is_highlighted(item, position):
    return format_at(item, position).background().style() != (
        Qt.BrushStyle.NoBrush)


def highlighted_note(view, text='one two three'):
    item = BeeTextItem(text)
    view.scene.addItem(item)
    item.apply_highlight(YELLOW)
    item.setSelected(True)
    return item


def no_color_button(dialog):
    return dialog.findChild(QtWidgets.QPushButton, 'no_color')


def press_no_highlight(dialog):
    """Stand in for the dialog: press its no-colour button."""

    no_color_button(dialog).click()
    return dialog.result()


# The note

def test_remove_highlight_from_all_the_text(view):
    item = highlighted_note(view)
    item.remove_highlight()
    for position in (1, 5, 10):
        assert not is_highlighted(item, position)


def test_remove_highlight_gives_the_words_the_box_colour(view):
    item = highlighted_note(view)
    item.remove_highlight()
    assert format_at(item, 1).foreground().color() == QtGui.QColor(
        item.defaultTextColor())


def test_remove_highlight_from_the_selection_only(view):
    item = highlighted_note(view)
    item.enter_edit_mode()
    cursor = item.textCursor()
    cursor.setPosition(4)
    cursor.setPosition(7, QtGui.QTextCursor.MoveMode.KeepAnchor)
    item.setTextCursor(cursor)
    item.remove_highlight()
    assert is_highlighted(item, 2)
    assert not is_highlighted(item, 6)
    assert is_highlighted(item, 10)


def test_remove_highlight_keeps_the_rest_of_the_look(view):
    item = highlighted_note(view)
    charformat = QtGui.QTextCharFormat()
    charformat.setFontWeight(QtGui.QFont.Weight.Bold)
    item.apply_char_format(charformat)
    item.remove_highlight()
    assert format_at(item, 2).fontWeight() == QtGui.QFont.Weight.Bold
    assert not is_highlighted(item, 2)


def test_apply_highlight_with_no_colour_removes_it(view):
    item = highlighted_note(view)
    item.apply_highlight(QtGui.QColor())
    assert not is_highlighted(item, 2)


# The dialog

def test_dialog_offers_no_highlight_beside_the_eyedropper(view):
    seen = {}

    def look(dialog):
        button = no_color_button(dialog)
        eyedropper = dialog.findChild(QtWidgets.QPushButton, 'eyedropper')
        seen['tooltip'] = button.toolTip()
        seen['text'] = button.text()
        seen['icon'] = not button.icon().isNull()
        row = layout_holding(dialog.layout(), button)[0]
        seen['beside'] = (
            isinstance(row, QtWidgets.QHBoxLayout)
            and row is layout_holding(dialog.layout(), eyedropper)[0])
        return 0

    highlighted_note(view)
    with patch.object(QtWidgets.QColorDialog, 'exec', look):
        view.on_action_text_highlight_color()
    assert seen == {'tooltip': 'No highlight', 'text': '', 'icon': True,
                    'beside': True}


def test_no_highlight_takes_it_off(view):
    item = highlighted_note(view)
    with patch.object(QtWidgets.QColorDialog, 'exec', press_no_highlight):
        view.on_action_text_highlight_color()
    assert not is_highlighted(item, 2)
    assert len(view.undo_stack) == 1


def test_no_highlight_undo_puts_it_back(view):
    item = highlighted_note(view)
    before = item.toHtml()
    with patch.object(QtWidgets.QColorDialog, 'exec', press_no_highlight):
        view.on_action_text_highlight_color()
    view.undo_stack.undo()
    assert item.toHtml() == before
    assert is_highlighted(item, 2)


def test_pick_color_returns_no_colour_for_the_button(view):
    previewed = []
    with patch.object(QtWidgets.QColorDialog, 'exec', press_no_highlight):
        color = view.pick_color_live(
            'Choose', QtGui.QColor('red'), previewed.append,
            none_label='No highlight')
    assert color is not None
    assert not color.isValid()
    assert not previewed[-1].isValid()


def test_other_colour_dialogs_have_no_such_button(view):
    seen = []

    def look(dialog):
        seen.append(no_color_button(dialog))
        return 0

    with patch.object(QtWidgets.QColorDialog, 'exec', look):
        view.pick_color_live('Choose', QtGui.QColor('red'), lambda c: None)
    assert seen == [None]


def test_no_colour_icon_is_drawn():
    from beeref.assets import BeeAssets
    assert not BeeAssets().color_icon('no_color').isNull()
