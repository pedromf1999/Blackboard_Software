"""The pinned notes stand against each other in their tab, a gap apart."""

import pytest
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref.items import BeeTextItem
from . import test_pinned_notes
from .test_pinned_notes import mouse_move, note_at, pin


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


def shown(board, note):
    """Where the note is in the window: itself, or its label."""

    return board.pinned_element_rect(note)


def move_to(board, note, top_left, release=True):
    """Drag a note by its middle until its top left is at a point."""

    start = note.screen_rect(board).center().toPoint()
    shift = QtCore.QPointF(top_left) - note.screen_rect(board).topLeft()
    end = start + shift.toPoint()
    viewport = board.viewport()
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 9):
        mouse_move(viewport, start + (end - start) * step / 8)
    if release:
        QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier, end)
    return end


def beside(board, note):
    """A gap to the right of a note, level with its top."""

    rect = shown(board, note)
    return QtCore.QPointF(rect.right() + board.PINS_GAP + 2, rect.top())


def gap_between(a, b):
    across = max(b.left() - a.right(), a.left() - b.right())
    down = max(b.top() - a.bottom(), a.top() - b.bottom())
    return max(across, down)


def test_put_beside_a_note_it_stands_a_gap_from_it(board):
    first, second = pinned(board, 'first', 'second')

    move_to(board, second, beside(board, first))

    one, two = shown(board, first), shown(board, second)
    assert two.left() - one.right() == pytest.approx(board.PINS_GAP, abs=0.6)
    assert two.top() == pytest.approx(one.top(), abs=0.6)
    assert board.pins_tab_rect().contains(two)


def test_it_rises_until_it_is_a_gap_below_what_is_above(board):
    first, second, third = pinned(board, 'first', 'second', 'third')
    move_to(board, second, beside(board, first))

    # Let go of below the second, lower than it needs to be
    low = beside(board, first) + QtCore.QPointF(0, 45)
    move_to(board, third, low)

    two, three = shown(board, second), shown(board, third)
    assert three.left() == pytest.approx(two.left(), abs=0.6)
    assert three.top() - two.bottom() == pytest.approx(board.PINS_GAP,
                                                       abs=0.6)


def test_what_stands_beside_a_note_follows_it_as_it_grows(board):
    first, second = pinned(board, 'first', 'second')
    move_to(board, second, beside(board, first))

    board.set_pinned_note_minimized(first, True)
    assert shown(board, second).left() - shown(board, first).right() == (
        pytest.approx(board.PINS_GAP, abs=1))
    board.set_pinned_note_minimized(first, False)
    first.setTextWidth(first.textWidth() + 60
                       if first.textWidth() > 0 else 200)
    board.place_pinned_notes()

    assert shown(board, second).left() - shown(board, first).right() == (
        pytest.approx(board.PINS_GAP, abs=1))


def test_opening_a_note_moves_down_what_is_under_it(board):
    first, second = pinned(board, 'one\ntwo\nthree', 'below')
    board.set_pinned_note_minimized(first, True)
    before = shown(board, second).top()

    board.set_pinned_note_minimized(first, False)

    assert shown(board, second).top() > before
    assert shown(board, second).top() - shown(board, first).bottom() == (
        pytest.approx(board.PINS_GAP, abs=0.6))


def test_a_note_put_above_another_pushes_it_down(board):
    first, second, third = pinned(board, 'first', 'second', 'third')
    move_to(board, second, beside(board, first))
    above = beside(board, first) - QtCore.QPointF(0, 4)

    move_to(board, third, above)

    two, three = shown(board, second), shown(board, third)
    assert three.top() == pytest.approx(shown(board, first).top(), abs=0.6)
    assert two.top() - three.bottom() == pytest.approx(board.PINS_GAP,
                                                       abs=0.6)


def test_none_is_ever_within_a_gap_of_another(board):
    notes = pinned(board, 'one', 'two\nlines', 'three', 'four\nfive\nsix',
                   'seven')
    move_to(board, notes[1], beside(board, notes[0]))
    move_to(board, notes[3], beside(board, notes[1]))
    move_to(board, notes[4], beside(board, notes[0])
            + QtCore.QPointF(0, 30))
    board.set_pinned_note_minimized(notes[2], True)
    board.set_pinned_note_minimized(notes[1], True)

    rects = [shown(board, note) for note in notes]
    for index, rect in enumerate(rects):
        for other in rects[index + 1:]:
            assert gap_between(rect, other) >= board.PINS_GAP - 1
    tab = board.pins_tab_rect()
    assert all(tab.contains(rect) for rect in rects)


def test_its_buttons_take_no_room(board):
    note = note_at(board, QtCore.QPoint(100, 120), 'a fairly long line of '
                   'words, wider than the narrowest tab')
    pin(board, note)

    tab = board.pins_tab_rect()
    assert tab.width() == pytest.approx(
        note.screen_rect(board).width() + 2 * board.pins_tab.PADDING,
        abs=1)


def test_too_far_from_the_tab_it_goes_back(board):
    first, second = pinned(board, 'first', 'second')
    place = shown(board, second)

    move_to(board, second, place.topLeft() - QtCore.QPointF(500, 0))

    assert shown(board, second).topLeft() == place.topLeft()


def test_where_it_would_go_is_shown_while_it_is_in_hand(board):
    first, second = pinned(board, 'first', 'second')
    tab = board.pins_tab

    end = move_to(board, second, beside(board, first), release=False)
    assert tab.drop_kind == 'place'
    expected = tab.drop_rect.translated(board.pins_tab_rect().topLeft())
    # Over the other notes as it goes
    assert second.zValue() > first.zValue()
    QTest.mouseRelease(board.viewport(), Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, end)

    assert tab.drop_kind is None
    assert shown(board, second).topLeft() == expected.topLeft()
    assert second.zValue() == first.zValue() == BeeTextItem.PINNED_Z


def test_onto_another_note_it_still_swaps_with_it(board):
    first, second, third = pinned(board, 'first', 'second', 'third')
    move_to(board, second, beside(board, first))
    one = shown(board, first).topLeft()
    two = shown(board, second).topLeft()

    start = first.screen_rect(board).center().toPoint()
    end = second.screen_rect(board).center().toPoint()
    QTest.mousePress(board.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 9):
        mouse_move(board.viewport(), start + (end - start) * step / 8)
    assert board.pins_tab.drop_kind == 'swap'
    QTest.mouseRelease(board.viewport(), Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, end)

    assert shown(board, second).topLeft() == one
    assert shown(board, first).left() == pytest.approx(
        shown(board, second).right() + board.PINS_GAP, abs=0.6)
    assert two.y() == pytest.approx(shown(board, first).top(), abs=0.6)


def test_a_folded_label_is_put_beside_a_note_too(board):
    first, second = pinned(board, 'first', 'second')
    board.set_pinned_note_minimized(second, True)
    label = board.pinned_note_widgets[second][1]
    start = label.rect().center()
    target = beside(board, first) + QtCore.QPointF(
        label.width() / 2, label.height() / 2)
    target = board.viewport().mapToGlobal(target.toPoint())

    QTest.mousePress(label, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 9):
        wanted = label.mapFromGlobal(target)
        mouse_move(label, start + (wanted - start) * step / 8)
    assert board.pins_tab.drop_kind == 'place'
    QTest.mouseRelease(label, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, label.rect().center())

    assert second.is_minimized is True
    assert shown(board, second).left() - shown(board, first).right() == (
        pytest.approx(board.PINS_GAP, abs=1))


def test_unpinned_what_stood_beside_it_closes_the_gap(board):
    first, second, third = pinned(board, 'first', 'second', 'third')
    move_to(board, second, beside(board, first))
    move_to(board, third, beside(board, second))

    board.unpin_notes([second])

    assert shown(board, third).left() - shown(board, first).right() == (
        pytest.approx(board.PINS_GAP, abs=0.6))


def test_the_arrangement_is_saved_with_the_board(board, tmp_path):
    from beeref import fileio

    first, second, third = pinned(board, 'first', 'second', 'third')
    move_to(board, second, beside(board, first))
    move_to(board, third, beside(board, second))
    before = [shown(board, note).topLeft() for note in (first, second,
                                                        third)]
    filename = str(tmp_path / 'board.blk')
    fileio.save_bee(filename, board.scene, create_new=True)

    board.scene.clear()
    fileio.load_bee(filename, board.scene)
    board.scene.add_queued_items()
    board.place_pinned_notes()

    notes = sorted(board.scene.pinned_notes(),
                   key=lambda note: note.toPlainText())
    after = [shown(board, note).topLeft() for note in notes]
    assert after == before


def test_a_board_from_before_opens_with_them_one_under_another(board):
    notes = [BeeTextItem(text, pin={'order': order, 'minimized': False})
             for text, order in (('b', 1), ('a', 0), ('c', 2))]
    for note in notes:
        board.scene.addItem(note)
    board.place_pinned_notes()

    rects = sorted((shown(board, note) for note in notes),
                   key=lambda rect: rect.top())
    assert [rect.left() for rect in rects] == pytest.approx(
        [rects[0].left()] * 3)
    by_top = sorted(notes, key=lambda note: shown(board, note).top())
    assert [note.toPlainText() for note in by_top] == ['a', 'b', 'c']


def hover(board, point):
    mouse_move(board.viewport(), QtCore.QPointF(point).toPoint(),
               Qt.MouseButton.NoButton)


def test_the_buttons_show_only_while_the_mouse_is_over_the_note(board):
    first, second = pinned(board, 'first', 'second')
    one, two = (board.pinned_note_widgets[note][0]
                for note in (first, second))
    assert not one.isVisible() and not two.isVisible()

    hover(board, first.screen_rect(board).center())
    assert one.isVisible() and not two.isVisible()

    hover(board, QtCore.QPoint(5, 5))
    assert not one.isVisible() and not two.isVisible()


def test_on_a_titled_note_the_buttons_are_in_its_title_band(board):
    note = note_at(board, QtCore.QPoint(100, 120), 'Sketch\nModel')
    note.title = 'To do today'
    pin(board, note)
    controls = board.pinned_note_widgets[note][0]

    hover(board, note.screen_rect(board).center())

    band = note.deviceTransform(board.viewportTransform()).mapRect(
        note.header_rect())
    assert controls.isVisible() is True
    assert band.adjusted(-0.5, -0.5, 0.5, 0.5).contains(
        QtCore.QRectF(controls.geometry()))
    assert controls.geometry().right() > band.center().x()


def test_on_an_untitled_note_they_are_in_its_top_corner(board):
    note = note_at(board, QtCore.QPoint(100, 120),
                   'Call the workshop at three')
    pin(board, note)
    controls = board.pinned_note_widgets[note][0]

    hover(board, note.screen_rect(board).center())

    rect = note.screen_rect(board)
    geometry = QtCore.QRectF(controls.geometry())
    assert controls.isVisible() is True
    assert rect.contains(geometry)
    assert geometry.top() - rect.top() < 6
    assert rect.right() - geometry.right() < 6


def test_the_buttons_take_the_colour_they_sit_on(board):
    note = note_at(board, QtCore.QPoint(100, 120), 'Sketch')
    note.title = 'To do'
    note.header_color = QtGui.QColor(230, 150, 30)
    pin(board, note)
    controls = board.pinned_note_widgets[note][0]

    hover(board, note.screen_rect(board).center())

    assert note.visible_header_color().name() in controls.styleSheet()


def test_a_folded_note_or_tab_shows_no_buttons(board):
    first, second = pinned(board, 'first', 'second')
    board.set_pinned_note_minimized(first, True)
    hover(board, shown(board, first).center())
    assert not board.pinned_note_widgets[first][0].isVisible()

    board.set_pins_tab_folded(True)
    hover(board, board.pins_tab_rect().center())
    assert not board.pinned_note_widgets[second][0].isVisible()
