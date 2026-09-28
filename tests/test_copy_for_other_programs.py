"""What copying hands to other programs: all the words, as they show."""

from unittest.mock import patch

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref import commands
from beeref.items import BeeGroupItem, BeePixmapItem, BeeTextItem


def press_key(item, key, typed=''):
    item.sceneEvent(QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, key,
                                    Qt.KeyboardModifier.NoModifier, typed))


def type_text(item, text):
    for char in text:
        if char == '\n':
            press_key(item, Qt.Key.Key_Return, '\r')
        else:
            press_key(item, Qt.Key.Key_A, char)


def task_note(view, lines):
    view.on_action_insert_tasks()
    item = view.scene.edit_item
    type_text(item, lines)
    item.exit_edit_mode()
    return item


def note(view, text, x=0, y=0):
    item = BeeTextItem(text)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def picture(view, x=0, y=0):
    img = QtGui.QImage(100, 80, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(90, 90, 110))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def a_group(view, items, title=''):
    group = BeeGroupItem(title=title)
    commands.GroupItems(view.scene, items, group).redo()
    return group


def copied(clipboard_mock, view, items):
    """What copying these items hands to other programs."""

    view.scene.clearSelection()
    for item in items:
        item.setSelected(True)
    view.on_action_copy()
    return clipboard_mock.return_value.setMimeData.call_args[0][0]


def blocks(item):
    result = []
    block = item.document().begin()
    while block.isValid():
        result.append(block)
        block = block.next()
    return result


def test_a_list_keeps_its_dashes(qapp):
    item = BeeTextItem()
    item.setPlainText('Shopping\nbread\nmilk\ncold')
    lines = blocks(item)
    item.set_list_level(lines[1], 1)
    item.set_list_level(lines[2], 1)
    item.set_list_level(lines[3], 2)
    assert item.text_for_other_programs() == (
        'Shopping\n- bread\n- milk\n\t- cold')


def test_a_numbered_list_keeps_its_numbers(qapp):
    item = BeeTextItem()
    item.setHtml('<ol><li>first</li><li>second</li></ol>')
    assert item.text_for_other_programs() == '1. first\n2. second'


def test_tasks_keep_their_boxes_and_numbers(view):
    item = task_note(view, 'one\ntwo\nthree')
    item.set_tasks_numbered(True)
    item.set_task_done(item.task_blocks()[1], True)
    # Numbered the way the note shows them: the finished one is not
    # counted, and sits at the foot with the others ticked off
    assert item.text_for_other_programs() == (
        '☐ 1. one\n☐ 2. three\n☑ two')


def test_tasks_without_numbers_keep_their_boxes(view):
    item = task_note(view, 'one\ntwo')
    item.set_task_done(item.task_blocks()[0], True)
    assert item.text_for_other_programs() == '☐ two\n☑ one'


def test_a_note_starts_with_its_title(qapp):
    item = BeeTextItem('the words')
    item.title = 'Heading'
    assert item.text_for_other_programs() == 'Heading\n\nthe words'


def test_a_table_goes_a_row_to_a_line(qapp):
    item = BeeTextItem()
    item.setPlainText('')
    table = item.insert_table(2, 2)
    for r, c, words in ((0, 0, 'a'), (0, 1, 'b'), (1, 0, 'c'), (1, 1, 'd')):
        table.cellAt(r, c).firstCursorPosition().insertText(words)
    assert item.text_for_other_programs().split('\n')[:2] == [
        'a\tb', 'c\td']


def test_a_picture_gives_its_caption(qapp):
    img = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_RGB32)
    item = BeePixmapItem(img)
    item.caption = 'A chair'
    assert item.text_for_other_programs() == 'A chair'


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_a_group_gives_its_title_and_everything_in_it(clipboard_mock, view):
    left = note(view, 'left note', 0, 0)
    right = note(view, 'right note', 400, 0)
    below = note(view, 'lower note', 0, 300)
    group = a_group(view, [below, right, left], title='Renders')

    mimedata = copied(clipboard_mock, view, [group])
    assert mimedata.text() == (
        'Renders\n\nleft note\n\nright note\n\nlower note')
    # And pasting on the board still gives the group itself
    assert mimedata.data('beeref/items') == b'1'


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_select_all_and_copy_takes_the_task_numbers_along(
        clipboard_mock, view):
    tasks = task_note(view, 'sketch\nrender')
    tasks.set_tasks_numbered(True)
    tasks.setPos(0, 0)
    group = a_group(view, [tasks], title='To do')

    view.scene.clearSelection()
    view.on_action_select_all()
    view.on_action_copy()
    mimedata = clipboard_mock.return_value.setMimeData.call_args[0][0]
    assert view.scene.selectedItems(user_only=True) == [group]
    assert mimedata.text() == 'To do\n\n☐ 1. sketch\n☐ 2. render'


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_groups_inside_groups_give_their_titles_too(clipboard_mock, view):
    inner = a_group(view, [note(view, 'inside')], title='Inner')
    outer = a_group(view, [inner], title='Outer')
    mimedata = copied(clipboard_mock, view, [outer])
    assert mimedata.text() == 'Outer\n\nInner\n\ninside'


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_items_are_read_in_rows(clipboard_mock, view):
    third = note(view, 'third', 0, 300)
    second = note(view, 'second', 400, 10)
    first = note(view, 'first', 0, 0)
    mimedata = copied(clipboard_mock, view, [third, second, first])
    assert mimedata.text() == 'first\n\nsecond\n\nthird'


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_a_picture_on_its_own_still_goes_as_a_picture(clipboard_mock, view):
    item = picture(view)
    item.caption = 'A chair'
    mimedata = copied(clipboard_mock, view, [item])
    assert mimedata.hasImage() is True


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_pictures_without_words_still_go_as_a_picture(clipboard_mock, view):
    mimedata = copied(clipboard_mock, view,
                      [picture(view), picture(view, 300, 0)])
    assert mimedata.hasImage() is True


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_words_win_over_a_picture_beside_them(clipboard_mock, view):
    mimedata = copied(clipboard_mock, view,
                      [picture(view), note(view, 'about it', 300, 0)])
    assert mimedata.text() == 'about it'


# Copying from inside a note, while writing in it

def control(key):
    return QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, key,
                           Qt.KeyboardModifier.ControlModifier, '')


def pick(item, start, end):
    cursor = item.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QtGui.QTextCursor.MoveMode.KeepAnchor)
    item.setTextCursor(cursor)


def written_list(view):
    """A titled, numbered task list with one task done, being written."""

    item = task_note(view, 'sketch\nmodel\nrender\nprint')
    item.set_tasks_numbered(True)
    item.set_task_done(item.task_blocks()[1], True)
    item.title = 'Chair'
    item.enter_edit_mode()
    return item


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_copying_a_whole_note_while_writing_keeps_everything(
        clipboard_mock, view):
    item = written_list(view)
    pick(item, 0, item.document().characterCount() - 1)
    item.keyPressEvent(control(Qt.Key.Key_C))

    mimedata = clipboard_mock.return_value.setMimeData.call_args[0][0]
    assert mimedata.text() == (
        'Chair\n\n☐ 1. sketch\n☐ 2. render\n☐ 3. print\n☑ model')
    # And a page with them, for programs that take formatted words
    page = mimedata.html()
    assert '<b>Chair</b>' in page
    for line in ('☐ 1. sketch', '☐ 2. render', '☐ 3. print'):
        assert line in page
    assert 'class="unchecked"' not in page


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_part_of_a_list_keeps_the_numbers_it_shows(clipboard_mock, view):
    item = written_list(view)
    render = item.task_blocks(done=False)[1]
    last = item.task_blocks(done=False)[2]
    pick(item, render.position(), last.position() + len(last.text()))
    item.keyPressEvent(control(Qt.Key.Key_C))

    mimedata = clipboard_mock.return_value.setMimeData.call_args[0][0]
    assert mimedata.text() == '☐ 2. render\n☐ 3. print'
    assert mimedata.html().count('<p') == 2


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_control_c_in_a_window_reaches_the_note(
        clipboard_mock, main_window, view, qtbot):
    """Through the window, where the menu's Copy has Ctrl+C as well."""

    main_window.show()
    qtbot.waitExposed(main_window)
    view.on_action_insert_tasks()
    item = view.scene.edit_item
    for number, words in enumerate(['sketch', 'model']):
        if number:
            QTest.keyClick(view.viewport(), Qt.Key.Key_Return)
        QTest.keyClicks(view.viewport(), words)
    item.set_tasks_numbered(True)
    item.title = 'Chair'
    pick(item, 0, item.document().characterCount() - 1)
    QTest.keyClick(view.viewport(), Qt.Key.Key_C,
                   Qt.KeyboardModifier.ControlModifier)

    mimedata = clipboard_mock.return_value.setMimeData.call_args[0][0]
    assert mimedata.text() == 'Chair\n\n☐ 1. sketch\n☐ 2. model'
    # Still writing: the menu's Copy would have ended that
    assert item.edit_mode is True


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_a_stretch_of_one_line_is_left_to_qt(clipboard_mock, view):
    item = written_list(view)
    start = item.task_blocks(done=False)[0].position()
    pick(item, start + 1, start + 4)
    assert item.copy_key_press(control(Qt.Key.Key_C)) is False


@patch('PyQt6.QtWidgets.QApplication.clipboard')
def test_cutting_takes_the_words_away_with_their_marks(clipboard_mock, view):
    item = task_note(view, 'one\ntwo\nthree')
    item.set_tasks_numbered(True)
    item.enter_edit_mode()
    two = item.task_blocks()[1]
    three = item.task_blocks()[2]
    pick(item, two.position(), three.position() + len(three.text()))
    item.keyPressEvent(control(Qt.Key.Key_X))

    mimedata = clipboard_mock.return_value.setMimeData.call_args[0][0]
    assert mimedata.text() == '☐ 2. two\n☐ 3. three'
    assert 'three' not in item.toPlainText()
