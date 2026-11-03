"""Scrolling the tab of pinned notes, when it is too tall for the window."""

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref.items import BeeTextItem


@pytest.fixture
def window(main_window, view, qtbot):
    """A window on screen, the board seen at 100%."""

    main_window.resize(1000, 700)
    main_window.show()
    qtbot.waitExposed(main_window)
    view.shortcuts_hint.hide()
    view.setTransform(QtGui.QTransform())
    return view


def pin(view, note):
    view.scene.clearSelection()
    note.setSelected(True)
    view.on_action_pin_note()
    view.scene.clearSelection()


def pinned_note(view, lines=80, word='line'):
    note = BeeTextItem('\n'.join(f'{word} {i}' for i in range(lines)))
    view.scene.addItem(note)
    note.setPos(view.mapToScene(QtCore.QPoint(100, 100)))
    pin(view, note)
    return note


@pytest.fixture
def tall(window):
    """A pinned note far taller than the window."""

    return pinned_note(window)


def wheel(view, point, notches, modifiers=Qt.KeyboardModifier.NoModifier,
          pixels=QtCore.QPoint(0, 0)):
    point = QtCore.QPointF(point)
    event = QtGui.QWheelEvent(
        point, QtCore.QPointF(view.mapToGlobal(point.toPoint())),
        pixels, QtCore.QPoint(0, 120 * notches), Qt.MouseButton.NoButton,
        modifiers, Qt.ScrollPhase.NoScrollPhase, False)
    QtWidgets.QApplication.sendEvent(view.viewport(), event)


def mouse(view, kind, point, buttons=Qt.MouseButton.LeftButton):
    point = QtCore.QPointF(point)
    button = (Qt.MouseButton.LeftButton
              if kind != QtCore.QEvent.Type.MouseMove
              else Qt.MouseButton.NoButton)
    event = QtGui.QMouseEvent(
        kind, point, QtCore.QPointF(view.mapToGlobal(point.toPoint())),
        button, buttons, Qt.KeyboardModifier.NoModifier)
    QtWidgets.QApplication.sendEvent(view.viewport(), event)


def in_tab(view):
    return view.pins_tab_rect().center()


def board_bars(view):
    return (view.horizontalScrollBar().value(),
            view.verticalScrollBar().value())


def test_a_tab_too_tall_for_the_window_is_kept_inside_it(window, tall):
    tab = window.pins_tab_rect()
    assert tab.bottom() <= window.viewport().height()
    assert tall.screen_rect(window).height() > tab.height()
    assert window.pins_tab.scrolled is not None
    assert window.pins_tab.scrollbar_rect() is not None


def test_a_short_tab_does_not_scroll(window):
    note = pinned_note(window, lines=3)
    assert window.pins_tab.scrolled is None
    assert window.pins_tab.scrollbar_rect() is None
    assert window.pins_clip is None
    assert note.pin_clip is None

    before = window.transform()
    wheel(window, in_tab(window), -3)
    # The wheel does what it always did there: zoom the board
    assert window.scene.pins_scroll == 0
    assert window.pending_zoom != 0 or window.transform() != before


def test_the_wheel_over_the_tab_scrolls_it(window, tall):
    top = tall.screen_rect(window).top()
    transform = window.transform()
    bars = board_bars(window)

    wheel(window, in_tab(window), -1)

    down = window.scene.pins_scroll
    assert down > 0
    assert tall.screen_rect(window).top() == pytest.approx(top - down)
    assert window.transform() == transform
    assert window.pending_zoom == 0
    assert board_bars(window) == bars


def test_the_wheel_goes_back_up(window, tall):
    wheel(window, in_tab(window), -2)
    down = window.scene.pins_scroll
    wheel(window, in_tab(window), 1)
    assert 0 < window.scene.pins_scroll < down


def test_it_stops_at_the_top_and_at_the_bottom(window, tall):
    wheel(window, in_tab(window), 5)
    assert window.scene.pins_scroll == 0

    wheel(window, in_tab(window), -500)
    offset, content, visible = window.pins_tab.scrolled
    assert offset == pytest.approx(content - visible)
    bottom = tall.screen_rect(window).bottom()
    assert bottom <= window.pins_tab_rect().bottom()
    assert bottom > window.pins_clip.bottom() - window.PINS_GAP * 3


def test_a_trackpad_scrolls_it_by_its_own_pixels(window, tall):
    wheel(window, in_tab(window), 0, pixels=QtCore.QPoint(0, -37))
    assert window.scene.pins_scroll == pytest.approx(37)


def test_with_a_key_held_the_wheel_is_the_board_s(window, tall):
    wheel(window, in_tab(window), -1, Qt.KeyboardModifier.ControlModifier)
    assert window.scene.pins_scroll == 0


def test_off_the_tab_the_wheel_is_the_board_s(window, tall):
    tab = window.pins_tab_rect()
    # The tab sits at the top right to begin with
    outside = QtCore.QPointF(tab.left() - 100, tab.center().y())
    assert window.viewport().rect().contains(outside.toPoint())
    wheel(window, outside, -1)
    assert window.scene.pins_scroll == 0
    assert window.pending_zoom != 0


def test_what_is_scrolled_under_the_header_is_cut_off(window, tall):
    wheel(window, in_tab(window), -5)
    assert tall.pin_clip is not None
    flags = QtWidgets.QGraphicsItem.GraphicsItemFlag
    assert tall.flags() & flags.ItemClipsToShape

    tab = window.pins_tab_rect()
    header = QtCore.QPoint(int(tab.left() + 40), int(tab.top() + 10))
    assert tall.screen_rect(window).contains(QtCore.QPointF(header))
    assert tall not in window.items(header)
    inside = QtCore.QPoint(int(tab.left() + 40), int(tab.center().y()))
    assert tall in window.items(inside)


def test_unpinned_it_is_whole_again(window, tall):
    wheel(window, in_tab(window), -5)
    assert tall.pin_clip is not None
    pin(window, tall)
    assert not tall.is_pinned
    assert tall.pin_clip is None
    flags = QtWidgets.QGraphicsItem.GraphicsItemFlag
    assert not tall.flags() & flags.ItemClipsToShape
    assert tall.shape().boundingRect().height() == pytest.approx(
        tall.boundingRect().height(), abs=1)


def test_the_bar_is_dragged(window, tall):
    tab = window.pins_tab_rect().topLeft()
    bar = window.pins_tab.scrollbar_rect().translated(tab)
    start = bar.center()
    mouse(window, QtCore.QEvent.Type.MouseButtonPress, start)
    mouse(window, QtCore.QEvent.Type.MouseMove,
          start + QtCore.QPointF(0, 100))
    mouse(window, QtCore.QEvent.Type.MouseButtonRelease,
          start + QtCore.QPointF(0, 100), Qt.MouseButton.NoButton)

    offset, content, visible = window.pins_tab.scrolled
    track = window.pins_tab.scrollbar_track()
    travel = track.height() - bar.height()
    assert offset == pytest.approx(100 / travel * (content - visible), abs=1)
    moved = window.pins_tab.scrollbar_rect().translated(tab)
    assert moved.top() == pytest.approx(bar.top() + 100, abs=1)


def test_pressed_below_the_bar_it_jumps_there(window, tall):
    tab = window.pins_tab_rect().topLeft()
    bar = window.pins_tab.scrollbar_rect().translated(tab)
    track = window.pins_tab.scrollbar_track().translated(tab)
    below = QtCore.QPointF(bar.center().x(), track.bottom() - 5)
    mouse(window, QtCore.QEvent.Type.MouseButtonPress, below)
    mouse(window, QtCore.QEvent.Type.MouseButtonRelease, below,
          Qt.MouseButton.NoButton)
    offset, content, visible = window.pins_tab.scrolled
    assert offset == pytest.approx(content - visible, abs=1)


def test_folding_the_tab_keeps_how_far_down_it_was(window, tall):
    wheel(window, in_tab(window), -3)
    down = window.scene.pins_scroll
    window.set_pins_tab_folded(True)
    assert window.pins_clip is None
    window.set_pins_tab_folded(False)
    assert window.scene.pins_scroll == pytest.approx(down)


def test_a_window_tall_enough_needs_no_scrolling(window, tall, main_window):
    wheel(window, in_tab(window), -3)
    tall.set_minimized(True)
    window.place_pinned_notes()
    assert window.pins_tab.scrolled is None
    assert window.scene.pins_scroll == 0
    assert window.pins_clip is None


def test_a_folded_note_scrolled_out_of_sight_is_hidden(window, tall):
    other = pinned_note(window, lines=2, word='other')
    window.set_pinned_note_minimized(other, True)
    label = window.pinned_note_widgets[other][1]
    # Under the tall note, below the bottom of the window
    assert label.isHidden()

    wheel(window, in_tab(window), -500)
    assert not label.isHidden()
    seen = window.pins_clip.intersected(QtCore.QRectF(label.geometry()))
    assert seen == QtCore.QRectF(label.geometry())


def test_a_folded_note_partly_in_sight_shows_only_that(window, tall):
    other = pinned_note(window, lines=2, word='other')
    window.set_pinned_note_minimized(other, True)
    label = window.pinned_note_widgets[other][1]
    wheel(window, in_tab(window), -500)
    height = label.height()
    clip = window.pins_clip
    window.scroll_pins_to(
        window.scene.pins_scroll - (clip.bottom() - label.y()) + height / 2)
    assert not label.isHidden()
    assert not label.mask().isEmpty()
    assert label.mask().boundingRect().height() < height


def test_writing_keeps_the_line_in_sight(window, tall, qtbot):
    tall.setSelected(True)
    tall.enter_edit_mode()
    cursor = tall.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
    tall.setTextCursor(cursor)
    tall.cursor_may_have_moved()
    qtbot.wait(10)

    line = tall.deviceTransform(window.viewportTransform()).mapRect(
        tall.words_rect(tall.textCursor().position()))
    assert window.scene.pins_scroll > 0
    assert window.pins_clip.contains(line)


@pytest.mark.parametrize('zoom', [0.25, 4])
def test_writing_leaves_the_board_where_it_is(window, tall, qtbot, zoom):
    # Qt reckons where the cursor is as if the note were on the board, at
    # the board's zoom: with the note's top scrolled out of the window,
    # that put the cursor out of sight, and Qt moved the board to show it
    window.setTransform(QtGui.QTransform.fromScale(zoom, zoom))
    tall.setSelected(True)
    tall.enter_edit_mode()
    cursor = tall.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
    tall.setTextCursor(cursor)
    tall.cursor_may_have_moved()
    qtbot.wait(10)
    assert tall.screen_rect(window).top() < 0
    bars = board_bars(window)

    for letter in 'more':
        qtbot.keyClick(window.viewport(), letter)
    qtbot.wait(10)

    assert tall.toPlainText().endswith('line 79more')
    assert board_bars(window) == bars


def test_a_search_brings_the_word_into_sight(window, tall):
    window.text_search_query = 'line 75'
    window.text_search_index = -1
    window.find_next_text_match()

    assert tall.isSelected()
    word = window.mapFromScene(
        tall.search_rect('line 75')).boundingRect()
    assert window.pins_clip.contains(QtCore.QRectF(word))


def test_the_bar_of_buttons_stays_level_with_what_is_seen(window, tall):
    wheel(window, in_tab(window), -10)
    assert tall.screen_rect(window).top() < window.pins_clip.top()
    tall.setSelected(True)
    window.update_text_toolbar()
    toolbar = window.text_toolbar
    assert not toolbar.isHidden()
    assert toolbar.y() >= window.pins_clip.top() - 1


def test_its_buttons_hide_with_its_band_scrolled_away(window, tall):
    wheel(window, in_tab(window), -10)
    controls = window.pinned_note_widgets[tall][0]
    point = window.pins_tab_rect().center()
    window.update_pinned_controls(point)
    assert controls.isHidden()


def test_its_buttons_show_with_its_band_in_sight(window, tall):
    controls = window.pinned_note_widgets[tall][0]
    point = tall.screen_rect(window).topLeft() + QtCore.QPointF(20, 20)
    window.update_pinned_controls(point)
    assert not controls.isHidden()


def test_how_far_down_is_not_kept_in_the_file(window, tall, tmp_path):
    wheel(window, in_tab(window), -3)
    assert 'scroll' not in window.scene.pins_tab
    path = str(tmp_path / 'scrolled.blk')
    window.do_save(path, create_new=True)
    while window.worker.isRunning():
        QtWidgets.QApplication.processEvents()
    window.open_from_file(path)
    while window.worker.isRunning():
        QtWidgets.QApplication.processEvents()
    QtWidgets.QApplication.processEvents()
    assert window.scene.pins_scroll == 0
