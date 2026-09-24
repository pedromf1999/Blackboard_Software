"""Tasks dragged up and down their list by a grip, and numbered."""

from unittest.mock import MagicMock

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref.items import BeeTextItem


def press_key(item, key, typed=''):
    item.sceneEvent(QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, key,
                                    Qt.KeyboardModifier.NoModifier, typed))


def type_text(item, text):
    for char in text:
        if char == '\n':
            press_key(item, Qt.Key.Key_Return, '\r')
        else:
            press_key(item, Qt.Key.Key_A, char)


def task_note(view, lines='one\ntwo\nthree\nfour'):
    view.on_action_insert_tasks()
    item = view.scene.edit_item
    type_text(item, lines)
    item.exit_edit_mode()
    return item


def words(item):
    return [block.text() for block in item.task_blocks(done=False)]


def mouse(pos):
    event = MagicMock()
    event.pos.return_value = pos
    event.button.return_value = Qt.MouseButton.LeftButton
    event.buttons.return_value = Qt.MouseButton.LeftButton
    event.modifiers.return_value = Qt.KeyboardModifier.NoModifier
    return event


def rows(item):
    return [marker for marker in item.list_markers()
            if marker['grip'] is not None]


def drag(item, task, to):
    """Take a task up by its grip and put it down at a point."""

    grip = rows(item)[task]['grip']
    item.mousePressEvent(mouse(grip.center()))
    item.mouseMoveEvent(mouse(to))
    item.mouseReleaseEvent(mouse(to))


def below(item, task):
    """A point just under the middle of a task's line."""

    row = rows(item)[task]['row']
    return QtCore.QPointF(row.center().x(), row.center().y() + 1)


def above(item, task):
    row = rows(item)[task]['row']
    return QtCore.QPointF(row.center().x(), row.top() + 1)


def test_the_grip_shows_on_the_task_under_the_mouse(view):
    item = task_note(view)
    second = rows(item)[1]

    item.hoverMoveEvent(mouse(second['row'].center()))

    assert item.hovered_task == second['position']
    assert [item.grip_shows(marker) for marker in rows(item)] == [
        False, True, False, False]


def test_the_grip_goes_when_the_mouse_leaves(view):
    item = task_note(view)
    item.hoverMoveEvent(mouse(rows(item)[1]['row'].center()))

    item.hoverLeaveEvent(mouse(QtCore.QPointF(-100, -100)))

    assert item.hovered_task is None


def test_a_finished_task_has_no_grip(view):
    item = task_note(view)
    item.set_task_done(item.task_blocks()[0], True)
    item.set_tasks_collapsed(False)

    done = [marker for marker in item.list_markers() if marker['done']]
    assert done and all(marker['grip'] is None for marker in done)


def test_a_task_is_dragged_further_down(view):
    item = task_note(view)

    drag(item, 0, below(item, 2))

    assert words(item) == ['two', 'three', 'one', 'four']


def test_a_task_is_dragged_further_up(view):
    item = task_note(view)

    drag(item, 3, above(item, 1))

    assert words(item) == ['one', 'four', 'two', 'three']


def test_a_task_is_dragged_to_the_top(view):
    item = task_note(view)

    drag(item, 2, above(item, 0))

    assert words(item) == ['three', 'one', 'two', 'four']


def test_to_the_top_of_the_tasks_stays_under_what_heads_them(view):
    """A line above the list stays above it."""

    item = BeeTextItem('')
    view.scene.addItem(item)
    item.enter_edit_mode()
    # Without the placeholder word a new note starts with
    cursor = item.textCursor()
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    cursor.removeSelectedText()
    item.setTextCursor(cursor)
    type_text(item, 'Shopping\none\ntwo')
    cursor = item.textCursor()
    cursor.setPosition(item.document().findBlockByNumber(1).position())
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End,
                        QtGui.QTextCursor.MoveMode.KeepAnchor)
    item.setTextCursor(cursor)
    item.make_tasks(True)
    item.exit_edit_mode()

    drag(item, 1, above(item, 0))

    assert item.document().firstBlock().text() == 'Shopping'
    assert words(item) == ['two', 'one']


def test_a_drag_is_one_step_to_undo(view):
    item = task_note(view)
    before = view.undo_stack.count()

    drag(item, 0, below(item, 2))
    assert view.undo_stack.count() == before + 1

    view.undo_stack.undo()
    assert words(item) == ['one', 'two', 'three', 'four']


def test_putting_a_task_down_where_it_was_changes_nothing(view):
    item = task_note(view)
    before = view.undo_stack.count()

    drag(item, 1, above(item, 1))

    assert words(item) == ['one', 'two', 'three', 'four']
    assert view.undo_stack.count() == before


def test_the_grip_neither_ticks_the_task_nor_moves_the_note(view):
    item = task_note(view)
    item.setPos(0, 0)

    drag(item, 0, below(item, 1))

    assert item.done_count() == 0
    assert item.pos() == QtCore.QPointF(0, 0)


def test_a_line_shows_where_the_task_would_go(view):
    item = task_note(view)
    grip = rows(item)[0]['grip']
    item.mousePressEvent(mouse(grip.center()))
    item.mouseMoveEvent(mouse(below(item, 2)))

    assert item.task_drag['slot'] == 3
    painter = MagicMock()
    item.paint_drop_line(painter, item.list_markers())
    painter.drawLine.assert_called_once()


def test_numbers_follow_the_order_of_the_tasks(view):
    item = task_note(view)

    item.set_tasks_numbered(True)

    assert [marker['number'] for marker in rows(item)] == [
        '1.', '2.', '3.', '4.']


def test_numbered_words_are_pushed_along_to_make_room(view):
    item = task_note(view)
    left = rows(item)[0]['box'].left()

    item.set_tasks_numbered(True)

    first = item.task_blocks()[0]
    assert first.blockFormat().leftMargin() > 0
    # The box stays where it was; the words move
    assert abs(rows(item)[0]['box'].left() - left) < 0.5


def test_finished_tasks_are_not_numbered(view):
    item = task_note(view)
    item.set_tasks_numbered(True)
    item.set_task_done(item.task_blocks()[1], True)
    item.set_tasks_collapsed(False)

    numbers = [(marker['number'], marker['done'])
               for marker in item.list_markers()]
    assert numbers == [('1.', False), ('2.', False), ('3.', False),
                       (None, True)]


def test_numbers_are_worked_out_again_after_a_drag(view):
    item = task_note(view)
    item.set_tasks_numbered(True)

    drag(item, 0, below(item, 2))

    assert [(marker['number']) for marker in rows(item)] == [
        '1.', '2.', '3.', '4.']
    assert words(item)[2] == 'one'


def test_a_tenth_task_makes_room_for_two_digits(view):
    item = task_note(view, '\n'.join(str(n) for n in range(9)))
    item.set_tasks_numbered(True)
    room = item.number_room()

    item.enter_edit_mode()
    cursor = item.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
    item.setTextCursor(cursor)
    type_text(item, '\nten')

    assert item.number_room() > room
    last = item.task_blocks()[-1]
    assert abs(last.blockFormat().leftMargin() - item.number_room()) < 0.01


def test_the_button_numbers_the_list_and_undo_takes_it_back(view):
    item = task_note(view)
    view.scene.clearSelection()
    item.setSelected(True)

    view.on_action_text_task_numbers()
    assert item.tasks_numbered is True

    view.on_action_text_task_numbers()
    assert item.tasks_numbered is False

    view.undo_stack.undo()
    assert item.tasks_numbered is True


def test_numbering_is_kept_when_saved_and_opened_again(view):
    item = task_note(view)
    item.set_tasks_numbered(True)
    data = item.get_extra_save_data()

    opened = BeeTextItem(html=data['html'],
                         tasks_numbered=data['tasks_numbered'])

    assert opened.tasks_numbered is True
    assert [marker['number'] for marker in rows(opened)] == [
        '1.', '2.', '3.', '4.']


def test_a_list_without_numbers_saves_as_before(view):
    item = task_note(view)

    assert 'tasks_numbered' not in item.get_extra_save_data()
    assert all(block.blockFormat().leftMargin() == 0
               for block in item.task_blocks())
