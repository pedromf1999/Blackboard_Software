"""The pinned notes stand in columns, side by side in their tab."""

import pytest
from PyQt6 import QtCore
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref.items import BeeTextItem
from . import test_pinned_notes
from .test_pinned_notes import drag, mouse_move, note_at, pin


# The window with a picture on its board, as the other pinned note tests
# have it
board = test_pinned_notes.board


def pinned(board, *texts):
    notes = []
    for index, text in enumerate(texts):
        note = note_at(board, QtCore.QPoint(100, 100 + 80 * index), text)
        pin(board, note)
        notes.append(note)
    board.scene.clearSelection()
    return notes


def middle(board, note):
    return note.screen_rect(board).center().toPoint()


def columns(board):
    return [[note.toPlainText() for note in column]
            for column in board.pinned_columns()]


def beside(board, note, side):
    """Just outside the tab, level with the note."""

    tab = board.pins_tab_rect()
    y = middle(board, note).y()
    if side == 'right':
        return QtCore.QPoint(round(tab.right()) + 15, y)
    return QtCore.QPoint(round(tab.left()) - 15, y)


def test_dragged_beside_the_tab_a_note_starts_a_column(board):
    first, second = pinned(board, 'first', 'second')

    drag(board.viewport(), middle(board, second),
         beside(board, second, 'right'))

    assert columns(board) == [['first'], ['second']]
    one, two = first.screen_rect(board), second.screen_rect(board)
    # Side by side, the second to the right of the first and its buttons
    assert two.left() > one.right()
    assert two.top() == pytest.approx(one.top(), abs=0.6)
    tab = board.pins_tab_rect()
    assert tab.contains(one) and tab.contains(two)


def test_or_a_first_column_on_the_left(board):
    first, second = pinned(board, 'first', 'second')

    drag(board.viewport(), middle(board, second),
         beside(board, second, 'left'))

    assert columns(board) == [['second'], ['first']]
    assert (second.screen_rect(board).right()
            < first.screen_rect(board).left())


def test_too_far_from_the_tab_it_goes_back(board):
    first, second = pinned(board, 'first', 'second')
    far = beside(board, second, 'left') - QtCore.QPoint(400, 0)

    drag(board.viewport(), middle(board, second), far)

    assert columns(board) == [['first', 'second']]


def test_dropped_under_a_column_it_goes_to_its_bottom(board):
    first, second, third = pinned(board, 'first', 'second', 'third\nlong\n'
                                  'with\nmany\nlines')
    drag(board.viewport(), middle(board, third),
         beside(board, third, 'right'))
    assert columns(board) == [['first', 'second'], ['third\nlong\nwith\n'
                                                    'many\nlines']]

    # Below the short column, beside the tall one
    under = second.screen_rect(board).bottomLeft().toPoint() + QtCore.QPoint(
        10, 20)
    drag(board.viewport(), middle(board, first), under)

    assert columns(board)[0] == ['second', 'first']


def test_dropped_above_a_column_it_goes_to_its_top(board):
    first, second, third = pinned(board, 'first', 'second', 'third')
    drag(board.viewport(), middle(board, third),
         beside(board, third, 'right'))
    assert columns(board) == [['first', 'second'], ['third']]

    above = third.screen_rect(board).topLeft().toPoint() + QtCore.QPoint(
        10, -6)
    drag(board.viewport(), middle(board, second), above)

    assert columns(board) == [['first'], ['second', 'third']]


def test_dropped_on_a_note_in_another_column_the_two_swap(board):
    first, second, third = pinned(board, 'first', 'second', 'third')
    drag(board.viewport(), middle(board, third),
         beside(board, third, 'right'))
    steps = board.undo_stack.count()

    drag(board.viewport(), middle(board, first), middle(board, third))

    assert columns(board) == [['third', 'second'], ['first']]
    # Rearranging the window, not the board
    assert board.undo_stack.count() == steps


def test_a_column_left_empty_is_gone(board):
    first, second = pinned(board, 'first', 'second')
    drag(board.viewport(), middle(board, second),
         beside(board, second, 'right'))
    assert len(board.pinned_columns()) == 2

    under = first.screen_rect(board).bottomLeft().toPoint() + QtCore.QPoint(
        10, 20)
    drag(board.viewport(), middle(board, second), under)

    assert columns(board) == [['first', 'second']]
    assert second.pin['column'] == 0


def gap_between(a, b):
    """The space between two rectangles that do not overlap."""

    across = max(b.left() - a.right(), a.left() - b.right())
    down = max(b.top() - a.bottom(), a.top() - b.bottom())
    return max(across, down)


def test_columns_keep_the_gap_and_never_overlap(board):
    notes = pinned(board, 'one', 'two\nlines', 'three', 'four\nfive\nsix')
    for note in notes[2:]:
        drag(board.viewport(), middle(board, note),
             beside(board, note, 'right'))
    board.set_pinned_note_minimized(notes[1], True)
    assert len(board.pinned_columns()) == 3

    rects = []
    for note in notes:
        controls, label = board.pinned_note_widgets[note]
        if note.is_minimized:
            rects.append(QtCore.QRectF(label.geometry()))
        else:
            rects.append(note.screen_rect(board).united(
                QtCore.QRectF(controls.geometry())))
    for index, rect in enumerate(rects):
        for other in rects[index + 1:]:
            assert gap_between(rect, other) >= board.PINS_GAP - 1.6
    tab = board.pins_tab_rect()
    for rect in rects:
        assert tab.contains(rect)


def test_folding_a_note_moves_only_those_below_it(board):
    first, second, third = pinned(board, 'one\ntwo\nthree\nfour', 'below',
                                  'beside')
    drag(board.viewport(), middle(board, third),
         beside(board, third, 'right'))
    below = second.screen_rect(board).top()
    side = third.screen_rect(board).topLeft()

    board.set_pinned_note_minimized(first, True)

    assert second.screen_rect(board).top() < below
    assert third.screen_rect(board).top() == pytest.approx(side.y())


def test_the_tab_is_as_tall_as_its_tallest_column(board):
    first, second = pinned(board, 'short', 'tall\nwith\nmany\nlines\nof it')
    drag(board.viewport(), middle(board, second),
         beside(board, second, 'right'))

    tab = board.pins_tab_rect()
    assert tab.bottom() == pytest.approx(
        second.screen_rect(board).bottom() + board.pins_tab.PADDING,
        abs=1)


def test_a_new_pin_goes_under_the_last_column(board):
    first, second = pinned(board, 'first', 'second')
    drag(board.viewport(), middle(board, second),
         beside(board, second, 'right'))

    [third] = pinned(board, 'third')

    assert columns(board) == [['first'], ['second', 'third']]


def test_the_way_is_shown_while_a_note_is_in_hand(board):
    first, second = pinned(board, 'first', 'second')
    tab = board.pins_tab
    start = middle(board, second)
    end = beside(board, second, 'right')

    QTest.mousePress(board.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 9):
        mouse_move(board.viewport(), start + (end - start) * step / 8)
    assert tab.drop_kind == 'new'
    assert tab.drop_rect is not None
    mouse_move(board.viewport(), middle(board, first))
    assert tab.drop_kind == 'swap'
    # Over the note it would swap with, not under it
    assert second.zValue() > first.zValue()
    mouse_move(board.viewport(), end)
    QTest.mouseRelease(board.viewport(), Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, end)

    assert tab.drop_kind is None
    assert columns(board) == [['first'], ['second']]
    assert second.zValue() == first.zValue() == BeeTextItem.PINNED_Z


def test_a_folded_label_starts_a_column_too(board):
    first, second = pinned(board, 'first', 'second')
    board.set_pinned_note_minimized(second, True)
    label = board.pinned_note_widgets[second][1]
    start = label.rect().center()
    target = board.viewport().mapToGlobal(beside(board, first, 'right'))

    QTest.mousePress(label, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 9):
        wanted = label.mapFromGlobal(target)
        mouse_move(label, start + (wanted - start) * step / 8)
    assert board.pins_tab.drop_kind == 'new'
    QTest.mouseRelease(label, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, label.rect().center())

    assert second.is_minimized is True
    assert columns(board) == [['first'], ['second']]
    assert label.geometry().left() > first.screen_rect(board).right()


def test_columns_are_saved_with_the_board(board, tmp_path):
    from beeref import fileio

    first, second, third = pinned(board, 'first', 'second', 'third')
    drag(board.viewport(), middle(board, second),
         beside(board, second, 'right'))
    assert columns(board) == [['first', 'third'], ['second']]
    filename = str(tmp_path / 'board.blk')
    fileio.save_bee(filename, board.scene, create_new=True)

    board.scene.clear()
    fileio.load_bee(filename, board.scene)
    board.scene.add_queued_items()
    board.place_pinned_notes()

    assert columns(board) == [['first', 'third'], ['second']]


def test_read_down_each_column_for_the_versions_before_columns(board):
    """Which put them all in one column, by their place alone."""

    first, second, third = pinned(board, 'first', 'second', 'third')
    drag(board.viewport(), middle(board, first),
         beside(board, first, 'right'))

    assert columns(board) == [['second', 'third'], ['first']]
    assert [note.pin['order'] for note in (second, third, first)] == [
        0, 1, 2]


def test_a_board_from_before_columns_opens_in_one(board):
    notes = [BeeTextItem(text, pin={'order': order, 'minimized': False})
             for text, order in (('b', 1), ('a', 0), ('c', 2))]
    for note in notes:
        board.scene.addItem(note)
    board.place_pinned_notes()

    assert columns(board) == [['a', 'b', 'c']]
