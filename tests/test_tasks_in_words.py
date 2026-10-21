"""Tasks in the middle of a note's words: ticked off and put back where
they stood, undone whole while writing, and their strip of finished
ones where they are."""

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref.items import BeeTextItem


def note_of(view, texts, tasks):
    """A note of these lines, those numbered in ``tasks`` with a box."""

    note = BeeTextItem('\n'.join(texts))
    view.scene.addItem(note)
    block = note.document().begin()
    index = 0
    while block.isValid():
        if index in tasks:
            note.set_task(block, True)
            block = note.document().findBlock(block.position())
        block = block.next()
        index += 1
    note.refresh_tasks()
    return note


def lines(note):
    found = []
    block = note.document().begin()
    while block.isValid():
        mark = ('[x]' if note.task_is_done(block)
                else '[ ]' if note.is_task(block) else '')
        found.append((mark, block.text()))
        block = block.next()
    return found


def block_of(note, text):
    block = note.document().begin()
    while block.isValid():
        if block.text() == text:
            return block
        block = block.next()


def key(note, k, text='', modifiers=Qt.KeyboardModifier.NoModifier):
    note.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, k,
                                       modifiers, text))


def undo(note):
    key(note, Qt.Key.Key_Z, '', Qt.KeyboardModifier.ControlModifier)


def redo(note):
    key(note, Qt.Key.Key_Z, '', Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.ShiftModifier)


MEETING = ['Notes from the meeting', 'Buy springs', 'Call Tiago',
           'Order PCB', 'Some more words', 'Last line']
MADE = [('', 'Notes from the meeting'), ('[ ]', 'Buy springs'),
        ('[ ]', 'Call Tiago'), ('[ ]', 'Order PCB'),
        ('', 'Some more words'), ('', 'Last line')]


def meeting(view):
    return note_of(view, MEETING, tasks={1, 2, 3})


# Ticked and put back

def test_a_ticked_task_goes_after_the_others_and_the_words_stay(view):
    note = meeting(view)
    note.change_task(block_of(note, 'Call Tiago'), True)
    assert lines(note) == [
        ('', 'Notes from the meeting'), ('[ ]', 'Buy springs'),
        ('[ ]', 'Order PCB'), ('[x]', 'Call Tiago'),
        ('', 'Some more words'), ('', 'Last line')]


def test_put_back_it_goes_back_where_it_stood(view):
    note = meeting(view)
    note.change_task(block_of(note, 'Call Tiago'), True)
    note.change_task(block_of(note, 'Call Tiago'), False)
    assert lines(note) == MADE


def test_the_first_put_back_goes_back_first(view):
    note = meeting(view)
    note.change_task(block_of(note, 'Buy springs'), True)
    note.change_task(block_of(note, 'Order PCB'), True)
    note.change_task(block_of(note, 'Buy springs'), False)
    assert lines(note)[1] == ('[ ]', 'Buy springs')
    assert lines(note)[2] == ('[ ]', 'Call Tiago')


# Undone while writing

def test_ctrl_z_while_writing_takes_a_tick_back_whole(view):
    note = meeting(view)
    note.enter_edit_mode()
    note.change_task(block_of(note, 'Buy springs'), True)
    assert ('[x]', 'Buy springs') in lines(note)
    undo(note)
    assert lines(note) == MADE
    assert all(block_of(note, text).isVisible() for _, text in MADE)
    redo(note)
    assert lines(note)[3] == ('[x]', 'Buy springs')
    note.exit_edit_mode()


def test_ctrl_z_takes_back_only_the_tick_not_what_was_typed(view):
    note = meeting(view)
    note.enter_edit_mode()
    cursor = note.textCursor()
    cursor.setPosition(block_of(note, 'Last line').position()
                       + len('Last line'))
    note.setTextCursor(cursor)
    for letter in ' here':
        key(note, Qt.Key.Key_A, letter)
    note.change_task(block_of(note, 'Order PCB'), True)
    undo(note)
    assert lines(note)[-1] == ('', 'Last line here')
    assert lines(note)[3] == ('[ ]', 'Order PCB')
    note.exit_edit_mode()


def test_ticks_while_writing_are_one_with_the_writing_on_the_board(view):
    note = meeting(view)
    note.enter_edit_mode()
    note.change_task(block_of(note, 'Buy springs'), True)
    note.exit_edit_mode()
    view.undo_stack.undo()
    assert lines(note) == MADE


def test_on_the_board_a_tick_is_still_a_step_to_undo(view):
    note = meeting(view)
    note.change_task(block_of(note, 'Call Tiago'), True)
    view.undo_stack.undo()
    assert lines(note) == MADE


# The strip of finished ones

def test_folded_away_their_strip_stands_where_they_are(view):
    note = meeting(view)
    note.tasks_collapsed = True
    note.change_task(block_of(note, 'Call Tiago'), True)
    layout = note.document().documentLayout()
    bar = note.done_bar_rect()
    last_to_do = layout.blockBoundingRect(block_of(note, 'Order PCB'))
    words = layout.blockBoundingRect(block_of(note, 'Some more words'))
    # Under all the words, it read as if the tasks had gone to the end
    assert bar.top() >= last_to_do.bottom() - 0.5
    assert bar.bottom() <= words.top() + 0.5


def test_the_room_for_the_strip_goes_when_it_does(view):
    note = meeting(view)
    note.tasks_collapsed = True
    note.change_task(block_of(note, 'Call Tiago'), True)
    after = block_of(note, 'Some more words')
    assert after.blockFormat().topMargin() > 0
    note.change_task(block_of(note, 'Call Tiago'), False)
    after = block_of(note, 'Some more words')
    assert after.blockFormat().topMargin() == 0
    note.change_task(block_of(note, 'Call Tiago'), True)
    note.set_tasks_collapsed(False)
    after = block_of(note, 'Some more words')
    assert after.blockFormat().topMargin() == 0


def test_the_note_is_no_taller_for_its_strip_inside_the_words(view):
    note = meeting(view)
    note.tasks_collapsed = True
    note.change_task(block_of(note, 'Call Tiago'), True)
    # The strip has its room inside the words already
    assert abs(note.box_rect().height() - note.text_rect().height()) < 0.5


def test_a_note_of_tasks_alone_keeps_its_strip_under_them(view):
    note = note_of(view, ['one', 'two', 'three'], tasks={0, 1, 2})
    note.tasks_collapsed = True
    note.change_task(block_of(note, 'one'), True)
    assert note.words_after_done() is None
    assert abs(note.done_bar_rect().top() - note.text_rect().bottom()) < 0.5
