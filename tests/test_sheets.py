"""Several pages in one board file, each a board of its own from nothing,
with a tab along the top of the window that can be given a colour."""

import os
import sqlite3
from unittest.mock import patch

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtTest import QTest
import pytest

from beeref import commands
from beeref.actions import actions
from beeref.fileio.sql import SQLiteIO
from beeref.items import BeeGroupItem, BeePixmapItem, BeeTextItem
from beeref.scene import BeeGraphicsScene
from tests.elsewhere import save


def note(view, words, x=0, y=0):
    """A note put on the page shown, as a step to undo."""

    item = BeeTextItem(words)
    item.setPos(x, y)
    view.undo_stack.push(commands.InsertItems(view.scene, [item]))
    return item


def picture(view):
    img = QtGui.QImage(60, 40, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor('teal'))
    item = BeePixmapItem(img)
    view.undo_stack.push(commands.InsertItems(view.scene, [item]))
    return item


def words_on(scene):
    return sorted(item.toPlainText() for item in scene.items_by_type('text'))


def two_pages(view):
    """A note on each of two pages, showing the second."""

    note(view, 'first page')
    view.on_action_new_sheet()
    note(view, 'second page')
    return view.sheets.first, view.sheets.sheets[1]


def reopen(view, qtbot, path):
    view.open_from_file(path)
    qtbot.waitUntil(
        lambda: view.filename == path and not view.worker.isRunning(),
        timeout=10000)
    qtbot.waitUntil(lambda: not view.loading_overlay.isVisible(),
                    timeout=5000)


def saved_and_reopened(view, qtbot, tmpdir):
    path = os.path.join(tmpdir, 'board.blk')
    save(view, qtbot, path)
    reopen(view, qtbot, path)
    return path


def tables_in(path):
    connection = sqlite3.connect(path)
    try:
        return {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        connection.close()


def meta_keys_in(path):
    connection = sqlite3.connect(path)
    try:
        return {row[0] for row in connection.execute(
            'SELECT key FROM blackboard_meta')}
    finally:
        connection.close()


# Each a board of its own

def test_a_board_starts_with_one_page(view):
    assert len(view.sheets) == 1
    assert view.sheets.is_plain()
    assert view.scene is view.sheets.current.scene


def test_a_new_page_is_a_board_from_nothing(view):
    first, second = two_pages(view)
    assert view.sheets.current is second
    assert view.scene is second.scene
    assert view.undo_stack is second.undo_stack
    assert words_on(first.scene) == ['first page']
    assert words_on(second.scene) == ['second page']


def test_going_back_shows_what_was_there(view):
    first, second = two_pages(view)
    view.show_sheet(first)
    assert view.scene is first.scene
    assert QtWidgets.QGraphicsView.scene(view) is first.scene
    assert view.layers_dock.tree.scene is first.scene


def test_each_page_is_looked_at_from_where_it_was_left(view):
    first, second = two_pages(view)
    view.setTransform(QtGui.QTransform.fromScale(3, 3))
    view.show_sheet(first)
    view.setTransform(QtGui.QTransform.fromScale(0.5, 0.5))
    view.show_sheet(second)
    assert view.get_scale() == pytest.approx(3)
    view.show_sheet(first)
    assert view.get_scale() == pytest.approx(0.5)


def test_a_page_gone_to_for_the_first_time_is_seen_whole(view, tmpdir,
                                                         qtbot):
    first, second = two_pages(view)
    for n in range(4):
        note(view, f'far {n}', 3000 * n, 2000 * n)
    saved_and_reopened(view, qtbot, tmpdir)
    # The page it was saved on, seen whole
    far = view.sheets.current.scene.itemsBoundingRect()
    seen = view.mapToScene(view.viewport().rect()).boundingRect()
    assert seen.contains(far.center())
    assert seen.width() >= far.width() or seen.height() >= far.height()


def test_each_page_has_its_own_undo(view):
    first, second = two_pages(view)
    view.on_action_undo()
    assert words_on(second.scene) == []
    assert words_on(first.scene) == ['first page']
    view.show_sheet(first)
    view.on_action_undo()
    assert words_on(first.scene) == []


def test_undo_is_offered_for_the_page_shown(view):
    first, second = two_pages(view)
    view.on_action_undo()
    undo = view.bee_actiongroups['active_when_can_undo'][0]
    assert not undo.isEnabled()
    view.show_sheet(first)
    assert undo.isEnabled()
    view.show_sheet(second)
    assert not undo.isEnabled()


def test_what_is_chosen_is_let_go_on_leaving(view):
    first, second = two_pages(view)
    item = view.scene.items_by_type('text').__next__()
    item.setSelected(True)
    view.show_sheet(first)
    assert not item.isSelected()
    assert view.scene.selectedItems(user_only=True) == []


def test_a_note_being_written_is_finished_on_leaving(view):
    first, second = two_pages(view)
    item = view.scene.items_by_type('text').__next__()
    item.setSelected(True)
    item.enter_edit_mode()
    assert second.scene.edit_item is item
    view.show_sheet(first)
    assert second.scene.edit_item is None
    assert not item.edit_mode


def test_a_title_being_written_is_kept_on_leaving(view):
    first, second = two_pages(view)
    item = next(second.scene.items_by_type('text'))
    item.setSelected(True)
    item.enter_title_edit_mode()
    item.title_editor.setPlainText('Written')
    view.show_sheet(first)
    assert second.scene.title_item is None
    assert item.title == 'Written'


def test_a_legend_belongs_to_its_page(view):
    first, second = two_pages(view)
    second.scene.legend = [{'color': (1, 2, 3, 255), 'text': 'Here'}]
    view.refresh_legend()
    view.show_sheet(first)
    assert view.scene.legend == []
    view.show_sheet(second)
    assert view.scene.legend[0]['text'] == 'Here'


def test_a_pinned_note_stays_on_its_page(view):
    first, second = two_pages(view)
    item = next(second.scene.items_by_type('text'))
    view.pin_notes([item])
    view.show_sheet(first)
    assert item.is_pinned
    assert item.scene() is second.scene
    assert view.scene.pinned_notes() == []
    view.show_sheet(second)
    assert view.scene.pinned_notes() == [item]
    assert view.pins_tab.scene() is second.scene


def test_what_is_copied_can_be_pasted_on_another_page(view):
    first, second = two_pages(view)
    item = next(second.scene.items_by_type('text'))
    item.setSelected(True)
    second.scene.copy_selection_to_internal_clipboard()
    view.show_sheet(first)
    first.scene.paste_from_internal_clipboard(QtCore.QPointF(50, 50))
    assert words_on(first.scene) == ['first page', 'second page']
    assert words_on(second.scene) == ['second page']


def test_the_arrows_go_round_the_pages(view):
    first, second = two_pages(view)
    view.on_action_next_sheet()
    assert view.sheets.current is first
    view.on_action_previous_sheet()
    assert view.sheets.current is second


def test_no_going_to_another_page_while_the_file_is_in_use(view):
    first, second = two_pages(view)
    with patch.object(view, 'busy_with_file', return_value=True):
        view.choose_sheet(first)
    assert view.sheets.current is second


# An empty page

def test_an_empty_page_of_several_does_not_offer_to_open_a_board(view):
    """Choosing a file there would have replaced all of them."""

    two_pages(view)
    view.on_action_new_sheet()
    assert not view.scene.items()
    assert not view.welcome_overlay.isVisible()


def test_an_empty_page_can_still_save_the_others(view):
    two_pages(view)
    view.on_action_new_sheet()
    assert view.sheets.current.scene.items() == []
    assert actions.actions['save'].qaction.isEnabled()
    assert actions.actions['save_as'].qaction.isEnabled()


def test_a_board_file_dropped_on_an_empty_page_does_not_replace_it(view):
    two_pages(view)
    view.on_action_new_sheet()
    url = QtCore.QUrl.fromLocalFile('elsewhere.blk')
    mimedata = QtCore.QMimeData()
    mimedata.setUrls([url])
    event = QtGui.QDropEvent(
        QtCore.QPointF(5, 5), QtCore.Qt.DropAction.CopyAction, mimedata,
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.NoModifier)
    with patch.object(view, 'open_from_file') as opened, \
            patch.object(view, 'do_insert_images'):
        view.dropEvent(event)
    opened.assert_not_called()


# Whether there is anything to save

def test_changes_on_a_page_not_shown_still_count(view):
    first, second = two_pages(view)
    view.sheets.set_clean()
    view.update_window_title()
    assert '*' not in view.parent.windowTitle()
    note(view, 'more')
    view.show_sheet(first)
    assert not view.sheets.is_clean()
    assert '*' in view.parent.windowTitle()


def test_naming_colouring_and_moving_pages_are_changes_to_save(view):
    first, second = two_pages(view)
    for change in (lambda: view.rename_sheet(second, 'Lid'),
                   lambda: view.move_sheet(0, 1)):
        view.sheets.set_clean()
        assert view.sheets.is_clean()
        change()
        assert not view.sheets.is_clean()
        assert '*' in view.parent.windowTitle()


def test_going_to_another_page_is_not_a_change(view):
    first, second = two_pages(view)
    view.sheets.set_clean()
    view.show_sheet(first)
    assert view.sheets.is_clean()


# Its tab

def test_there_is_a_tab_for_each_page(view):
    tabs = view.sheet_tabs.tabs
    assert tabs.count() == 1
    first, second = two_pages(view)
    assert tabs.count() == 2
    assert tabs.tabText(1) == second.name
    assert tabs.currentIndex() == 1


def test_choosing_a_tab_goes_to_its_page(view):
    first, second = two_pages(view)
    view.sheet_tabs.tabs.setCurrentIndex(0)
    assert view.sheets.current is first


def test_moving_a_tab_moves_its_page(view):
    first, second = two_pages(view)
    view.sheet_tabs.tabs.moveTab(0, 1)
    assert view.sheets.sheets == [second, first]
    assert view.sheets.current is second
    assert view.sheet_tabs.tabs.currentIndex() == 0


def test_the_button_for_another_page_is_beside_the_tabs(view, qtbot):
    view.parent.show()
    qtbot.waitExposed(view.parent)
    QtWidgets.QApplication.processEvents()
    bar = view.sheet_tabs
    gap = bar.new_sheet.x() - bar.tabs.tabRect(0).right()
    assert 0 <= gap <= 6


def test_the_tab_being_dragged_is_drawn_in_its_own_colour(view, qtbot):
    """Not the picture Qt drags about, which stays where it started and
    is in the colours of the style."""

    first, second = two_pages(view)
    view.show_sheet(first)
    color_chosen(view, first, QtGui.QColor(200, 30, 40))
    view.parent.show()
    qtbot.waitExposed(view.parent)
    tabs = view.sheet_tabs.tabs
    start = tabs.tabRect(0).center()
    QTest.mousePress(tabs, QtCore.Qt.MouseButton.LeftButton, pos=start)
    for step in range(1, 11):
        point = start + QtCore.QPoint(5 * step, 0)
        QtWidgets.QApplication.sendEvent(tabs, QtGui.QMouseEvent(
            QtCore.QEvent.Type.MouseMove, QtCore.QPointF(point),
            QtCore.QPointF(tabs.mapToGlobal(point)),
            QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.KeyboardModifier.NoModifier))
    tabs.repaint()
    moving = [child for child in tabs.children()
              if isinstance(child, QtWidgets.QWidget)
              and child.metaObject().className() == 'QWidget']
    assert len(moving) == 1
    assert moving[0].isHidden()
    # Its own colour, where it has been dragged to, on top of the other
    image = tabs.grab().toImage()
    spot = tabs.tabRect(0).center() + QtCore.QPoint(50, -8)
    assert image.pixelColor(spot) == QtGui.QColor(200, 30, 40)
    QTest.mouseRelease(tabs, QtCore.Qt.MouseButton.LeftButton,
                       pos=start + QtCore.QPoint(50, 0))


def test_with_many_pages_the_tabs_scroll(view, qtbot):
    """A window's bar would have put them away in a menu of its own."""

    view.parent.resize(600, 400)
    view.parent.show()
    qtbot.waitExposed(view.parent)
    for _ in range(30):
        view.on_action_new_sheet()
    QtWidgets.QApplication.processEvents()
    bar = view.sheet_tabs
    assert bar.tabs.isVisible() and bar.new_sheet.isVisible()
    assert bar.new_sheet.geometry().right() < bar.width()
    assert bar.tabs.tabRect(bar.tabs.currentIndex()).right() <= (
        bar.tabs.width())


def test_a_new_page_has_a_name_of_its_own(view):
    first, second = two_pages(view)
    view.rename_sheet(second, 'Page 3')
    view.on_action_new_sheet()
    assert len({sheet.name for sheet in view.sheets}) == 3


def test_a_name_left_empty_is_not_taken(view):
    first, second = two_pages(view)
    view.rename_sheet(second, '   ')
    assert second.name == 'Page 2'


def test_the_tab_is_renamed_in_place(view, qtbot):
    first, second = two_pages(view)
    tabs = view.sheet_tabs.tabs
    tabs.rename(1)
    tabs.editor.setText('Battery')
    tabs.editor.finish()
    assert second.name == 'Battery'
    assert tabs.tabText(1) == 'Battery'


def test_escape_leaves_the_name_as_it_was(view):
    first, second = two_pages(view)
    tabs = view.sheet_tabs.tabs
    tabs.rename(1)
    tabs.editor.setText('Battery')
    tabs.editor.keyPressEvent(QtGui.QKeyEvent(
        QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Escape,
        QtCore.Qt.KeyboardModifier.NoModifier))
    assert second.name == 'Page 2'


def color_chosen(view, sheet, color):
    with patch.object(view, 'pick_color_live', return_value=color):
        view.pick_sheet_color(sheet)


def test_a_tab_is_given_a_colour_and_the_board_is_not(view):
    first, second = two_pages(view)
    background = QtGui.QBrush(view.backgroundBrush())
    color_chosen(view, second, QtGui.QColor(200, 30, 40))
    assert second.color == (200, 30, 40, 255)
    assert view.backgroundBrush() == background
    assert first.color is None


def test_a_colour_can_be_taken_off_again(view):
    first, second = two_pages(view)
    color_chosen(view, second, QtGui.QColor(200, 30, 40))
    color_chosen(view, second, QtGui.QColor())
    assert second.color is None


def test_cancelling_the_colour_leaves_it_as_it_was(view):
    first, second = two_pages(view)
    color_chosen(view, second, QtGui.QColor(200, 30, 40))
    view.sheets.set_clean()
    color_chosen(view, second, None)
    assert second.color == (200, 30, 40, 255)
    assert view.sheets.is_clean()


def test_the_colour_is_shown_on_the_tab(view, qtbot):
    first, second = two_pages(view)
    view.parent.show()
    qtbot.waitExposed(view.parent)
    color_chosen(view, first, QtGui.QColor(200, 30, 40))
    tabs = view.sheet_tabs.tabs
    second_color = QtGui.QColor(30, 200, 40)
    color_chosen(view, second, second_color)
    QtWidgets.QApplication.processEvents()
    image = tabs.grab().toImage()
    # Near the left end of the selected tab, under its rounded corner
    rect = tabs.tabRect(1)
    assert image.pixelColor(rect.left() + 4, rect.center().y()) == second_color


# Taken away

def test_an_empty_page_is_deleted_without_asking(view):
    first, second = two_pages(view)
    view.on_action_new_sheet()
    third = view.sheets.current
    view.delete_sheet(third)
    assert third not in view.sheets.sheets
    assert view.sheets.current is second


def test_a_page_with_things_on_it_is_asked_about(view):
    first, second = two_pages(view)
    button = QtWidgets.QMessageBox.StandardButton
    with patch.object(QtWidgets.QMessageBox, 'question',
                      return_value=button.Cancel):
        view.delete_sheet(second)
    assert second in view.sheets.sheets
    with patch.object(QtWidgets.QMessageBox, 'question',
                      return_value=button.Yes):
        view.delete_sheet(second)
    assert view.sheets.sheets == [first]
    assert view.scene is first.scene


def test_the_last_page_cannot_be_deleted(view):
    view.delete_sheet(view.sheets.current)
    assert len(view.sheets) == 1


def test_a_new_board_is_back_to_one_page(view):
    first, second = two_pages(view)
    second.color = (1, 2, 3, 255)
    view.clear_scene()
    assert len(view.sheets) == 1
    assert view.sheets.is_plain()
    assert view.sheet_tabs.tabs.count() == 1
    assert view.scene is first.scene
    assert view.scene.items() == []


# In the file

def test_a_file_keeps_its_pages_and_what_is_on_them(view, qtbot, tmpdir):
    first, second = two_pages(view)
    view.rename_sheet(first, 'Lid')
    view.rename_sheet(second, 'Battery')
    color_chosen(view, second, QtGui.QColor(10, 20, 30))
    picture(view)
    saved_and_reopened(view, qtbot, tmpdir)
    assert [sheet.name for sheet in view.sheets] == ['Lid', 'Battery']
    lid, battery = view.sheets.sheets
    assert words_on(lid.scene) == ['first page']
    assert words_on(battery.scene) == ['second page']
    assert len(list(battery.scene.items_by_type('pixmap'))) == 1
    assert len(list(lid.scene.items_by_type('pixmap'))) == 0
    assert battery.color == (10, 20, 30, 255)
    assert lid.color is None
    assert view.sheets.is_clean()
    assert view.sheet_tabs.tabs.count() == 2


def test_it_opens_on_the_page_it_was_saved_on(view, qtbot, tmpdir):
    first, second = two_pages(view)
    saved_and_reopened(view, qtbot, tmpdir)
    assert view.sheets.current is view.sheets.sheets[1]
    assert view.scene is view.sheets.sheets[1].scene
    view.show_sheet(view.sheets.first)
    path = view.filename
    save(view, qtbot, path, create_new=False)
    reopen(view, qtbot, path)
    assert view.sheets.current is view.sheets.first


def test_groups_stay_on_their_page(view, qtbot, tmpdir):
    first, second = two_pages(view)
    one = note(view, 'one')
    two = note(view, 'two', 400, 0)
    group = BeeGroupItem()
    view.undo_stack.push(commands.GroupItems(view.scene, [one, two], group))
    saved_and_reopened(view, qtbot, tmpdir)
    page = view.sheets.sheets[1]
    groups = list(page.scene.items_by_type('group'))
    assert len(groups) == 1
    assert sorted(c.toPlainText() for c in groups[0].bee_children()) == [
        'one', 'two']


def test_each_page_keeps_its_legend_and_pinned_notes(view, qtbot, tmpdir):
    first, second = two_pages(view)
    first.scene.legend = [{'color': (1, 2, 3, 255), 'text': 'Mine'}]
    second.scene.legend = [{'color': (4, 5, 6, 255), 'text': 'Yours'}]
    second.scene.pins_tab['minimized'] = True
    item = next(second.scene.items_by_type('text'))
    view.pin_notes([item])
    saved_and_reopened(view, qtbot, tmpdir)
    one, two = view.sheets.sheets
    assert one.scene.legend[0]['text'] == 'Mine'
    assert two.scene.legend[0]['text'] == 'Yours'
    assert two.scene.pins_tab['minimized'] is True
    assert one.scene.pins_tab['minimized'] is False
    assert [n.toPlainText() for n in two.scene.pinned_notes()] == [
        'second page']
    assert one.scene.pinned_notes() == []


def test_saved_again_nothing_moves_or_goes(view, qtbot, tmpdir):
    two_pages(view)
    path = saved_and_reopened(view, qtbot, tmpdir)
    page = view.sheets.sheets[1]
    view.show_sheet(page)
    note(view, 'added later')
    view.show_sheet(view.sheets.first)
    note(view, 'and here')
    save(view, qtbot, path, create_new=False)
    reopen(view, qtbot, path)
    one, two = view.sheets.sheets
    assert words_on(one.scene) == ['and here', 'first page']
    assert words_on(two.scene) == ['added later', 'second page']


def test_deleted_from_a_page_is_gone_from_the_file(view, qtbot, tmpdir):
    two_pages(view)
    path = saved_and_reopened(view, qtbot, tmpdir)
    page = view.sheets.sheets[1]
    item = next(page.scene.items_by_type('text'))
    page.scene.removeItem(item)
    save(view, qtbot, path, create_new=False)
    reopen(view, qtbot, path)
    assert words_on(view.sheets.sheets[1].scene) == []
    assert words_on(view.sheets.sheets[0].scene) == ['first page']


def test_save_as_keeps_every_page(view, qtbot, tmpdir):
    two_pages(view)
    picture(view)
    path = saved_and_reopened(view, qtbot, tmpdir)
    other = os.path.join(tmpdir, 'copy.blk')
    save(view, qtbot, other)
    reopen(view, qtbot, other)
    assert view.filename == other and path != other
    one, two = view.sheets.sheets
    assert words_on(one.scene) == ['first page']
    assert words_on(two.scene) == ['second page']
    assert len(list(two.scene.items_by_type('pixmap'))) == 1


def test_pages_put_in_another_order_keep_what_is_on_them(view, qtbot, tmpdir):
    first, second = two_pages(view)
    view.move_sheet(0, 1)
    saved_and_reopened(view, qtbot, tmpdir)
    now_first, now_second = view.sheets.sheets
    assert now_first.name == 'Page 2'
    assert words_on(now_first.scene) == ['second page']
    assert words_on(now_second.scene) == ['first page']


def test_a_deleted_page_is_gone_from_the_file(view, qtbot, tmpdir):
    two_pages(view)
    path = saved_and_reopened(view, qtbot, tmpdir)
    page = view.sheets.sheets[1]
    with patch.object(
            QtWidgets.QMessageBox, 'question',
            return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        view.delete_sheet(page)
    save(view, qtbot, path, create_new=False)
    reopen(view, qtbot, path)
    assert len(view.sheets) == 1
    assert words_on(view.scene) == ['first page']


# And what was there before

def test_a_board_of_one_page_is_the_file_it_always_was(view, qtbot, tmpdir):
    note(view, 'alone')
    path = os.path.join(tmpdir, 'board.blk')
    save(view, qtbot, path)
    assert 'blackboard_item_sheets' not in tables_in(path)
    assert 'sheets' not in meta_keys_in(path)


def test_back_down_to_one_page_it_is_that_file_again(view, qtbot, tmpdir):
    two_pages(view)
    path = saved_and_reopened(view, qtbot, tmpdir)
    assert 'blackboard_item_sheets' in tables_in(path)
    with patch.object(
            QtWidgets.QMessageBox, 'question',
            return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        view.delete_sheet(view.sheets.sheets[1])
    save(view, qtbot, path, create_new=False)
    assert 'blackboard_item_sheets' not in tables_in(path)
    assert 'sheets' not in meta_keys_in(path)


def test_one_page_with_a_name_keeps_it(view, qtbot, tmpdir):
    note(view, 'alone')
    view.rename_sheet(view.sheets.current, 'Lid')
    saved_and_reopened(view, qtbot, tmpdir)
    assert view.sheets.current.name == 'Lid'


def test_a_version_that_knows_nothing_of_pages_loses_nothing(view, qtbot,
                                                             tmpdir):
    """It reads the items and tables it knows of; every item of every
    page is among them."""

    two_pages(view)
    path = os.path.join(tmpdir, 'board.blk')
    save(view, qtbot, path)
    scene = BeeGraphicsScene(QtGui.QUndoStack())
    SQLiteIO(path, scene, readonly=True).read()
    scene.add_queued_items()
    assert words_on(scene) == ['first page', 'second page']
    # Its next save leaves the page each item is on alone
    SQLiteIO(path, scene).write()
    reopen(view, qtbot, path)
    assert words_on(view.sheets.sheets[1].scene) == ['second page']
    assert words_on(view.sheets.sheets[0].scene) == ['first page']


def test_what_a_version_without_pages_adds_lands_on_the_first(view, qtbot,
                                                              tmpdir):
    two_pages(view)
    path = os.path.join(tmpdir, 'board.blk')
    save(view, qtbot, path)
    scene = BeeGraphicsScene(QtGui.QUndoStack())
    SQLiteIO(path, scene, readonly=True).read()
    scene.add_queued_items()
    scene.addItem(BeeTextItem('from an old version'))
    SQLiteIO(path, scene).write()
    reopen(view, qtbot, path)
    assert words_on(view.sheets.first.scene) == [
        'first page', 'from an old version']
    assert words_on(view.sheets.sheets[1].scene) == ['second page']


def test_an_unknown_item_on_a_page_stays_there_and_is_kept(view, qtbot,
                                                           tmpdir):
    two_pages(view)
    path = os.path.join(tmpdir, 'board.blk')
    save(view, qtbot, path)
    connection = sqlite3.connect(path)
    cursor = connection.execute(
        "INSERT INTO items (type, x, y, z, scale, rotation, flip, data) "
        "VALUES ('from_the_future', 0, 0, 0, 1, 0, 1, '{}')")
    unknown = cursor.lastrowid
    connection.execute(
        'INSERT INTO blackboard_item_sheets (item_id, sheet_id) '
        'VALUES (?, ?)', (unknown, view.sheets.sheets[1].id))
    connection.commit()
    connection.close()
    reopen(view, qtbot, path)
    page = view.sheets.sheets[1]
    assert len(list(page.scene.items_by_type('error'))) == 1
    assert len(list(view.sheets.first.scene.items_by_type('error'))) == 0
    view.on_disk.remember(path)
    save(view, qtbot, path, create_new=False)
    reopen(view, qtbot, path)
    assert len(list(view.sheets.sheets[1].scene.items_by_type('error'))) == 1


def test_pages_the_file_says_nonsense_about_do_not_stop_it_opening(
        view, qtbot, tmpdir):
    two_pages(view)
    path = os.path.join(tmpdir, 'board.blk')
    save(view, qtbot, path)
    connection = sqlite3.connect(path)
    connection.execute(
        "UPDATE blackboard_meta SET value='not json' WHERE key='sheets'")
    connection.commit()
    connection.close()
    reopen(view, qtbot, path)
    assert len(view.sheets) == 1
    assert words_on(view.scene) == ['first page', 'second page']
