"""Lists in notes: a dash and a space at the start of a line begin one."""

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref.items import BeeTextItem


def press(item, key, text='', modifier=Qt.KeyboardModifier.NoModifier):
    """Press a key the way the scene does.

    Through sceneEvent rather than keyPressEvent: Qt sends Tab and
    Shift+Tab from there straight to the text, and a test calling
    keyPressEvent would never see that.
    """

    event = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, key, modifier, text)
    item.sceneEvent(event)
    return event


KEYS = {
    '\n': (Qt.Key.Key_Return, '\r'),
    '\t': (Qt.Key.Key_Tab, '\t'),
    ' ': (Qt.Key.Key_Space, ' '),
    '-': (Qt.Key.Key_Minus, '-'),
}


def type_text(item, text):
    """Type as a person would, one key at a time."""

    for char in text:
        key, typed = KEYS.get(char, (Qt.Key.Key_A, char))
        press(item, key, typed)


def shift_tab(item):
    return press(item, Qt.Key.Key_Backtab,
                 modifier=Qt.KeyboardModifier.ShiftModifier)


def backspace(item):
    press(item, Qt.Key.Key_Backspace, '\b')


def empty_note(view):
    item = BeeTextItem('x')
    view.scene.addItem(item)
    item.enter_edit_mode()
    cursor = item.textCursor()
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    cursor.removeSelectedText()
    item.setTextCursor(cursor)
    return item


def lines(item):
    """Each paragraph's words and how deep in a list it sits."""

    result = []
    block = item.document().begin()
    while block.isValid():
        result.append((block.text(), item.list_level(block)))
        block = block.next()
    return result


def indents(item):
    """How far each paragraph is pushed along outside of any list."""

    result = []
    block = item.document().begin()
    while block.isValid():
        result.append(block.blockFormat().indent())
        block = block.next()
    return result


def test_dash_and_space_start_a_list(view):
    item = empty_note(view)
    type_text(item, '- apples')
    assert lines(item) == [('apples', 1)]


def test_the_dash_only_counts_at_the_start_of_a_line(view):
    item = empty_note(view)
    type_text(item, 'one - two')
    assert lines(item) == [('one - two', 0)]


def test_a_dash_without_a_space_is_just_a_dash(view):
    item = empty_note(view)
    type_text(item, '-5 degrees')
    assert lines(item) == [('-5 degrees', 0)]


def test_a_dash_typed_in_front_of_words_makes_them_an_item(view):
    item = BeeTextItem('apples')
    view.scene.addItem(item)
    item.enter_edit_mode()
    type_text(item, '- ')
    assert lines(item) == [('apples', 1)]


def test_enter_starts_the_next_item(view):
    item = empty_note(view)
    type_text(item, 'Shopping\n- apples\npears')
    assert lines(item) == [('Shopping', 0), ('apples', 1), ('pears', 1)]


def test_the_items_share_one_list(view):
    item = empty_note(view)
    type_text(item, '- apples\npears')
    first = item.document().begin()
    assert first.textList().count() == 2


def test_enter_on_an_empty_item_ends_the_list(view):
    item = empty_note(view)
    type_text(item, '- apples\n\nafter')
    assert lines(item) == [('apples', 1), ('after', 0)]
    assert indents(item) == [0, 0]


def test_tab_at_the_start_of_an_item_goes_one_level_in(view):
    item = empty_note(view)
    type_text(item, '- apples\n\tgreen')
    assert lines(item) == [('apples', 1), ('green', 2)]


def test_tab_inside_the_words_of_an_item_types_a_tab(view):
    item = empty_note(view)
    type_text(item, '- apples\tpears')
    assert lines(item) == [('apples\tpears', 1)]


def test_tab_outside_a_list_types_a_tab(view):
    item = empty_note(view)
    type_text(item, '\tapples')
    assert lines(item) == [('\tapples', 0)]


def test_enter_on_an_empty_inner_item_steps_back_out(view):
    item = empty_note(view)
    type_text(item, '- apples\n\tgreen\n\npears')
    assert lines(item) == [('apples', 1), ('green', 2), ('pears', 1)]


def test_stepping_back_out_rejoins_the_list_above(view):
    item = empty_note(view)
    type_text(item, '- apples\n\tgreen\n\npears')
    first = item.document().begin()
    last = first.next().next()
    assert last.textList().count() == 2
    assert item.list_above(last, 1) is not None


def test_shift_tab_goes_one_level_out(view):
    item = empty_note(view)
    type_text(item, '- apples\n\tgreen')
    shift_tab(item)
    assert lines(item) == [('apples', 1), ('green', 1)]


def test_shift_tab_goes_out_when_it_comes_as_tab_with_shift(view):
    item = empty_note(view)
    type_text(item, '- apples\n\tgreen')
    press(item, Qt.Key.Key_Tab, modifier=Qt.KeyboardModifier.ShiftModifier)
    assert lines(item) == [('apples', 1), ('green', 1)]


def test_shift_tab_at_the_top_level_stays_put_and_keeps_the_focus(view):
    item = empty_note(view)
    type_text(item, '- apples')
    event = shift_tab(item)
    assert lines(item) == [('apples', 1)]
    assert event.isAccepted()


def test_backspace_at_the_start_of_an_item_takes_the_dash_away(view):
    item = empty_note(view)
    type_text(item, '- apples')
    cursor = item.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
    item.setTextCursor(cursor)

    backspace(item)
    # Still pushed along, as in Word, until Backspace is pressed again
    assert lines(item) == [('apples', 0)]
    assert indents(item) == [1]
    backspace(item)
    assert indents(item) == [0]


def test_a_dash_typed_on_a_line_pushed_along_goes_back_in_there(view):
    item = empty_note(view)
    type_text(item, '- apples')
    cursor = item.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfBlock)
    item.setTextCursor(cursor)
    backspace(item)

    type_text(item, '- ')
    assert lines(item) == [('apples', 1)]
    assert indents(item) == [0]


def test_undo_gives_back_the_dash_as_typed(view):
    item = empty_note(view)
    type_text(item, '- ')
    assert lines(item) == [('', 1)]
    item.document().undo()
    assert lines(item) == [('- ', 0)]


def test_a_list_in_a_table_cell_is_its_own_list(view):
    item = empty_note(view)
    item.insert_table(rows=1, columns=2)
    type_text(item, '- apples')
    table = item.current_table()
    item.setTextCursor(table.cellAt(0, 1).firstCursorPosition())
    del table
    type_text(item, '- pears')

    block = item.textCursor().block()
    assert item.list_level(block) == 1
    assert block.textList().count() == 1


def test_a_list_is_kept_when_saved_and_opened_again(view):
    item = empty_note(view)
    type_text(item, 'Shopping\n- apples\n\tgreen\n\npears')
    item.exit_edit_mode()

    opened = BeeTextItem(html=item.get_extra_save_data()['html'])
    assert lines(opened) == [
        ('Shopping', 0), ('apples', 1), ('green', 2), ('pears', 1)]


def test_the_step_follows_the_size_of_the_text(view):
    item = empty_note(view)
    type_text(item, '- apples')
    small = item.document().indentWidth()

    cursor = QtGui.QTextCursor(item.document())
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    fmt = QtGui.QTextCharFormat()
    fmt.setFontPointSize(36)
    cursor.mergeCharFormat(fmt)
    assert item.document().indentWidth() > 2 * small


def test_every_bulleted_item_gets_a_dash(view):
    item = empty_note(view)
    type_text(item, 'Shopping\n- apples\npears that go on for long enough '
              'to wrap onto a second line')
    item.set_wrap_width(120)
    assert len(item.list_markers()) == 2


def test_numbered_lists_keep_their_numbers(view):
    item = BeeTextItem(html='<ol><li>one</li><li>two</li></ol>')
    view.scene.addItem(item)
    assert item.list_markers() == []


ZOOM = 4


def render(item):
    """The note drawn at four times its size, from its top left corner."""

    item.setPos(0, 0)
    rect = QtCore.QRectF(0, 0, item.boundingRect().right(),
                         item.boundingRect().bottom())
    image = QtGui.QImage(int(rect.width() * ZOOM), int(rect.height() * ZOOM),
                         QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor(255, 0, 255))
    painter = QtGui.QPainter(image)
    item.scene().render(painter, QtCore.QRectF(image.rect()), rect,
                        Qt.AspectRatioMode.IgnoreAspectRatio)
    painter.end()
    return image


def colours_in(image, rect):
    # A little in from the right, where the first letter starts and its
    # softened edge may already show
    rect = rect.adjusted(0, 0, -1, 0)
    found = set()
    for x in range(int(rect.left() * ZOOM), int(rect.right() * ZOOM)):
        for y in range(int(rect.top() * ZOOM), int(rect.bottom() * ZOOM)):
            if image.valid(x, y):
                found.add(image.pixel(x, y))
    return found


def test_qts_dot_is_not_drawn_in_front_of_an_item(view):
    item = empty_note(view)
    type_text(item, '- apples')
    item.exit_edit_mode()
    item.setSelected(False)
    item.setPos(0, 0)
    # Nothing in place of the dot, so all that shows there is the box
    item.LIST_MARKER = ''
    clear = item.list_markers()[0][0]

    image = render(item)
    assert colours_in(image, clear) == {item.box_color.rgba()}


def test_the_dash_is_drawn_in_front_of_an_item(view):
    item = empty_note(view)
    type_text(item, '- apples')
    item.exit_edit_mode()
    item.setSelected(False)
    item.setPos(0, 0)
    clear = item.list_markers()[0][0]

    image = render(item)
    assert len(colours_in(image, clear)) > 1
