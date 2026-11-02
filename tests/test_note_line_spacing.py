"""The lines of a note stood apart, as if with an empty line between them:
tasks above all, whose list of lines reads easier for it."""

import os
from unittest.mock import MagicMock

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
import pytest

from beeref import commands
from beeref.fileio.sql import SQLiteIO
from beeref.items import BeeTextItem
from beeref.scene import BeeGraphicsScene


def note(view, lines, tasks=True, **kwargs):
    item = BeeTextItem('\n'.join(lines), **kwargs)
    view.scene.addItem(item)
    if tasks:
        block = item.document().begin()
        while block.isValid():
            item.set_task(block, True)
            block = item.document().findBlock(block.position()).next()
        item.refresh_tasks()
    return item


def block_of(item, text):
    block = item.document().begin()
    while block.isValid():
        if block.text() == text:
            return block
        block = block.next()
    raise LookupError(text)


def box_of(item, text):
    return item.document().documentLayout().blockBoundingRect(
        block_of(item, text))


def gap_after(item, first, second):
    return box_of(item, second).top() - box_of(item, first).bottom()


def press(item, key, typed='', modifiers=Qt.KeyboardModifier.NoModifier):
    item.sceneEvent(QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress, key, modifiers, typed))


def ctrl_z(item):
    press(item, Qt.Key.Key_Z, '', Qt.KeyboardModifier.ControlModifier)


def lines_of(item):
    return item.toPlainText().split('\n')


def at_end_of(item, text):
    cursor = item.textCursor()
    block = block_of(item, text)
    cursor.setPosition(block.position() + block.length() - 1)
    item.setTextCursor(cursor)


# How it looks

def test_a_note_has_its_lines_together_until_asked(view):
    item = note(view, ['one', 'two'])
    assert item.lines_spaced is False
    assert gap_after(item, 'one', 'two') == pytest.approx(0, abs=0.5)


def test_they_stand_as_far_apart_as_with_an_empty_line_between(view):
    spaced = note(view, ['one', 'two', 'three'], tasks=False)
    spaced.set_lines_spaced(True)
    written = note(view, ['one', '', 'two', '', 'three'], tasks=False)
    assert spaced.text_rect().height() == pytest.approx(
        written.text_rect().height(), abs=1)
    assert box_of(spaced, 'three').top() == pytest.approx(
        box_of(written, 'three').top(), abs=1)


def test_tasks_stand_apart_too(view):
    item = note(view, ['one', 'two', 'three'])
    line = box_of(item, 'one').height()
    item.set_lines_spaced(True)
    assert gap_after(item, 'one', 'two') == pytest.approx(line, abs=1)
    assert gap_after(item, 'two', 'three') == pytest.approx(line, abs=1)


def test_no_line_is_added_or_taken_away(view):
    item = note(view, ['one', 'two', 'three'])
    before = item.toPlainText()
    item.set_lines_spaced(True)
    assert item.toPlainText() == before


def test_the_note_does_not_grow_under_its_last_line(view):
    item = note(view, ['one', 'two'], tasks=False)
    margin = item.document().documentMargin()
    item.set_lines_spaced(True)
    assert item.text_rect().bottom() == pytest.approx(
        box_of(item, 'two').bottom() + margin, abs=1)


def test_the_gap_is_as_big_as_the_letters_above_it(view):
    item = note(view, ['big', 'small', 'end'], tasks=False)
    cursor = QtGui.QTextCursor(block_of(item, 'big'))
    cursor.select(QtGui.QTextCursor.SelectionType.BlockUnderCursor)
    fmt = QtGui.QTextCharFormat()
    fmt.setFontPointSize(40)
    cursor.mergeCharFormat(fmt)
    item.set_lines_spaced(True)
    assert gap_after(item, 'big', 'small') > 2 * gap_after(
        item, 'small', 'end')


def test_a_wrapped_line_takes_one_line_of_room(view):
    words = 'many words that wrap round ' * 8
    item = note(view, [words.strip(), 'next'], tasks=False, text_width=200)
    line = box_of(item, 'next').height()
    item.set_lines_spaced(True)
    assert gap_after(item, words.strip(), 'next') == pytest.approx(
        line, abs=1)


def test_a_table_keeps_to_its_rows(view):
    item = note(view, ['before', 'after'], tasks=False)
    cursor = QtGui.QTextCursor(block_of(item, 'before'))
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
    table = cursor.insertTable(2, 2)
    item.set_lines_spaced(True)
    cell = table.cellAt(0, 0).firstCursorPosition().block()
    assert cell.blockFormat().bottomMargin() == 0
    assert block_of(item, 'after').blockFormat().bottomMargin() == 0


# With finished tasks

def tasks_ticked(view):
    item = note(view, ['one', 'two', 'three'])
    item.set_lines_spaced(True)
    item.change_task(block_of(item, 'three'), True)
    return item


def test_their_strip_stays_close_under_the_last_line_in_sight(view):
    item = tasks_ticked(view)
    assert item.tasks_collapsed
    # No room kept for lines out of sight: the strip is where it was
    assert block_of(item, 'two').blockFormat().bottomMargin() == 0
    margin = item.document().documentMargin()
    assert item.done_bar_rect().top() == pytest.approx(
        box_of(item, 'two').bottom() + margin, abs=1)


def test_opened_out_the_strip_has_its_room_and_they_stand_apart(view):
    item = note(view, ['one', 'two', 'three', 'four'])
    item.set_lines_spaced(True)
    item.change_task(block_of(item, 'three'), True)
    item.change_task(block_of(item, 'four'), True)
    item.set_tasks_collapsed(False)
    strip = item.done_bar_rect()
    assert strip.top() >= box_of(item, 'two').bottom() - 0.5
    assert strip.bottom() <= box_of(item, 'three').top() + 0.5
    line = box_of(item, 'one').height()
    assert gap_after(item, 'three', 'four') == pytest.approx(line, abs=1)
    item.set_tasks_collapsed(True)
    assert block_of(item, 'two').blockFormat().bottomMargin() == 0


def test_ticking_leaves_the_rest_apart(view):
    item = tasks_ticked(view)
    line = box_of(item, 'one').height()
    assert gap_after(item, 'one', 'two') == pytest.approx(line, abs=1)
    item.change_task(block_of(item, 'three'), False)
    assert gap_after(item, 'one', 'two') == pytest.approx(line, abs=1)
    assert gap_after(item, 'two', 'three') == pytest.approx(line, abs=1)


# Dragging and ticking find the right line in the room between

def mouse(pos):
    event = MagicMock()
    event.pos.return_value = pos
    event.scenePos.return_value = pos
    event.button.return_value = Qt.MouseButton.LeftButton
    event.buttons.return_value = Qt.MouseButton.LeftButton
    event.modifiers.return_value = Qt.KeyboardModifier.NoModifier
    return event


def test_a_task_is_dragged_past_the_others_by_its_grip(view):
    item = note(view, ['one', 'two', 'three', 'four'])
    item.set_lines_spaced(True)
    rect = box_of(item, 'one')
    grip = None
    for x in range(-5, 60):
        point = QtCore.QPointF(rect.left() + x, rect.center().y())
        if item.task_grip_at(point) is not None:
            grip = point
            break
    assert grip is not None
    item.mousePressEvent(mouse(grip))
    item.mouseMoveEvent(mouse(QtCore.QPointF(
        grip.x(), box_of(item, 'three').bottom() + 3)))
    item.mouseReleaseEvent(mouse(QtCore.QPointF(
        grip.x(), box_of(item, 'three').bottom() + 3)))
    assert lines_of(item) == ['two', 'three', 'one', 'four']
    # And it stands apart like the rest where it landed, with the last
    # line still having none under it
    line = box_of(item, 'two').height()
    assert gap_after(item, 'three', 'one') == pytest.approx(line, abs=1)
    assert block_of(item, 'four').blockFormat().bottomMargin() == 0


# Writing

def test_new_lines_stand_apart_as_they_are_written(view):
    item = note(view, ['one'])
    item.set_lines_spaced(True)
    item.enter_edit_mode()
    at_end_of(item, 'one')
    line = box_of(item, 'one').height()
    press(item, Qt.Key.Key_Return, '\r')
    press(item, Qt.Key.Key_A, 'a')
    assert lines_of(item) == ['one', 'a']
    assert gap_after(item, 'one', 'a') == pytest.approx(line, abs=1)
    assert block_of(item, 'a').blockFormat().bottomMargin() == 0
    item.exit_edit_mode()


def test_undoing_while_writing_takes_the_new_line_with_its_room(view):
    item = note(view, ['one'], tasks=False)
    item.set_lines_spaced(True)
    item.enter_edit_mode()
    at_end_of(item, 'one')
    press(item, Qt.Key.Key_Return, '\r')
    assert lines_of(item) == ['one', '']
    ctrl_z(item)
    assert lines_of(item) == ['one']
    assert block_of(item, 'one').blockFormat().bottomMargin() == 0
    # And brought back again, not lost to putting the room back
    press(item, Qt.Key.Key_Z, '', Qt.KeyboardModifier.ControlModifier
          | Qt.KeyboardModifier.ShiftModifier)
    assert lines_of(item) == ['one', '']
    item.exit_edit_mode()


def test_writing_many_lines_can_all_be_undone(view):
    item = note(view, ['one'], tasks=False)
    item.set_lines_spaced(True)
    item.enter_edit_mode()
    at_end_of(item, 'one')
    for letter in 'abc':
        press(item, Qt.Key.Key_Return, '\r')
        press(item, Qt.Key.Key_A, letter)
    assert lines_of(item) == ['one', 'a', 'b', 'c']
    for _ in range(12):
        ctrl_z(item)
    assert lines_of(item) == ['one']
    item.exit_edit_mode()


def test_writing_thrown_away_leaves_it_as_it_was(view):
    item = note(view, ['one', 'two'])
    item.set_lines_spaced(True)
    before = item.text_rect().height()
    item.enter_edit_mode()
    at_end_of(item, 'two')
    press(item, Qt.Key.Key_Return, '\r')
    press(item, Qt.Key.Key_Escape)
    assert lines_of(item) == ['one', 'two']
    assert item.text_rect().height() == pytest.approx(before, abs=1)


def test_closed_up_while_writing_then_thrown_away_leaves_no_room(view):
    """The text put back has the room in it; the note no longer has it."""

    item = note(view, ['one', 'two'])
    item.set_lines_spaced(True)
    item.enter_edit_mode()
    item.set_lines_spaced(False)
    press(item, Qt.Key.Key_Escape)
    assert block_of(item, 'one').blockFormat().bottomMargin() == 0


# Asked for

def test_the_button_stands_the_lines_apart_and_undo_takes_it_back(view):
    item = note(view, ['one', 'two'])
    before = item.text_rect().height()
    view.scene.clearSelection()
    item.setSelected(True)
    view.on_action_text_line_spacing()
    assert item.lines_spaced is True
    assert item.text_rect().height() > before
    assert view.text_toolbar.line_spacing.isChecked()
    view.undo_stack.undo()
    assert item.lines_spaced is False
    assert item.text_rect().height() == pytest.approx(before, abs=0.5)
    view.update_text_toolbar()
    assert not view.text_toolbar.line_spacing.isChecked()
    view.undo_stack.redo()
    assert item.lines_spaced is True


def test_the_button_closes_them_up_again(view):
    item = note(view, ['one', 'two'])
    before = item.text_rect().height()
    view.scene.clearSelection()
    item.setSelected(True)
    view.on_action_text_line_spacing()
    view.on_action_text_line_spacing()
    assert item.lines_spaced is False
    assert item.text_rect().height() == pytest.approx(before, abs=0.5)
    assert block_of(item, 'one').blockFormat().bottomMargin() == 0


def test_the_button_works_on_the_note_being_written(view):
    item = note(view, ['one', 'two'])
    view.scene.clearSelection()
    item.setSelected(True)
    item.enter_edit_mode()
    view.on_action_text_line_spacing()
    assert item.lines_spaced is True
    assert gap_after(item, 'one', 'two') > 0
    item.exit_edit_mode()


def test_notes_chosen_together_end_up_alike(view):
    first = note(view, ['one', 'two'])
    second = note(view, ['three', 'four'])
    second.set_lines_spaced(True)
    view.scene.clearSelection()
    first.setSelected(True)
    second.setSelected(True)
    wanted = not view.scene.selected_text_items()[0].lines_spaced
    view.on_action_text_line_spacing()
    assert first.lines_spaced is wanted
    assert second.lines_spaced is wanted


def test_a_note_without_tasks_can_be_spaced_as_well(view):
    item = note(view, ['one', 'two'], tasks=False)
    view.scene.clearSelection()
    item.setSelected(True)
    view.on_action_text_line_spacing()
    assert gap_after(item, 'one', 'two') > 0


def test_a_pinned_note_makes_room_in_the_tab(view):
    first = note(view, ['one', 'two', 'three'])
    second = note(view, ['below'])
    view.pin_notes([first, second])
    QtCore.QCoreApplication.processEvents()
    view.place_pinned_notes()
    before = second.scenePos().y()
    commands.ChangeLineSpacing([first], True).redo()
    QtCore.QCoreApplication.processEvents()
    view.place_pinned_notes()
    assert second.scenePos().y() != before
    first_bottom = first.mapToScene(first.pin_rect().bottomLeft()).y()
    assert second.mapToScene(second.pin_rect().topLeft()).y() >= first_bottom


# Kept

def test_it_is_kept_with_the_board(view, tmpdir):
    item = note(view, ['one', 'two', 'three'])
    item.set_lines_spaced(True)
    height = item.text_rect().height()
    path = os.path.join(tmpdir, 'board.blk')
    SQLiteIO(path, view.scene, create_new=True).write()
    scene = BeeGraphicsScene(QtGui.QUndoStack())
    SQLiteIO(path, scene, readonly=True).read()
    scene.add_queued_items()
    read = next(scene.items_by_type('text'))
    assert read.lines_spaced is True
    assert read.text_rect().height() == pytest.approx(height, abs=1)
    # Closed up, it is closed up for good
    read.set_lines_spaced(False)
    assert read.text_rect().height() < height - 5


def test_a_note_not_spaced_saves_as_it_did(view):
    item = note(view, ['one', 'two'])
    assert 'lines_spaced' not in item.get_extra_save_data()
    item.set_lines_spaced(True)
    assert item.get_extra_save_data()['lines_spaced'] is True
    item.set_lines_spaced(False)
    assert 'lines_spaced' not in item.get_extra_save_data()


def test_a_copy_stands_apart_too(view):
    item = note(view, ['one', 'two'])
    item.set_lines_spaced(True)
    copy = item.create_copy()
    assert copy.lines_spaced is True
    assert gap_after(copy, 'one', 'two') > 0


def test_a_version_that_knows_nothing_of_it_still_shows_it(view):
    """The room is in the text, which is all it reads."""

    item = note(view, ['one', 'two'], tasks=False)
    item.set_lines_spaced(True)
    read = QtGui.QTextDocument()
    read.setHtml(item.toHtml())
    assert read.begin().blockFormat().bottomMargin() > 0
    assert read.lastBlock().blockFormat().bottomMargin() == 0


def test_room_that_came_back_with_the_text_goes_if_the_note_is_not_spaced(
        view):
    """A file saved by such a version has the room, but says nothing of
    the note being spaced: it opens closed up."""

    item = note(view, ['one', 'two'], tasks=False)
    item.set_lines_spaced(True)
    read = BeeTextItem(html=item.toHtml())
    assert read.lines_spaced is False
    assert gap_after(read, 'one', 'two') == pytest.approx(0, abs=0.5)


def test_a_lines_own_room_is_kept_when_it_is_not_of_this_size(view):
    item = note(view, ['pasted', 'next'], tasks=False)
    fmt = block_of(item, 'pasted').blockFormat()
    fmt.setBottomMargin(3)
    QtGui.QTextCursor(block_of(item, 'pasted')).setBlockFormat(fmt)
    item.refresh_tasks()
    assert block_of(item, 'pasted').blockFormat().bottomMargin() == 3
