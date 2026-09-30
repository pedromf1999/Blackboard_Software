"""Notes pinned to the window: in sight wherever the board is moved."""

import pytest
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from beeref import commands
from beeref.items import BeeGroupItem, BeePixmapItem, BeeTextItem


@pytest.fixture
def board(main_window, view, qtbot):
    """A window on screen, with a picture on the board seen at 100%."""

    main_window.resize(1000, 700)
    main_window.show()
    qtbot.waitExposed(main_window)
    view.shortcuts_hint.hide()
    img = QtGui.QImage(400, 300, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(90, 90, 120))
    view.picture = BeePixmapItem(img)
    view.scene.addItem(view.picture)
    view.setTransform(QtGui.QTransform())
    view.centerOn(view.picture)
    return view


def note_at(view, point, text='one\ntwo'):
    """A note on the board, seen at the given point of the window."""

    note = BeeTextItem(text)
    view.scene.addItem(note)
    note.setPos(view.mapToScene(point))
    return note


def pin(view, note):
    view.scene.clearSelection()
    note.setSelected(True)
    view.on_action_pin_note()


def spot(view, note):
    return note.screen_rect(view).topLeft()


def close(a, b, tolerance=0.6):
    return abs(a.x() - b.x()) < tolerance and abs(a.y() - b.y()) < tolerance


def zoom_to(view, scale):
    view.setTransform(QtGui.QTransform.fromScale(scale, scale))


def test_a_pinned_note_stays_put_whatever_the_board_does(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    before = note.screen_rect(board)
    pin(board, note)
    assert note.is_pinned is True
    assert note.screen_rect(board) == before

    for _ in range(6):
        board.zoom(-400, QtCore.QPointF(500, 300))
    board.pan(QtCore.QPointF(-300, 200))
    for _ in range(9):
        board.zoom(400, QtCore.QPointF(200, 500))

    after = note.screen_rect(board)
    assert close(after.topLeft(), before.topLeft())
    assert abs(after.width() - before.width()) < 0.01


def test_it_is_pinned_at_the_size_it_is_seen(board):
    zoom_to(board, 2)
    note = note_at(board, QtCore.QPoint(100, 120))
    before = note.screen_rect(board)
    pin(board, note)

    assert note.scale() == pytest.approx(2)
    assert note.screen_rect(board).size() == before.size()


def test_one_pinned_far_zoomed_out_can_still_be_read(board):
    zoom_to(board, 0.05)
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)

    assert note.scale() == pytest.approx(board.PIN_MIN_SCALE)


def test_dragged_somewhere_else_it_stays_there_and_is_no_edit(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    steps = board.undo_stack.count()
    board.scene.clearSelection()

    start = note.screen_rect(board).center().toPoint()
    end = QtCore.QPoint(850, 600)
    QTest.mousePress(board.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 6):
        point = start + (end - start) * step / 5
        event = QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseMove, QtCore.QPointF(point),
            QtCore.QPointF(board.viewport().mapToGlobal(point)),
            Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier)
        QtGui.QGuiApplication.sendEvent(board.viewport(), event)
    QTest.mouseRelease(board.viewport(), Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, end)

    moved = note.screen_rect(board).center()
    assert close(moved, QtCore.QPointF(end), tolerance=2)
    # Kept from the corner it is now nearest
    assert note.pin['corner'] == [1, 1]
    assert board.undo_stack.count() == steps
    board.zoom(-500, QtCore.QPointF(100, 100))
    assert close(note.screen_rect(board).center(), moved)


def test_it_keeps_to_its_corner_when_the_window_changes(board, main_window):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    note.pin['corner'] = [1, 1]
    note.pin['offset'] = [20, 30]
    board.place_pinned_notes()
    area = board.viewport().rect()
    rect = note.screen_rect(board)
    assert rect.right() == pytest.approx(area.width() - 20)
    assert rect.bottom() == pytest.approx(area.height() - 30)

    main_window.resize(800, 600)
    QTest.qWait(50)
    area = board.viewport().rect()
    rect = note.screen_rect(board)
    assert rect.right() == pytest.approx(area.width() - 20)
    assert rect.bottom() == pytest.approx(area.height() - 30)


def test_a_window_too_small_for_its_spot_keeps_it_in_sight(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    note.pin['corner'] = [0, 0]
    note.pin['offset'] = [5000, 5000]
    board.place_pinned_notes()

    rect = note.screen_rect(board)
    assert board.viewport().rect().toRectF().contains(rect)
    # Its own spot is kept, for when there is room again
    assert note.pin['offset'] == [5000, 5000]


def test_folded_away_it_leaves_a_label_in_its_corner(board):
    note = note_at(board, QtCore.QPoint(100, 120), text='Chair\nmodel it')
    pin(board, note)
    controls, label = board.pinned_note_widgets[note]
    assert controls.isVisible() is True

    controls.minimize.click()
    assert note.is_minimized is True
    assert note.isVisible() is False
    assert label.isVisible() is True
    assert controls.isVisible() is False
    assert label.text() == 'Chair'
    assert close(QtCore.QPointF(label.pos()), spot(board, note), tolerance=1)

    label.click()
    assert note.isVisible() is True
    assert label.isVisible() is False


def test_a_label_says_the_title_when_there_is_one(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    note.title = 'To do'
    pin(board, note)
    board.set_pinned_note_minimized(note, True)

    _, label = board.pinned_note_widgets[note]
    assert label.text() == 'To do'


def test_one_press_folds_them_all_and_the_next_opens_them(board):
    first = note_at(board, QtCore.QPoint(100, 120))
    second = note_at(board, QtCore.QPoint(600, 120))
    pin(board, first)
    pin(board, second)

    board.on_action_fold_pinned_notes()
    assert first.is_minimized and second.is_minimized
    board.on_action_fold_pinned_notes()
    assert not first.is_minimized and not second.is_minimized


def test_saved_and_opened_again_it_is_still_pinned(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    note.set_minimized(True)
    data = note.get_extra_save_data()

    opened = BeeTextItem(**data)
    assert opened.is_pinned is True
    assert opened.pin == note.pin
    assert opened.is_minimized is True
    # And a note saved before there were pinned notes is not one
    assert BeeTextItem(text='old').is_pinned is False
    assert 'pin' not in BeeTextItem('old').get_extra_save_data()


def test_unpinned_it_goes_on_the_board_just_as_it_is_seen(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    zoom_to(board, 2)
    before = note.screen_rect(board)

    pin(board, note)
    assert note.is_pinned is False
    after = note.screen_rect(board)
    assert close(after.topLeft(), before.topLeft())
    assert after.width() == pytest.approx(before.width())
    # On the board again: it grows with the zoom
    zoom_to(board, 4)
    assert note.screen_rect(board).width() == pytest.approx(
        2 * before.width())


def test_pinning_is_one_step_to_undo_and_redo(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    scale, pos = note.scale(), note.pos()
    pin(board, note)

    board.undo_stack.undo()
    assert note.is_pinned is False
    assert note.scale() == scale
    assert note.pos() == pos
    board.undo_stack.redo()
    assert note.is_pinned is True


def test_pinned_out_of_a_group_and_put_back_by_undo(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    group = BeeGroupItem()
    commands.GroupItems(board.scene, [note, board.picture], group).redo()
    pin(board, note)
    assert note.parentItem() is None
    assert note not in group.bee_children()

    board.undo_stack.undo()
    assert note.parentItem() is group


def test_select_all_leaves_pinned_notes_out(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    board.on_action_select_all()

    assert board.picture.isSelected() is True
    assert note.isSelected() is False


def test_select_all_leaves_one_out_even_when_it_is_all_there_is(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    board.scene.removeItem(board.picture)
    board.scene.clearSelection()
    board.on_action_select_all()

    assert note.isSelected() is False


def test_a_selection_rectangle_never_takes_one_up(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    board.scene.clearSelection()
    board.scene.active_mode = board.scene.RUBBERBAND_MODE
    note.setSelected(True)
    board.scene.active_mode = None

    assert note.isSelected() is False


def test_the_board_is_measured_without_them(board):
    picture_rect = board.scene.itemsBoundingRect()
    note = note_at(board, QtCore.QPoint(900, 650))
    pin(board, note)

    assert board.scene.itemsBoundingRect() == picture_rect


def test_what_is_brought_to_the_front_stays_under_them(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    board.scene.clearSelection()
    board.picture.setSelected(True)
    board.on_action_raise_to_top()
    board.picture.bring_to_front()

    assert board.picture.zValue() < note.zValue()
    assert board.scene.max_z < note.zValue()


def test_a_copy_of_a_pinned_note_goes_on_the_board(board):
    zoom_to(board, 0.5)
    note = note_at(board, QtCore.QPoint(100, 120))
    note.setScale(2)
    pin(board, note)

    copy = note.create_copy()
    assert copy.is_pinned is False
    # The size it is seen at
    assert copy.scale() == pytest.approx(note.scale() / 0.5)


def test_a_pinned_note_never_joins_a_group(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    group = BeeGroupItem()
    commands.GroupItems(board.scene, [board.picture], group).redo()
    pin(board, note)
    under = group.mapToScene(group.rect().center())

    board.scene.put_in_group_at([note], under)
    assert note.parentItem() is None
    assert board.scene.get_drop_group(note) is None


def test_pictures_of_the_board_leave_them_out(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)

    with board.scene.pinned_notes_hidden():
        assert note.opacity() == 0
    assert note.opacity() == 1


def test_found_where_it_is_seen_at_any_zoom(board):
    zoom_to(board, 0.25)
    note = note_at(board, QtCore.QPoint(100, 120))
    note.setScale(4)
    pin(board, note)
    middle = note.screen_rect(board).center().toPoint()

    assert board.get_text_item_at(middle) is note
    # And a point of the board maps to the same point of the note that
    # the window shows there
    inside = QtCore.QPointF(10, 5)
    seen_at = note.deviceTransform(board.viewportTransform()).map(inside)
    board_point = board.mapToScene(seen_at.toPoint())
    assert close(note.mapFromScene(board_point), inside, tolerance=1)


def test_the_text_bar_shows_that_it_is_pinned(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    board.scene.clearSelection()
    note.setSelected(True)

    assert board.text_toolbar.pin.isChecked() is True
    board.on_action_pin_note()
    assert board.text_toolbar.pin.isChecked() is False


def test_found_by_a_search_it_opens_and_the_board_stays(board):
    note = note_at(board, QtCore.QPoint(100, 120), text='buy oak')
    pin(board, note)
    board.set_pinned_note_minimized(note, True)
    board.scene.clearSelection()
    transform = board.transform()
    centre = board.mapToScene(board.viewport().rect().center())

    board.text_search_query = 'oak'
    board.text_search_index = -1
    board.find_next_text_match()

    assert note.is_minimized is False
    assert note.isSelected() is True
    assert board.transform() == transform
    assert board.mapToScene(board.viewport().rect().center()) == centre


def mouse_move(widget, point, buttons=Qt.MouseButton.LeftButton):
    event = QtGui.QMouseEvent(
        QtCore.QEvent.Type.MouseMove, QtCore.QPointF(point),
        QtCore.QPointF(widget.mapToGlobal(point)),
        Qt.MouseButton.NoButton, buttons, Qt.KeyboardModifier.NoModifier)
    QtGui.QGuiApplication.sendEvent(widget, event)


def drag(widget, start, end, steps=8):
    QTest.mousePress(widget, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, steps + 1):
        mouse_move(widget, start + (end - start) * step / steps)
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, end)


def folded(board, note):
    pin(board, note)
    board.set_pinned_note_minimized(note, True)
    return board.pinned_note_widgets[note][1]


def test_a_folded_label_goes_where_it_is_dragged(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    label = folded(board, note)
    start = label.rect().center()
    target = board.mapToGlobal(QtCore.QPoint(700, 500))

    QTest.mousePress(label, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 9):
        wanted = label.mapFromGlobal(target)
        mouse_move(label, start + (wanted - start) * step / 8)
    QTest.mouseRelease(label, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, label.rect().center())
    dropped = label.geometry()

    # Put down, not opened, and left there by the view
    assert note.is_minimized is True
    assert dropped.center().x() > 500
    board.place_pinned_notes()
    assert label.geometry() == dropped
    # Opened, the note is in the corner the label marked
    label.click()
    rect = note.screen_rect(board)
    assert rect.right() == pytest.approx(dropped.x() + dropped.width())
    assert rect.bottom() == pytest.approx(dropped.y() + dropped.height())


def test_a_click_on_a_folded_label_still_opens_it(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    label = folded(board, note)
    QTest.mouseClick(label, Qt.MouseButton.LeftButton)

    assert note.is_minimized is False


def test_a_folded_label_takes_the_title_colour(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    note.title = 'To do'
    note.header_color = QtGui.QColor(230, 150, 30)
    label = folded(board, note)

    assert '#e6961e' in label.styleSheet()


def test_without_a_colour_of_its_own_the_label_is_the_box_colour(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    label = folded(board, note)

    assert note.visible_header_color().name() in label.styleSheet()


def test_a_pinned_note_is_made_wider_by_its_side(board):
    zoom_to(board, 0.5)
    note = note_at(board, QtCore.QPoint(100, 120),
                   text='Sketch the chair for the client\nModel it')
    note.setScale(3)
    pin(board, note)
    board.scene.clearSelection()
    note.setSelected(True)
    before = note.screen_rect(board)
    side = QtCore.QPoint(round(before.right()) - 1,
                         round(before.center().y()))

    drag(board.viewport(), side, side + QtCore.QPoint(100, 0))
    after = note.screen_rect(board)
    assert after.width() == pytest.approx(before.width() + 100, abs=2)
    assert after.left() == pytest.approx(before.left())
    assert board.undo_stack.undoText() == 'Change text width'
    # Kept where it was made wider, whatever the board does next
    board.zoom(-400, QtCore.QPointF(300, 300))
    assert close(note.screen_rect(board).topLeft(), after.topLeft())


def test_a_pinned_note_keeps_its_size_by_its_corners(board):
    note = note_at(board, QtCore.QPoint(100, 120),
                   text='Sketch the chair for the client\nModel it')
    note.setScale(2)
    pin(board, note)
    board.scene.clearSelection()
    note.setSelected(True)

    assert note.has_selection_handles()
    assert note.offers_corner_handles() is False
    assert list(note.corner_handles()) == []
    rect = note.screen_rect(board)
    corner = QtCore.QPoint(round(rect.right()) - 1,
                           round(rect.bottom()) - 1)
    drag(board.viewport(), corner, corner + QtCore.QPoint(60, 60))
    assert note.scale() == 2
    # A note on the board still has them
    assert BeeTextItem('x').offers_corner_handles() is True


def test_deleted_it_takes_its_buttons_with_it(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    assert note in board.pinned_note_widgets

    board.scene.clearSelection()
    note.setSelected(True)
    board.on_action_delete_items()
    board.place_pinned_notes()
    assert note not in board.pinned_note_widgets

    board.undo_stack.undo()
    board.place_pinned_notes()
    assert note.is_pinned is True
    assert note in board.pinned_note_widgets
