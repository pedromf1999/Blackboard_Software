"""What keeps a full board quick to move and zoom."""

from unittest.mock import patch

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref import commands
from beeref.items import BeeGroupItem, BeePixmapItem, BeeTextItem


KEPT = QtWidgets.QGraphicsItem.CacheMode.DeviceCoordinateCache
NOT_KEPT = QtWidgets.QGraphicsItem.CacheMode.NoCache


def picture(view, x=0, y=0, width=200, height=150):
    img = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(90, 90, 120))
    item = BeePixmapItem(img)
    view.scene.addItem(item)
    item.setPos(x, y)
    return item


def task_note(view):
    """A list of three things to do, written and put away."""

    from .test_task_lists import task_note as written
    note = written(view)
    note.exit_edit_mode()
    return note


# What a note counts once for each change of its words

def test_a_note_counts_its_lines_once_for_each_change(view):
    note = task_note(view)
    note.task_blocks()
    with patch.object(note.document(), 'begin',
                      wraps=note.document().begin) as begin:
        for _ in range(20):
            note.task_blocks()
            note.done_count()
            note.largest_point_size()
            note.box_rect()
    begin.assert_not_called()


def test_ticking_a_box_is_counted_straight_away(view):
    note = task_note(view)
    assert note.done_count() == 0
    [first, *_] = note.task_blocks()

    note.set_task_done(first, True)

    assert note.done_count() == 1
    assert len(note.task_blocks(done=False)) == 2


def test_new_words_are_counted_straight_away(view):
    note = task_note(view)
    assert len(note.task_blocks()) == 3

    note.setPlainText('just words')

    assert note.task_blocks() == []
    assert note.done_count() == 0


def test_bigger_letters_are_counted_straight_away(view):
    note = BeeTextItem('words')
    view.scene.addItem(note)
    before = note.largest_point_size()
    cursor = QtGui.QTextCursor(note.document())
    cursor.select(QtGui.QTextCursor.SelectionType.Document)
    size = QtGui.QTextCharFormat()
    size.setFontPointSize(40)
    cursor.mergeCharFormat(size)

    assert note.largest_point_size() == 40
    assert note.largest_point_size() != before


def test_a_title_band_is_measured_again_when_the_title_changes(view):
    note = BeeTextItem('words')
    view.scene.addItem(note)
    note.title = 'Short'
    short = note.header_height()
    assert note.header_height() == short

    note.title = 'A title long enough to need more room than the other'
    note.setTextWidth(80)

    assert note.header_height() > 0
    group = BeeGroupItem()
    view.scene.addItem(group)
    picture(view).setParentItem(group)
    group.fit_to_children()
    group.title = 'Lid'
    one_line = group.header_height()
    group.title = 'Lid latch, ' * 30
    assert group.header_height() > one_line


# The board measured by what stands on it

def test_the_board_is_measured_by_what_stands_on_it(view):
    first = picture(view, 0, 0)
    second = picture(view, 600, 400)
    group = BeeGroupItem()
    commands.GroupItems(view.scene, [first, second], group).redo()
    loose = picture(view, -500, -300)

    rect = view.scene.itemsBoundingRect()

    everything = QtCore.QRectF()
    for item in (group, first, second, loose):
        everything = everything.united(item.mapToScene(
            item.bounding_rect_unselected()).boundingRect())
    assert rect == everything


# The layers panel, left alone while it is put away

def test_a_put_away_layers_panel_is_not_rebuilt(view):
    tree = view.layers_dock.tree
    assert view.layers_dock.collapsed is True
    with patch.object(tree, 'get_signature') as signature:
        picture(view)
        tree.schedule_refresh()
        QtWidgets.QApplication.processEvents()
    signature.assert_not_called()


def test_opened_again_it_shows_what_was_added_meanwhile(view):
    tree = view.layers_dock.tree
    picture(view)
    tree.schedule_refresh()

    view.on_action_show_layers(True)

    assert tree.topLevelItemCount() == 1


# Every item kept drawn

def test_every_item_is_kept_drawn(view):
    note = BeeTextItem('words')
    view.scene.addItem(note)
    group = BeeGroupItem()
    view.scene.addItem(group)

    assert picture(view).cacheMode() == KEPT
    assert note.cacheMode() == KEPT
    assert group.cacheMode() == KEPT


def test_a_picture_of_the_board_is_drawn_afresh(view):
    item = picture(view)

    with view.scene.drawn_afresh():
        assert item.cacheMode() == NOT_KEPT
    assert item.cacheMode() == KEPT


def test_exporting_draws_afresh(view):
    from beeref.fileio.export import SceneToPixmapExporter

    item = picture(view)
    seen = []
    original = BeePixmapItem.paint

    def paint(self, painter, option, widget):
        seen.append(self.cacheMode())
        return original(self, painter, option, widget)

    exporter = SceneToPixmapExporter(view.scene)
    exporter.size = QtCore.QSize(200, 150)
    with patch.object(BeePixmapItem, 'paint', paint):
        exporter.render_to_image()

    assert seen and all(mode == NOT_KEPT for mode in seen)
    assert item.cacheMode() == KEPT


def test_choosing_a_second_item_redraws_the_first(view):
    """Its handles go: they only show while it is the one chosen."""

    first = picture(view)
    second = picture(view, 400, 0)
    first.setSelected(True)

    with patch.object(BeePixmapItem, 'update') as update:
        second.setSelected(True)

    assert update.call_count >= 2


def test_a_new_board_colour_redraws_everything(view):
    picture(view)
    note = BeeTextItem('words')
    view.scene.addItem(note)

    with patch.object(BeePixmapItem, 'update') as pictures, \
            patch.object(BeeTextItem, 'update') as notes:
        view.on_canvas_color_changed('#404040')

    pictures.assert_called()
    notes.assert_called()


# Zooming from a picture of the board

@pytest.fixture
def board(main_window, view, qtbot):
    main_window.resize(900, 600)
    main_window.show()
    qtbot.waitExposed(main_window)
    view.shortcuts_hint.hide()
    for column in range(4):
        picture(view, column * 250, 0)
    view.setTransform(QtGui.QTransform())
    view.centerOn(QtCore.QPointF(450, 75))
    return view


def centre(view):
    return QtCore.QPointF(view.viewport().width() / 2,
                          view.viewport().height() / 2)


def test_a_zoom_is_drawn_from_a_picture_of_the_board(board):
    board.zoom(120, centre(board))

    assert board.quick_zoom is not None
    picture_of_board, seen_as = board.quick_zoom
    assert picture_of_board.deviceIndependentSize().toSize() == (
        board.viewport().size())
    # Taken before the zoom step
    assert seen_as.m11() == pytest.approx(1)


def test_it_is_drawn_sharp_again_once_the_zoom_stops(board, qtbot):
    board.zoom(120, centre(board))
    assert board.quick_zoom is not None

    qtbot.waitUntil(lambda: board.quick_zoom is None,
                    timeout=board.QUICK_ZOOM_SETTLE * 10)


def test_the_picture_follows_the_zoom(board):
    board.zoom(120, centre(board))
    board.zoom(120, centre(board))

    shown = board.viewport().grab().toImage()
    board.end_quick_zoom()
    sharp = board.viewport().grab().toImage()

    # The same board, in the same place: only a little softer at the
    # edges of things. The middle of a picture is the same colour.
    middle = board.mapFromScene(QtCore.QPointF(350, 75))
    assert shown.pixelColor(middle) == sharp.pixelColor(middle)
    assert sharp.pixelColor(middle) == QtGui.QColor(90, 90, 120)


def test_it_is_taken_again_once_scaled_too_far(board):
    board.zoom(120, centre(board))
    first = board.quick_zoom[0]
    for _ in range(12):
        board.zoom(120, centre(board))

    assert board.quick_zoom[0] is not first


def test_a_press_ends_it_at_once(board):
    from PyQt6.QtTest import QTest

    board.zoom(120, centre(board))
    QTest.mousePress(board.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, QtCore.QPoint(5, 5))
    QTest.mouseRelease(board.viewport(), Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, QtCore.QPoint(5, 5))

    assert board.quick_zoom is None


def test_pinned_notes_stay_out_of_the_picture(board):
    note = BeeTextItem('pinned')
    board.scene.addItem(note)
    board.scene.clearSelection()
    note.setSelected(True)
    board.on_action_pin_note()
    board.scene.clearSelection()

    board.zoom(120, centre(board))

    # Put back as they were once the picture was taken
    assert note.opacity() == 1
    assert board.quick_zoom is not None


# What is kept drawn always matches what the item is

def differences(view):
    """How many sampled pixels of the window differ from the board drawn
    afresh, with nothing kept."""

    viewport = view.viewport()
    viewport.repaint()
    shown = viewport.grab().toImage()
    with view.scene.drawn_afresh():
        viewport.repaint()
        fresh = viewport.grab().toImage()
    viewport.repaint()
    return sum(1 for x in range(0, shown.width(), 3)
               for y in range(0, shown.height(), 3)
               if shown.pixel(x, y) != fresh.pixel(x, y))


@pytest.fixture
def wide_note(main_window, view, qtbot):
    """A note wider than the window it is seen in."""

    main_window.resize(900, 600)
    main_window.show()
    qtbot.waitExposed(main_window)
    view.shortcuts_hint.hide()
    note = BeeTextItem('a very long note ' * 12)
    view.scene.addItem(note)
    view.setTransform(QtGui.QTransform.fromScale(2, 2))
    view.centerOn(QtCore.QPointF(150, 10))
    view.viewport().repaint()
    assert note.sceneBoundingRect().width() * 2 > view.viewport().width()
    return note


def test_a_note_wider_than_the_window_is_drawn_true_when_chosen(
        view, wide_note):
    """Chosen, it grows on every side for its handles; what was kept of
    it was put back out of place."""

    wide_note.setSelected(True)
    assert differences(view) <= 2
    view.scene.clearSelection()
    assert differences(view) <= 2


def test_and_when_it_is_given_a_title(view, wide_note):
    wide_note.title = 'A title'
    assert differences(view) <= 2


@pytest.fixture
def set_width_note(main_window, view, qtbot):
    """A note of a set width, which what is typed does not make wider."""

    main_window.resize(900, 600)
    main_window.show()
    qtbot.waitExposed(main_window)
    view.shortcuts_hint.hide()
    # A cursor that blinked between the two pictures compared would
    # count as a difference
    flash_time = QtWidgets.QApplication.cursorFlashTime()
    QtWidgets.QApplication.setCursorFlashTime(0)
    note = BeeTextItem('Ribs', text_width=300)
    view.scene.addItem(note)
    view.setTransform(QtGui.QTransform.fromScale(2, 2))
    view.centerOn(note)
    view.viewport().repaint()
    yield note
    QtWidgets.QApplication.setCursorFlashTime(flash_time)
    # Nothing left chosen or being written when the window goes
    if note.edit_mode:
        note.exit_edit_mode(commit=False)
    view.scene.clearSelection()


def write_at_the_end(view, note, words):
    """What typing after the note's last word amounts to."""

    note.enter_edit_mode()
    cursor = note.textCursor()
    cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
    note.setTextCursor(cursor)
    view.viewport().repaint()
    for char in words:
        note.sceneEvent(QtGui.QKeyEvent(
            QtCore.QEvent.Type.KeyPress, Qt.Key.Key_A,
            Qt.KeyboardModifier.NoModifier, char))


def test_what_is_typed_into_a_note_of_a_set_width_is_drawn(
        view, set_width_note):
    """Qt asks for the words after a change to be drawn again as a
    rectangle too big for what is kept of the note, and none of it was:
    what was typed stayed out of sight until the writing ended."""

    write_at_the_end(view, set_width_note, ' and what was typed')
    assert differences(view) <= 2


def test_and_into_a_pinned_note(view, set_width_note):
    view.scene.clearSelection()
    set_width_note.setSelected(True)
    view.on_action_pin_note()
    view.viewport().repaint()

    write_at_the_end(view, set_width_note, ' and what was typed')
    assert differences(view) <= 2
