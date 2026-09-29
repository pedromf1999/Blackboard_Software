"""Numbered lists: lines numbered 1, 2, 3, with no boxes to tick."""

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

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


def new_note(view):
    """An empty note, being written in."""

    view.new_note_at(QtCore.QPointF(0, 0))
    item = view.scene.edit_item
    press(item, Qt.Key.Key_Delete)
    return item


def blocks(item):
    result = []
    block = item.document().begin()
    while block.isValid():
        result.append(block)
        block = block.next()
    return result


def numbers(item):
    """What stands in front of each line: its number, or None."""

    return [block.textList().itemText(block) if item.is_numbered(block)
            else None for block in blocks(item)]


def select_all(item):
    cursor = item.textCursor()
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    item.setTextCursor(cursor)


def test_the_button_starts_a_numbered_list_that_goes_on(view):
    item = new_note(view)
    view.on_action_text_task_numbers()
    type_text(item, 'sketch\nmodel\nrender')

    assert numbers(item) == ['1.', '2.', '3.']
    # A list, and no boxes
    assert item.has_tasks() is False
    assert len({id(block.textList()) for block in blocks(item)}) == 1


def test_pressing_again_takes_the_numbers_off(view):
    item = new_note(view)
    view.on_action_text_task_numbers()
    type_text(item, 'sketch\nmodel')
    select_all(item)
    view.on_action_text_task_numbers()

    assert numbers(item) == [None, None]
    assert all(block.textList() is None for block in blocks(item))
    # With no room left in front of the words for a number
    assert all(block.blockFormat().leftMargin() == 0
               for block in blocks(item))


def test_the_lines_picked_out_are_numbered(view):
    item = new_note(view)
    type_text(item, 'Chair\nsketch\nmodel')
    cursor = item.textCursor()
    cursor.setPosition(blocks(item)[1].position())
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End,
                        QtGui.QTextCursor.MoveMode.KeepAnchor)
    item.setTextCursor(cursor)
    view.on_action_text_task_numbers()

    assert numbers(item) == [None, '1.', '2.']


def test_a_list_with_dashes_becomes_numbered(view):
    item = new_note(view)
    type_text(item, '- sketch\nmodel')
    assert numbers(item) == [None, None]
    select_all(item)
    view.on_action_text_task_numbers()

    assert numbers(item) == ['1.', '2.']


def test_enter_on_an_empty_numbered_line_ends_the_list(view):
    item = new_note(view)
    view.on_action_text_task_numbers()
    type_text(item, 'sketch\n\nafter')

    assert numbers(item) == ['1.', None]
    assert blocks(item)[1].text() == 'after'


def test_tab_makes_a_numbered_list_inside_the_list(view):
    item = new_note(view)
    view.on_action_text_task_numbers()
    type_text(item, 'sketch\n')
    press(item, Qt.Key.Key_Tab)
    type_text(item, 'rough\n')
    press(item, Qt.Key.Key_Backtab)
    type_text(item, 'model')

    assert [item.list_level(block) for block in blocks(item)] == [1, 2, 1]
    assert numbers(item) == ['1.', '1.', '2.']


def test_in_a_task_list_the_button_still_numbers_the_tasks(view):
    view.on_action_insert_tasks()
    item = view.scene.edit_item
    type_text(item, 'one\ntwo')
    view.on_action_text_task_numbers()

    assert item.tasks_numbered is True
    assert numbers(item) == [None, None]
    assert item.has_tasks() is True


def test_a_note_chosen_on_the_board_is_numbered_whole(view):
    item = BeeTextItem('sketch\nmodel\nrender')
    view.scene.addItem(item)
    view.scene.clearSelection()
    item.setSelected(True)

    view.on_action_text_task_numbers()
    assert numbers(item) == ['1.', '2.', '3.']

    view.on_action_text_task_numbers()
    assert numbers(item) == [None, None, None]

    view.undo_stack.undo()
    assert numbers(item) == ['1.', '2.', '3.']


def test_boxes_on_a_numbered_line_replace_its_number(view):
    item = new_note(view)
    view.on_action_text_task_numbers()
    type_text(item, 'sketch\nmodel')
    select_all(item)
    view.on_action_text_tasks()

    assert item.has_tasks() is True
    assert numbers(item) == [None, None]
    # Drawn with a box, as any task is
    assert len([marker for marker in item.list_markers()
                if marker['box'] is not None]) == 2


def test_a_numbered_list_is_kept_when_saved_and_opened_again(view):
    item = new_note(view)
    view.on_action_text_task_numbers()
    type_text(item, 'sketch\nmodel')
    item.exit_edit_mode()

    opened = BeeTextItem(html=item.get_extra_save_data()['html'])
    assert numbers(opened) == ['1.', '2.']
    assert opened.text_for_other_programs() == '1. sketch\n2. model'


def test_numbers_three_digits_wide_get_room_in_the_box(qapp):
    item = BeeTextItem()
    item.setPlainText('\n'.join(f'line {n}' for n in range(1, 121)))
    item.number_lines(item.all_lines(), True)

    document = item.document()
    last = blocks(item)[-1]
    metrics = QtGui.QFontMetricsF(
        last.charFormat().font().resolve(document.defaultFont()))
    words_start = (document.indentWidth() * item.list_level(last)
                   + last.blockFormat().leftMargin())
    assert words_start >= metrics.horizontalAdvance('120. ')
    # All the lines alike, so that they line up
    assert len({round(block.blockFormat().leftMargin(), 2)
                for block in blocks(item)}) == 1
