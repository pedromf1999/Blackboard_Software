"""Task lists: notes whose lines carry a box to tick off."""

from unittest.mock import MagicMock

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref.actions.actions import actions
from beeref.items import BeeTextItem


def press(item, key, text='', modifier=Qt.KeyboardModifier.NoModifier):
    item.sceneEvent(QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, key,
                                    modifier, text))


KEYS = {
    '\n': (Qt.Key.Key_Return, '\r'),
    ' ': (Qt.Key.Key_Space, ' '),
    '-': (Qt.Key.Key_Minus, '-'),
}


def type_text(item, text):
    for char in text:
        key, typed = KEYS.get(char, (Qt.Key.Key_A, char))
        press(item, key, typed)


def task_note(view, lines='one\ntwo\nthree'):
    """A task list with a line for each of the given ones."""

    view.on_action_insert_tasks()
    item = view.scene.edit_item
    type_text(item, lines)
    return item


def blocks(item):
    result = []
    block = item.document().begin()
    while block.isValid():
        result.append(block)
        block = block.next()
    return result


def lines(item):
    """Each line's words, whether it is ticked, and whether it shows."""

    return [(block.text(), item.task_is_done(block), block.isVisible())
            for block in blocks(item)]


def click(item, pos, button=Qt.MouseButton.LeftButton):
    event = MagicMock()
    event.pos.return_value = pos
    event.button.return_value = button
    event.modifiers.return_value = Qt.KeyboardModifier.NoModifier
    item.mousePressEvent(event)
    return event


def test_the_shortcuts_are_the_ones_asked_for():
    assert actions['insert_tasks'].shortcuts == ['Ctrl+Shift+T']
    assert actions['insert_text'].shortcuts == ['Ctrl+T']
    assert actions['insert_table'].shortcuts == ['Alt+T']


def test_a_new_task_list_is_a_note_waiting_to_be_typed_into(view):
    view.on_action_insert_tasks()
    item = view.scene.edit_item

    assert isinstance(item, BeeTextItem)
    assert item.edit_mode is True
    assert item.has_tasks() is True
    assert lines(item) == [('', False, True)]


def test_enter_starts_the_next_task(view):
    item = task_note(view)

    assert [line[0] for line in lines(item)] == ['one', 'two', 'three']
    assert all(item.is_task(block) for block in blocks(item))


def test_ticking_a_task_off_drops_it_to_the_foot_and_strikes_it_through(view):
    item = task_note(view)

    item.set_task_done(blocks(item)[0], True)

    assert lines(item) == [('two', False, True), ('three', False, True),
                           ('one', True, False)]
    done = blocks(item)[-1]
    assert done.charFormat().fontStrikeOut() is True
    assert item.done_count() == 1


def test_the_finished_tasks_show_when_the_strip_is_opened(view):
    item = task_note(view)
    item.set_task_done(blocks(item)[0], True)

    item.set_tasks_collapsed(False)
    assert lines(item)[-1] == ('one', True, True)

    item.set_tasks_collapsed(True)
    assert lines(item)[-1] == ('one', True, False)


def test_unticking_a_task_puts_it_back_with_the_others(view):
    item = task_note(view)
    item.set_task_done(blocks(item)[0], True)

    item.set_task_done(blocks(item)[-1], False)

    assert lines(item) == [('two', False, True), ('three', False, True),
                           ('one', False, True)]
    assert blocks(item)[-1].charFormat().fontStrikeOut() is False
    assert item.done_count() == 0


def test_a_task_put_back_brings_no_gap_with_it(view):
    """Opened out, the first finished task keeps room above it for the
    strip. Put back on the list, it carried that room up with it, as a
    gap between the tasks still to do."""

    item = task_note(view)
    item.exit_edit_mode()
    height = item.boundingRect().height()
    item.set_task_done(blocks(item)[0], True)
    item.set_tasks_collapsed(False)

    item.set_task_done(blocks(item)[-1], False)

    assert [block.blockFormat().topMargin()
            for block in blocks(item)] == [0, 0, 0]
    assert item.boundingRect().height() == height


def test_unticking_the_only_task_left_puts_it_first(view):
    item = task_note(view, 'one\ntwo')
    for block in blocks(item):
        item.set_task_done(block, True)
    assert item.done_count() == 2

    item.set_task_done(blocks(item)[1], False)

    assert lines(item) == [('two', False, True), ('one', True, False)]


def test_the_words_keep_their_formatting_when_a_task_moves(view):
    item = task_note(view, 'one\ntwo')
    cursor = QtGui.QTextCursor(blocks(item)[0])
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfBlock,
                        QtGui.QTextCursor.MoveMode.KeepAnchor)
    bold = QtGui.QTextCharFormat()
    bold.setFontWeight(QtGui.QFont.Weight.Bold)
    cursor.mergeCharFormat(bold)

    item.set_task_done(blocks(item)[0], True)

    moved = blocks(item)[-1]
    fragment = next(iter([moved.begin().fragment()]))
    assert fragment.text() == 'one'
    assert fragment.charFormat().fontWeight() == QtGui.QFont.Weight.Bold


def test_clicking_the_box_ticks_the_task_off(view):
    item = task_note(view)
    item.exit_edit_mode()
    box = item.list_markers()[0]['box']

    click(item, box.center())

    assert lines(item)[-1] == ('one', True, False)


def test_clicking_the_start_of_the_words_ticks_nothing(view):
    """Qt ticks a box of its own where it believes the box to be, which
    in a note is the start of the words. Ticked that way, the words were
    not struck through and the line stayed among the ones still to do,
    with the strip of finished tasks drawn over it."""

    view.resize(800, 600)
    item = task_note(view)
    view.on_action_fit_scene()
    block = blocks(item)[1]
    layout = block.layout()
    line = layout.lineAt(0)
    point = QtCore.QPointF(
        layout.position().x() + line.naturalTextRect().left() + 4,
        layout.position().y() + line.y() + line.height() / 2)

    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier,
                     view.mapFromScene(item.mapToScene(point)))

    assert item.edit_mode is True
    assert item.done_count() == 0
    assert [item.task_is_done(b) for b in blocks(item)] == [
        False, False, False]


def test_clicking_the_box_of_a_finished_task_puts_it_back(view):
    item = task_note(view)
    item.exit_edit_mode()
    item.set_task_done(blocks(item)[0], True)
    item.set_tasks_collapsed(False)
    box = [marker for marker in item.list_markers()
           if marker['done']][0]['box']

    click(item, box.center())

    assert item.done_count() == 0


def test_ticking_a_task_off_is_one_step_that_can_be_undone(view):
    item = task_note(view)
    item.exit_edit_mode()
    before = view.undo_stack.count()
    box = item.list_markers()[0]['box']

    click(item, box.center())
    assert view.undo_stack.count() == before + 1

    view.undo_stack.undo()
    assert item.done_count() == 0
    assert [line[0] for line in lines(item)] == ['one', 'two', 'three']


def test_the_strip_can_be_pressed_in_both_states(view):
    """Opened out, the strip sits inside the words, and a rectangle
    inside another is a hole under Qt's usual fill rule: presses on it
    went straight through the note."""

    item = task_note(view)
    item.exit_edit_mode()
    item.set_task_done(blocks(item)[0], True)

    assert item.shape().contains(item.done_bar_rect().center()) is True

    item.set_tasks_collapsed(False)
    assert item.shape().contains(item.done_bar_rect().center()) is True


def test_dragging_on_from_a_box_does_not_take_the_note_with_it(view):
    """The press is answered by the box, so it never reaches the part
    that moves a note about -- which then had no drag to follow and
    raised an error on the first movement."""

    item = task_note(view)
    item.exit_edit_mode()
    item.setPos(0, 0)
    box = item.list_markers()[0]['box']
    click(item, box.center())

    move = MagicMock()
    move.pos.return_value = box.center() + QtCore.QPointF(40, 40)
    move.scenePos.return_value = QtCore.QPointF(40, 40)
    move.buttons.return_value = Qt.MouseButton.LeftButton
    move.modifiers.return_value = Qt.KeyboardModifier.NoModifier
    item.mouseMoveEvent(move)

    assert item.pos() == QtCore.QPointF(0, 0)

    release = MagicMock()
    release.button.return_value = Qt.MouseButton.LeftButton
    item.mouseReleaseEvent(release)
    assert item.pressed_on_task is False


def test_clicking_the_strip_opens_and_closes_it(view):
    item = task_note(view)
    item.exit_edit_mode()
    item.set_task_done(blocks(item)[0], True)
    assert item.tasks_collapsed is True

    click(item, item.done_bar_rect().center())
    assert item.tasks_collapsed is False

    click(item, item.done_bar_rect().center())
    assert item.tasks_collapsed is True


def test_the_strip_is_only_there_once_something_is_finished(view):
    item = task_note(view)

    assert item.shows_done_bar() is False
    height = item.boundingRect().height()

    item.set_task_done(blocks(item)[0], True)
    assert item.shows_done_bar() is True
    assert item.boundingRect().height() > height
    assert item.done_bar_text() == '1 completed'


def test_a_task_carries_a_box_where_a_list_carries_a_dash(view):
    tasks = task_note(view, 'one')
    tasks.exit_edit_mode()

    plain = BeeTextItem('')
    view.scene.addItem(plain)
    plain.enter_edit_mode()
    type_text(plain, '- one')
    plain.exit_edit_mode()

    assert tasks.list_markers()[0]['box'] is not None
    assert plain.list_markers()[0]['box'] is None


def test_the_boxes_go_on_and_off_the_lines_being_written(view):
    item = BeeTextItem('')
    view.scene.addItem(item)
    item.enter_edit_mode()
    type_text(item, 'one\ntwo')
    cursor = item.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End,
                        QtGui.QTextCursor.MoveMode.KeepAnchor)
    item.setTextCursor(cursor)
    view.scene.edit_item = item

    view.on_action_text_tasks()
    assert [item.is_task(block) for block in blocks(item)] == [True, True]

    view.on_action_text_tasks()
    assert [item.is_task(block) for block in blocks(item)] == [False, False]


def test_backspace_takes_the_box_off_with_the_list(view):
    item = task_note(view, 'one')
    cursor = item.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
    item.setTextCursor(cursor)

    press(item, Qt.Key.Key_Backspace, '\b')

    assert item.has_tasks() is False
    assert item.toPlainText() == 'one'


def test_the_line_after_a_finished_task_starts_out_unfinished(view):
    item = task_note(view, 'one')
    item.set_task_done(blocks(item)[0], True)
    item.set_tasks_collapsed(False)
    cursor = item.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
    item.setTextCursor(cursor)

    press(item, Qt.Key.Key_Return, '\r')
    type_text(item, 'two')

    assert item.task_is_done(item.textCursor().block()) is False
    typed = item.textCursor().block().begin().fragment()
    assert typed.text() == 'two'
    assert typed.charFormat().fontStrikeOut() is False


def test_a_task_list_is_kept_when_saved_and_opened_again(view):
    item = task_note(view)
    item.set_task_done(blocks(item)[0], True)
    item.set_tasks_collapsed(False)
    data = item.get_extra_save_data()

    opened = BeeTextItem(html=data['html'],
                         tasks_collapsed=data['tasks_collapsed'])

    assert lines(opened) == [('two', False, True), ('three', False, True),
                             ('one', True, True)]
    done = blocks(opened)[-1].begin().fragment()
    assert done.charFormat().fontStrikeOut() is True


def test_a_folded_away_task_list_opens_folded_away(view):
    item = task_note(view)
    item.set_task_done(blocks(item)[0], True)
    data = item.get_extra_save_data()

    assert 'tasks_collapsed' not in data
    opened = BeeTextItem(html=data['html'])

    assert opened.tasks_collapsed is True
    assert lines(opened)[-1] == ('one', True, False)


def test_a_note_without_tasks_saves_as_it_always_did(view):
    item = BeeTextItem('hello')
    view.scene.addItem(item)

    assert 'tasks_collapsed' not in item.get_extra_save_data()
    assert item.shows_done_bar() is False


def test_a_copy_of_a_task_list_is_a_task_list(view):
    item = task_note(view)
    item.exit_edit_mode()
    item.set_task_done(blocks(item)[0], True)
    item.set_tasks_collapsed(False)

    copy = item.create_copy()

    assert copy.done_count() == 1
    assert copy.tasks_collapsed is False
