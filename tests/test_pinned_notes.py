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
    pin(board, note)
    assert note.is_pinned is True
    # In the tab of pinned notes
    assert board.pins_tab_rect().contains(note.screen_rect(board))
    before = note.screen_rect(board)

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


def test_dragged_onto_another_the_two_swap_and_it_is_no_edit(board):
    first = note_at(board, QtCore.QPoint(100, 120), text='first')
    second = note_at(board, QtCore.QPoint(100, 300), text='second\nnote')
    pin(board, first)
    pin(board, second)
    steps = board.undo_stack.count()
    assert [first.pin['order'], second.pin['order']] == [0, 1]
    board.scene.clearSelection()

    start = first.screen_rect(board).center().toPoint()
    end = second.screen_rect(board).center().toPoint()
    drag(board.viewport(), start, end)

    assert [first.pin['order'], second.pin['order']] == [1, 0]
    assert second.screen_rect(board).top() < first.screen_rect(board).top()
    assert board.undo_stack.count() == steps


def test_dragged_nowhere_in_particular_it_goes_back(board):
    first = note_at(board, QtCore.QPoint(100, 120), text='first')
    second = note_at(board, QtCore.QPoint(100, 300), text='second')
    pin(board, first)
    pin(board, second)
    place = first.screen_rect(board)
    board.scene.clearSelection()

    start = place.center().toPoint()
    drag(board.viewport(), start, QtCore.QPoint(150, 600))
    assert first.pin['order'] == 0
    assert close(first.screen_rect(board).topLeft(), place.topLeft())


def test_the_tab_keeps_to_its_corner_when_the_window_changes(
        board, main_window):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    board.scene.pins_tab['corner'] = [1, 1]
    board.scene.pins_tab['offset'] = [20, 30]
    board.place_pinned_notes()
    area = board.viewport().rect()
    rect = board.pins_tab_rect()
    assert rect.right() == pytest.approx(area.width() - 20)
    assert rect.bottom() == pytest.approx(area.height() - 30)
    assert rect.contains(note.screen_rect(board))

    main_window.resize(800, 600)
    QTest.qWait(50)
    area = board.viewport().rect()
    rect = board.pins_tab_rect()
    assert rect.right() == pytest.approx(area.width() - 20)
    assert rect.bottom() == pytest.approx(area.height() - 30)


def test_a_window_too_small_for_the_tab_keeps_it_in_sight(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    board.scene.pins_tab['corner'] = [0, 0]
    board.scene.pins_tab['offset'] = [5000, 5000]
    board.place_pinned_notes()

    assert board.viewport().rect().toRectF().contains(board.pins_tab_rect())
    # Its own place is kept, for when there is room again
    assert board.scene.pins_tab['offset'] == [5000, 5000]


def test_folded_away_it_leaves_a_label_in_its_corner(board):
    note = note_at(board, QtCore.QPoint(100, 120), text='Chair\nmodel it')
    pin(board, note)
    controls, label = board.pinned_note_widgets[note]
    # Its buttons show while the mouse is over it
    assert controls.isVisible() is False
    mouse_move(board.viewport(), note.screen_rect(board).center().toPoint(),
               Qt.MouseButton.NoButton)
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


def test_one_press_folds_the_tab_away_and_the_next_opens_it(board):
    first = note_at(board, QtCore.QPoint(100, 120))
    second = note_at(board, QtCore.QPoint(600, 120))
    pin(board, first)
    pin(board, second)
    open_height = board.pins_tab_rect().height()

    board.on_action_fold_pinned_notes()
    assert board.scene.pins_tab['minimized'] is True
    assert not first.isVisible() and not second.isVisible()
    assert board.pins_tab_rect().height() < open_height
    # Each note keeps whether it is open itself
    assert not first.is_minimized and not second.is_minimized

    board.on_action_fold_pinned_notes()
    assert first.isVisible() and second.isVisible()
    assert board.pins_tab_rect().height() == open_height


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


def test_a_folded_label_dragged_onto_a_note_swaps_with_it(board):
    first = note_at(board, QtCore.QPoint(100, 120), text='first')
    second = note_at(board, QtCore.QPoint(100, 300), text='second\nnote')
    pin(board, first)
    pin(board, second)
    board.set_pinned_note_minimized(first, True)
    label = board.pinned_note_widgets[first][1]
    start = label.rect().center()
    target = board.mapToGlobal(second.screen_rect(board).center().toPoint())

    QTest.mousePress(label, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, start)
    for step in range(1, 9):
        wanted = label.mapFromGlobal(target)
        mouse_move(label, start + (wanted - start) * step / 8)
    QTest.mouseRelease(label, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier, label.rect().center())

    # Put down, not opened, below the note it swapped with
    assert first.is_minimized is True
    assert [first.pin['order'], second.pin['order']] == [1, 0]
    assert label.geometry().top() > second.screen_rect(board).bottom()


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
    # The tab on the left, with room to grow into
    board.scene.pins_tab['corner'] = [0, 0]
    board.scene.pins_tab['offset'] = [16, 16]
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


def gaps(board):
    """The space between each pinned note and the next in the tab."""

    tops = []
    for note, slot in board.pin_slots:
        if note.is_minimized:
            label = board.pinned_note_widgets[note][1]
            rect = QtCore.QRectF(label.geometry())
        else:
            rect = note.screen_rect(board)
        tops.append(rect)
    return [below.top() - above.bottom()
            for above, below in zip(tops, tops[1:])]


def test_the_notes_in_the_tab_keep_a_gap_and_never_overlap(board):
    notes = [note_at(board, QtCore.QPoint(100, 100 + 100 * i), text=text)
             for i, text in enumerate(['one', 'two\nlines', 'three',
                                       'four\nfive\nsix'])]
    for note in notes:
        note.setScale(1.5)
        pin(board, note)
    board.set_pinned_note_minimized(notes[1], True)

    # Exactly the gap between each and the next: their buttons are
    # inside them, and take no room
    slots = [slot for _, slot in board.pin_slots]
    assert [below.top() - above.bottom()
            for above, below in zip(slots, slots[1:])] == pytest.approx(
                [board.PINS_GAP] * 3)
    assert gaps(board) == pytest.approx([board.PINS_GAP] * 3, abs=0.6)
    # And in the order they were pinned
    assert [note.pin['order'] for note in notes] == [0, 1, 2, 3]


def test_opening_or_folding_a_note_moves_the_ones_below(board):
    first = note_at(board, QtCore.QPoint(100, 120),
                    text='one\ntwo\nthree\nfour')
    second = note_at(board, QtCore.QPoint(100, 400), text='below')
    pin(board, first)
    pin(board, second)
    was = second.screen_rect(board).top()

    board.set_pinned_note_minimized(first, True)
    assert second.screen_rect(board).top() < was
    assert gaps(board) == pytest.approx([board.PINS_GAP], abs=0.6)

    board.set_pinned_note_minimized(first, False)
    assert second.screen_rect(board).top() == pytest.approx(was)


def test_the_tab_is_dragged_by_its_header_with_the_notes(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    tab = board.pins_tab
    before = board.pins_tab_rect()
    note_before = note.screen_rect(board)
    header = QtCore.QPoint(round(before.left() + 40),
                           round(before.top() + tab.HEADER / 2))

    drag(board.viewport(), header, header + QtCore.QPoint(-300, 250))
    after = board.pins_tab_rect()
    assert close(after.topLeft(), before.topLeft()
                 + QtCore.QPointF(-300, 250), tolerance=1)
    assert close(note.screen_rect(board).topLeft(),
                 note_before.topLeft() + QtCore.QPointF(-300, 250),
                 tolerance=1)
    # Kept there when the window changes size, from its nearest corner
    assert board.scene.pins_tab['corner'] == [1, 0]


def test_dragging_the_tab_moves_nothing_on_the_board(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    board.scene.clearSelection()
    board.picture.setSelected(True)
    where = board.picture.pos()
    steps = board.undo_stack.count()
    rect = board.pins_tab_rect()
    header = QtCore.QPoint(round(rect.left() + 40), round(rect.top() + 10))

    drag(board.viewport(), header, header + QtCore.QPoint(-200, 100))
    assert board.picture.pos() == where
    assert board.undo_stack.count() == steps


def test_the_tab_folds_away_by_its_button_and_opens_by_a_click(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    tab = board.pins_tab
    rect = board.pins_tab_rect()
    button = tab.button_rect()
    point = QtCore.QPoint(round(rect.left() + button.center().x()),
                          round(rect.top() + button.center().y()))

    QTest.mouseClick(board.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, point)
    assert board.scene.pins_tab['minimized'] is True
    assert note.isVisible() is False
    folded_rect = board.pins_tab_rect()
    assert folded_rect.height() == tab.HEADER

    QTest.mouseClick(board.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier,
                     folded_rect.center().toPoint())
    assert board.scene.pins_tab['minimized'] is False
    assert note.isVisible() is True


def test_a_double_click_on_the_tab_does_not_zoom_the_board(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    transform = board.transform()
    rect = board.pins_tab_rect()
    QTest.mouseDClick(board.viewport(), Qt.MouseButton.LeftButton,
                      Qt.KeyboardModifier.NoModifier,
                      QtCore.QPoint(round(rect.left() + 40),
                                    round(rect.top() + 10)))

    assert board.transform() == transform


def test_the_tab_goes_with_the_last_pinned_note(board):
    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    assert board.pins_tab.scene() is board.scene
    pin(board, note)
    assert board.pins_tab.scene() is None


def test_the_tab_is_saved_with_the_board(board, tmp_path):
    from beeref import fileio

    note = note_at(board, QtCore.QPoint(100, 120))
    pin(board, note)
    board.scene.pins_tab['corner'] = [0, 1]
    board.scene.pins_tab['offset'] = [30, 40]
    board.scene.pins_tab['minimized'] = True
    filename = str(tmp_path / 'board.blk')
    fileio.save_bee(filename, board.scene, create_new=True)

    board.scene.clear()
    assert board.scene.pins_tab == board.scene.PINS_TAB
    fileio.load_bee(filename, board.scene)
    board.scene.add_queued_items()
    assert board.scene.pins_tab == {
        'corner': [0, 1], 'offset': [30, 40], 'minimized': True}
    [opened] = board.scene.pinned_notes()
    assert opened.pin['order'] == 0


def test_a_board_from_before_the_tab_opens_with_one(board):
    old = BeeTextItem(pin={'corner': [1, 1], 'offset': [20, 30],
                           'minimized': False})
    board.scene.addItem(old)
    board.place_pinned_notes()

    assert board.pins_tab_rect().contains(old.screen_rect(board))
    assert old.pin['order'] == 0


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
