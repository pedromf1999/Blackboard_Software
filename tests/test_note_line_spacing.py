"""Lines of a note stood apart, as if with an empty line after each: the
lines chosen while writing, or the whole of a note chosen on the board."""

import os
from unittest.mock import MagicMock

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
import pytest

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


def spaced(item, *texts):
    return [item.line_is_spaced(block_of(item, text)) for text in texts]


def space(item, *texts):
    item.space_lines([block_of(item, text).position() for text in texts], True)


def space_all(item):
    item.space_lines(item.all_lines(), True)


def at_end_of(item, text):
    cursor = item.textCursor()
    block = block_of(item, text)
    cursor.setPosition(block.position() + block.length() - 1)
    item.setTextCursor(cursor)


def select(item, first, last):
    """From inside one line to inside another: part of the words."""

    cursor = item.textCursor()
    cursor.setPosition(block_of(item, first).position() + 1)
    cursor.setPosition(block_of(item, last).position() + 1,
                       QtGui.QTextCursor.MoveMode.KeepAnchor)
    item.setTextCursor(cursor)


def writing(view, item):
    view.scene.clearSelection()
    item.setSelected(True)
    item.enter_edit_mode()


def on_board(view, *items):
    view.scene.clearSelection()
    for item in items:
        item.setSelected(True)


# Only what is chosen

def test_a_selection_spaces_the_lines_it_touches_and_no_others(view):
    item = note(view, ['one', 'two', 'three', 'four', 'five'])
    line = box_of(item, 'one').height()
    writing(view, item)
    select(item, 'two', 'three')
    view.on_action_text_line_spacing()
    assert gap_after(item, 'one', 'two') == pytest.approx(0, abs=0.5)
    assert gap_after(item, 'two', 'three') == pytest.approx(line, abs=1)
    assert gap_after(item, 'three', 'four') == pytest.approx(line, abs=1)
    assert gap_after(item, 'four', 'five') == pytest.approx(0, abs=0.5)
    item.exit_edit_mode()


def test_part_of_a_line_counts_for_the_line(view):
    item = note(view, ['one', 'two', 'three'], tasks=False)
    writing(view, item)
    select(item, 'one', 'one')
    cursor = item.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(2, QtGui.QTextCursor.MoveMode.KeepAnchor)
    item.setTextCursor(cursor)
    view.on_action_text_line_spacing()
    assert spaced(item, 'one', 'two', 'three') == [True, False, False]
    item.exit_edit_mode()


def test_with_nothing_selected_it_is_the_line_of_the_cursor(view):
    item = note(view, ['one', 'two', 'three'])
    writing(view, item)
    at_end_of(item, 'two')
    view.on_action_text_line_spacing()
    assert spaced(item, 'one', 'two', 'three') == [False, True, False]
    item.exit_edit_mode()


def test_the_selection_stays_selected_to_be_pressed_again(view):
    item = note(view, ['one', 'two', 'three'])
    writing(view, item)
    select(item, 'one', 'two')
    view.on_action_text_line_spacing()
    assert item.textCursor().hasSelection()
    assert item.chosen_lines() == [block_of(item, 'one').position(),
                                   block_of(item, 'two').position()]
    item.exit_edit_mode()


def test_pressed_again_they_close_up_and_the_others_stay(view):
    item = note(view, ['one', 'two', 'three', 'four'])
    space(item, 'three')
    writing(view, item)
    select(item, 'one', 'two')
    view.on_action_text_line_spacing()
    view.on_action_text_line_spacing()
    assert spaced(item, 'one', 'two', 'three') == [False, False, True]
    assert gap_after(item, 'one', 'two') == pytest.approx(0, abs=0.5)
    item.exit_edit_mode()


def test_a_selection_only_part_spaced_is_spaced_first(view):
    item = note(view, ['one', 'two', 'three'])
    space(item, 'one')
    writing(view, item)
    select(item, 'one', 'two')
    view.on_action_text_line_spacing()
    assert spaced(item, 'one', 'two') == [True, True]
    item.exit_edit_mode()


def test_chosen_on_the_board_it_is_the_whole_note(view):
    item = note(view, ['one', 'two', 'three'])
    on_board(view, item)
    view.on_action_text_line_spacing()
    assert spaced(item, 'one', 'two', 'three') == [True, True, True]
    view.on_action_text_line_spacing()
    assert spaced(item, 'one', 'two', 'three') == [False, False, False]
    assert gap_after(item, 'one', 'two') == pytest.approx(0, abs=0.5)


def test_on_the_board_a_note_part_spaced_is_spaced_whole_first(view):
    item = note(view, ['one', 'two', 'three'])
    space(item, 'two')
    on_board(view, item)
    view.on_action_text_line_spacing()
    assert spaced(item, 'one', 'two', 'three') == [True, True, True]


def test_notes_chosen_together_end_up_alike(view):
    first = note(view, ['one', 'two'])
    second = note(view, ['three', 'four'])
    space_all(second)
    on_board(view, first, second)
    wanted = not view.scene.selected_text_items()[0].lines_are_spaced(
        view.scene.selected_text_items()[0].all_lines())
    view.on_action_text_line_spacing()
    assert spaced(first, 'one', 'two') == [wanted, wanted]
    assert spaced(second, 'three', 'four') == [wanted, wanted]


def test_undo_takes_back_only_that(view):
    item = note(view, ['one', 'two', 'three'])
    space(item, 'three')
    writing(view, item)
    select(item, 'one', 'one')
    view.on_action_text_line_spacing()
    item.exit_edit_mode()
    view.undo_stack.undo()
    view.undo_stack.undo()
    assert spaced(item, 'one', 'three') == [False, True]
    view.undo_stack.redo()
    view.undo_stack.redo()
    assert spaced(item, 'one', 'three') == [True, True]


# The button says which

def test_the_button_is_pressed_on_a_spaced_line_and_not_on_another(view):
    item = note(view, ['one', 'two', 'three'])
    space(item, 'two')
    writing(view, item)
    button = view.text_toolbar.line_spacing
    at_end_of(item, 'two')
    item.cursor_may_have_moved()
    assert button.isChecked()
    at_end_of(item, 'one')
    item.cursor_may_have_moved()
    assert not button.isChecked()
    select(item, 'one', 'two')
    item.cursor_may_have_moved()
    assert not button.isChecked()
    item.exit_edit_mode()


def test_the_button_on_the_board_says_for_the_whole_note(view):
    item = note(view, ['one', 'two'])
    on_board(view, item)
    button = view.text_toolbar.line_spacing
    space(item, 'one')
    view.update_text_toolbar()
    assert not button.isChecked()
    view.on_action_text_line_spacing()
    assert button.isChecked()
    view.undo_stack.undo()
    view.update_text_toolbar()
    assert not button.isChecked()


# How it looks

def test_a_note_has_its_lines_together_until_asked(view):
    item = note(view, ['one', 'two'])
    assert spaced(item, 'one', 'two') == [False, False]
    assert gap_after(item, 'one', 'two') == pytest.approx(0, abs=0.5)


def test_they_stand_as_far_apart_as_with_an_empty_line_between(view):
    item = note(view, ['one', 'two', 'three'], tasks=False)
    space_all(item)
    written = note(view, ['one', '', 'two', '', 'three'], tasks=False)
    assert item.text_rect().height() == pytest.approx(
        written.text_rect().height(), abs=1)
    assert box_of(item, 'three').top() == pytest.approx(
        box_of(written, 'three').top(), abs=1)


def test_no_line_is_added_or_taken_away(view):
    item = note(view, ['one', 'two', 'three'])
    before = item.toPlainText()
    space_all(item)
    assert item.toPlainText() == before


def test_the_note_does_not_grow_under_its_last_line(view):
    item = note(view, ['one', 'two'], tasks=False)
    margin = item.document().documentMargin()
    space_all(item)
    assert item.text_rect().bottom() == pytest.approx(
        box_of(item, 'two').bottom() + margin, abs=1)


def test_the_last_line_has_its_room_once_another_comes_after_it(view):
    item = note(view, ['one', 'two'], tasks=False)
    space(item, 'two')
    assert block_of(item, 'two').blockFormat().bottomMargin() == 0
    line = box_of(item, 'two').height()
    writing(view, item)
    at_end_of(item, 'two')
    press(item, Qt.Key.Key_Return, '\r')
    press(item, Qt.Key.Key_A, 'a')
    assert gap_after(item, 'two', 'a') == pytest.approx(line, abs=1)
    item.exit_edit_mode()


def test_the_gap_is_as_big_as_the_letters_above_it(view):
    item = note(view, ['big', 'small', 'end'], tasks=False)
    cursor = QtGui.QTextCursor(block_of(item, 'big'))
    cursor.select(QtGui.QTextCursor.SelectionType.BlockUnderCursor)
    fmt = QtGui.QTextCharFormat()
    fmt.setFontPointSize(40)
    cursor.mergeCharFormat(fmt)
    space_all(item)
    assert gap_after(item, 'big', 'small') > 2 * gap_after(
        item, 'small', 'end')


def test_the_gap_follows_when_the_letters_change_size(view):
    item = note(view, ['one', 'two'], tasks=False)
    space_all(item)
    before = gap_after(item, 'one', 'two')
    on_board(view, item)
    view.scale_selected_text(2)
    assert gap_after(item, 'one', 'two') > 1.5 * before
    assert spaced(item, 'one', 'two') == [True, True]


def test_a_wrapped_line_takes_one_line_of_room(view):
    words = 'many words that wrap round ' * 8
    item = note(view, [words.strip(), 'next'], tasks=False, text_width=200)
    line = box_of(item, 'next').height()
    space_all(item)
    assert gap_after(item, words.strip(), 'next') == pytest.approx(
        line, abs=1)


def test_a_table_keeps_to_its_rows(view):
    item = note(view, ['before', 'after'], tasks=False)
    cursor = QtGui.QTextCursor(block_of(item, 'before'))
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock)
    table = cursor.insertTable(2, 2)
    space_all(item)
    cell = table.cellAt(0, 0).firstCursorPosition().block()
    assert cell.blockFormat().bottomMargin() == 0
    assert cell.userState() != item.LINE_SPACED


# With finished tasks

def test_a_ticked_task_takes_its_mark_and_the_one_above_keeps_its_own(view):
    item = note(view, ['one', 'two', 'three', 'four'])
    space(item, 'two')
    item.change_task(block_of(item, 'two'), True)
    assert lines_of(item) == ['one', 'three', 'four', 'two']
    assert spaced(item, 'one', 'three', 'four', 'two') == [
        False, False, False, True]
    item.change_task(block_of(item, 'two'), False)
    assert lines_of(item) == ['one', 'two', 'three', 'four']
    assert spaced(item, 'one', 'two', 'three', 'four') == [
        False, True, False, False]


def test_a_line_not_spaced_does_not_take_the_mark_of_the_one_below(view):
    item = note(view, ['one', 'two', 'three'])
    space(item, 'one')
    item.change_task(block_of(item, 'two'), True)
    assert spaced(item, 'one', 'three', 'two') == [True, False, False]


def test_the_top_task_ticked_off_leaves_the_others_as_they_were(view):
    item = note(view, ['one', 'two', 'three'])
    space(item, 'one')
    item.change_task(block_of(item, 'one'), True)
    assert lines_of(item) == ['two', 'three', 'one']
    assert spaced(item, 'two', 'three', 'one') == [False, False, True]


def test_put_back_at_the_top_each_keeps_its_own(view):
    item = note(view, ['one', 'two', 'three'])
    space(item, 'two')
    item.change_task(block_of(item, 'one'), True)
    assert lines_of(item)[0] == 'two'
    item.change_task(block_of(item, 'one'), False)
    assert lines_of(item) == ['one', 'two', 'three']
    assert spaced(item, 'one', 'two', 'three') == [False, True, False]


def test_their_strip_stays_close_under_the_last_line_in_sight(view):
    item = note(view, ['one', 'two', 'three'])
    space_all(item)
    item.change_task(block_of(item, 'three'), True)
    assert item.tasks_collapsed
    assert block_of(item, 'two').blockFormat().bottomMargin() == 0
    margin = item.document().documentMargin()
    assert item.done_bar_rect().top() == pytest.approx(
        box_of(item, 'two').bottom() + margin, abs=1)


def test_opened_out_the_strip_has_its_room_and_they_stand_apart(view):
    item = note(view, ['one', 'two', 'three', 'four'])
    space_all(item)
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


# Dragging a task

def mouse(pos):
    event = MagicMock()
    event.pos.return_value = pos
    event.scenePos.return_value = pos
    event.button.return_value = Qt.MouseButton.LeftButton
    event.buttons.return_value = Qt.MouseButton.LeftButton
    event.modifiers.return_value = Qt.KeyboardModifier.NoModifier
    return event


def drag_below(item, text, below):
    rect = box_of(item, text)
    grip = None
    for x in range(-5, 60):
        point = QtCore.QPointF(rect.left() + x, rect.center().y())
        if item.task_grip_at(point) is not None:
            grip = point
            break
    assert grip is not None
    to = QtCore.QPointF(grip.x(), box_of(item, below).bottom() + 3)
    item.mousePressEvent(mouse(grip))
    item.mouseMoveEvent(mouse(to))
    item.mouseReleaseEvent(mouse(to))


def test_a_task_dragged_takes_its_mark_with_it(view):
    item = note(view, ['one', 'two', 'three', 'four'])
    space(item, 'one')
    drag_below(item, 'one', 'three')
    assert lines_of(item) == ['two', 'three', 'one', 'four']
    assert spaced(item, 'two', 'three', 'one', 'four') == [
        False, False, True, False]
    line = box_of(item, 'two').height()
    assert gap_after(item, 'one', 'four') == pytest.approx(line, abs=1)
    assert gap_after(item, 'two', 'three') == pytest.approx(0, abs=0.5)


def test_tasks_all_spaced_are_dragged_as_ever(view):
    item = note(view, ['one', 'two', 'three', 'four'])
    space_all(item)
    drag_below(item, 'one', 'three')
    assert lines_of(item) == ['two', 'three', 'one', 'four']
    assert all(spaced(item, 'two', 'three', 'one', 'four'))
    assert block_of(item, 'four').blockFormat().bottomMargin() == 0


# Writing

def test_a_new_line_stands_apart_like_the_one_it_came_from(view):
    item = note(view, ['one'])
    space_all(item)
    writing(view, item)
    at_end_of(item, 'one')
    line = box_of(item, 'one').height()
    press(item, Qt.Key.Key_Return, '\r')
    press(item, Qt.Key.Key_A, 'a')
    press(item, Qt.Key.Key_Return, '\r')
    press(item, Qt.Key.Key_B, 'b')
    assert lines_of(item) == ['one', 'a', 'b']
    assert gap_after(item, 'one', 'a') == pytest.approx(line, abs=1)
    assert gap_after(item, 'a', 'b') == pytest.approx(line, abs=1)
    assert spaced(item, 'b') == [True]
    assert block_of(item, 'b').blockFormat().bottomMargin() == 0
    item.exit_edit_mode()


def test_a_new_line_after_one_not_spaced_is_not(view):
    item = note(view, ['one', 'two'], tasks=False)
    space(item, 'two')
    writing(view, item)
    at_end_of(item, 'one')
    press(item, Qt.Key.Key_Return, '\r')
    press(item, Qt.Key.Key_A, 'a')
    assert lines_of(item) == ['one', 'a', 'two']
    assert spaced(item, 'one', 'a', 'two') == [False, False, True]
    item.exit_edit_mode()


def test_a_line_split_in_two_has_both_parts_apart(view):
    item = note(view, ['onetwo', 'next'], tasks=False)
    space(item, 'onetwo')
    writing(view, item)
    cursor = item.textCursor()
    cursor.setPosition(3)
    item.setTextCursor(cursor)
    press(item, Qt.Key.Key_Return, '\r')
    assert lines_of(item) == ['one', 'two', 'next']
    assert spaced(item, 'one', 'two', 'next') == [True, True, False]
    item.exit_edit_mode()


def test_lines_pasted_into_one_that_stands_apart_stand_apart(view, qapp):
    item = note(view, ['one', 'last'], tasks=False)
    space(item, 'one')
    writing(view, item)
    at_end_of(item, 'one')
    mimedata = QtCore.QMimeData()
    mimedata.setHtml('<p>first</p><p>second</p><p>third</p>')
    clipboard = MagicMock()
    clipboard.mimeData.return_value = mimedata
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr('PyQt6.QtWidgets.QApplication.clipboard',
                      lambda: clipboard)
        press(item, Qt.Key.Key_V, '', Qt.KeyboardModifier.ControlModifier)
    pasted = lines_of(item)
    assert 'second' in pasted and 'third' in pasted
    assert spaced(item, 'second', 'third') == [True, True]
    assert spaced(item, 'last') == [False]
    item.exit_edit_mode()


def test_undoing_while_writing_takes_the_new_line_with_its_room(view):
    item = note(view, ['one'], tasks=False)
    space_all(item)
    writing(view, item)
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
    space_all(item)
    writing(view, item)
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
    item = note(view, ['one', 'two', 'three'])
    space(item, 'one')
    before = item.text_rect().height()
    writing(view, item)
    at_end_of(item, 'three')
    press(item, Qt.Key.Key_Return, '\r')
    press(item, Qt.Key.Key_Escape)
    assert lines_of(item) == ['one', 'two', 'three']
    assert spaced(item, 'one', 'two') == [True, False]
    assert item.text_rect().height() == pytest.approx(before, abs=1)


def test_a_note_with_none_spaced_is_left_alone_as_it_is_written(view):
    item = note(view, ['one'], tasks=False)
    writing(view, item)
    at_end_of(item, 'one')
    press(item, Qt.Key.Key_Return, '\r')
    press(item, Qt.Key.Key_A, 'a')
    assert spaced(item, 'one', 'a') == [False, False]
    item.exit_edit_mode()


# Pinned

def test_a_pinned_note_makes_room_in_the_tab(view):
    first = note(view, ['one', 'two', 'three'])
    second = note(view, ['below'])
    view.pin_notes([first, second])
    QtCore.QCoreApplication.processEvents()
    view.place_pinned_notes()
    before = second.scenePos().y()
    on_board(view, first)
    view.on_action_text_line_spacing()
    QtCore.QCoreApplication.processEvents()
    view.place_pinned_notes()
    assert second.scenePos().y() != before
    first_bottom = first.mapToScene(first.pin_rect().bottomLeft()).y()
    assert second.mapToScene(second.pin_rect().topLeft()).y() >= first_bottom


# Kept

def saved_and_read(view, tmpdir):
    path = os.path.join(tmpdir, 'board.blk')
    SQLiteIO(path, view.scene, create_new=True).write()
    scene = BeeGraphicsScene(QtGui.QUndoStack())
    SQLiteIO(path, scene, readonly=True).read()
    scene.add_queued_items()
    # What is on a scene goes with it
    view.scene_read_back = scene
    return next(scene.items_by_type('text'))


def test_each_line_is_kept_as_it_is_with_the_board(view, tmpdir):
    item = note(view, ['one', 'two', 'three', 'four'])
    space(item, 'two', 'four')
    height = item.text_rect().height()
    read = saved_and_read(view, tmpdir)
    assert spaced(read, 'one', 'two', 'three', 'four') == [
        False, True, False, True]
    assert read.text_rect().height() == pytest.approx(height, abs=1)


def test_a_last_line_keeps_its_mark_in_the_file(view, tmpdir):
    """It has no room to show for it, being the last."""

    item = note(view, ['one', 'two'], tasks=False)
    space(item, 'two')
    read = saved_and_read(view, tmpdir)
    assert spaced(read, 'one', 'two') == [False, True]


def test_finished_tasks_folded_away_keep_theirs(view, tmpdir):
    item = note(view, ['one', 'two', 'three'])
    space(item, 'two')
    item.change_task(block_of(item, 'two'), True)
    read = saved_and_read(view, tmpdir)
    read.set_tasks_collapsed(False)
    assert spaced(read, 'one', 'three', 'two') == [False, False, True]


def test_closed_up_after_reading_it_is_closed_up_for_good(view, tmpdir):
    item = note(view, ['one', 'two', 'three'])
    space_all(item)
    read = saved_and_read(view, tmpdir)
    height = read.text_rect().height()
    read.space_lines(read.all_lines(), False)
    assert read.text_rect().height() < height - 5
    assert '-qt-user-state' not in read.toHtml()


def test_a_note_with_none_saves_as_it_did(view):
    item = note(view, ['one', 'two'])
    html = item.toHtml()
    assert '-qt-user-state' not in html
    assert 'lines_spaced' not in item.get_extra_save_data()
    space_all(item)
    item.space_lines(item.all_lines(), False)
    assert item.toHtml() == html


def test_a_copy_has_the_same_lines_apart(view):
    item = note(view, ['one', 'two', 'three'])
    space(item, 'two')
    copy = item.create_copy()
    assert spaced(copy, 'one', 'two', 'three') == [False, True, False]
    assert gap_after(copy, 'two', 'three') > 0


def test_a_version_that_knows_nothing_of_it_still_shows_it(view):
    """The room is in the text, and so is the mark, for when it comes
    back."""

    item = note(view, ['one', 'two'], tasks=False)
    space_all(item)
    read = QtGui.QTextDocument()
    read.setHtml(item.toHtml())
    assert read.begin().blockFormat().bottomMargin() > 0
    assert read.lastBlock().blockFormat().bottomMargin() == 0
    assert read.lastBlock().userState() == item.LINE_SPACED


def test_a_note_saved_when_only_whole_notes_could_be_spaced(view):
    item = BeeTextItem('one\ntwo', lines_spaced=True)
    view.scene.addItem(item)
    assert spaced(item, 'one', 'two') == [True, True]
    assert gap_after(item, 'one', 'two') > 0


def test_a_lines_own_room_is_kept_when_it_is_not_of_this_size(view):
    item = note(view, ['pasted', 'next'], tasks=False)
    fmt = block_of(item, 'pasted').blockFormat()
    fmt.setBottomMargin(3)
    QtGui.QTextCursor(block_of(item, 'pasted')).setBlockFormat(fmt)
    item.refresh_tasks()
    assert block_of(item, 'pasted').blockFormat().bottomMargin() == 3
    assert spaced(item, 'pasted') == [False]
