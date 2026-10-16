"""The bar saying the open board was saved somewhere else, and taking
the newer version from it."""

import os
from unittest.mock import patch

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref.fileio.ondisk import looks
from beeref.items import BeeTextItem
from tests.elsewhere import save, saved_elsewhere, words_in


def bar_of(view):
    return view.elsewhere_bar


def looked_twice(view):
    """Two looks, as the timer takes them: the second finds it settled."""

    view.check_elsewhere()
    view.check_elsewhere()


def test_nothing_shown_for_a_board_left_alone(view, saved_board):
    looked_twice(view)
    assert bar_of(view).isHidden()


def test_nothing_shown_for_its_own_saves(view, qtbot, saved_board):
    view.scene.addItem(BeeTextItem('more'))
    save(view, qtbot, saved_board, create_new=False)
    looked_twice(view)
    assert bar_of(view).isHidden()


def test_shown_once_saved_elsewhere_and_settled(view, saved_board):
    saved_elsewhere(saved_board)
    view.check_elsewhere()
    # Perhaps still coming in: not read yet
    assert bar_of(view).isHidden()
    view.check_elsewhere()
    assert not bar_of(view).isHidden()
    assert 'saved somewhere else' in bar_of(view).words.text()
    assert bar_of(view).reload_button.text() == 'Reload'
    assert bar_of(view).copy_button.isHidden()


def test_a_file_still_changing_is_waited_for(view, saved_board):
    saved_elsewhere(saved_board)
    view.check_elsewhere()
    saved_elsewhere(saved_board, words='theirs, still coming')
    view.check_elsewhere()
    assert bar_of(view).isHidden()
    view.check_elsewhere()
    assert not bar_of(view).isHidden()


def test_with_changes_here_it_offers_to_keep_them(view, saved_board):
    view.scene.addItem(BeeTextItem('more'))
    view.undo_stack.resetClean()
    saved_elsewhere(saved_board)
    looked_twice(view)
    assert 'not saved' in bar_of(view).words.text()
    assert bar_of(view).reload_button.text() == 'Reload, Losing Mine'
    assert not bar_of(view).copy_button.isHidden()


def test_the_bar_follows_whether_changes_are_saved(view, saved_board):
    saved_elsewhere(saved_board)
    looked_twice(view)
    view.undo_stack.resetClean()
    assert not bar_of(view).copy_button.isHidden()
    view.undo_stack.setClean()
    assert bar_of(view).copy_button.isHidden()


def test_reload_reads_the_other_version_where_it_was_looked_at(
        view, qtbot, saved_board):
    view.scale(3, 3)
    view.centerOn(QtCore.QPointF(40, 30))
    transform = QtGui.QTransform(view.transform())
    center = view.mapToScene(view.viewport().rect().center())
    saved_elsewhere(saved_board, words='theirs', mark='their-mark')
    looked_twice(view)
    bar_of(view).reload_button.click()
    qtbot.waitUntil(lambda: view.on_disk.filename == saved_board,
                    timeout=10000)
    assert [item.toPlainText()
            for item in view.scene.items_by_type('text')] == ['theirs']
    assert view.transform() == transform
    now = view.mapToScene(view.viewport().rect().center())
    assert abs(now.x() - center.x()) <= 2 and abs(now.y() - center.y()) <= 2
    assert view.on_disk.mark == 'their-mark'
    assert bar_of(view).isHidden()
    assert view.undo_stack.isClean()


def test_after_reloading_saving_asks_nothing(view, qtbot, saved_board):
    saved_elsewhere(saved_board)
    looked_twice(view)
    view.reload_from_elsewhere()
    qtbot.waitUntil(lambda: view.on_disk.filename == saved_board,
                    timeout=10000)
    assert not view.on_disk.changed_elsewhere()


def test_opening_a_board_still_fits_it_to_the_window(view, qtbot, saved_board):
    with patch.object(view, 'on_action_fit_scene') as fit:
        view.open_from_file(saved_board)
        qtbot.waitUntil(lambda: view.on_disk.filename == saved_board,
                        timeout=10000)
    fit.assert_called_once()


def test_not_now_puts_it_away_until_it_changes_again(view, saved_board):
    saved_elsewhere(saved_board)
    looked_twice(view)
    bar_of(view).close_button.click()
    assert bar_of(view).isHidden()
    looked_twice(view)
    assert bar_of(view).isHidden()
    saved_elsewhere(saved_board, words='theirs again')
    looked_twice(view)
    assert not bar_of(view).isHidden()


def test_not_now_still_asks_before_saving_over_it(view, saved_board):
    saved_elsewhere(saved_board)
    looked_twice(view)
    view.dismiss_elsewhere()
    assert view.on_disk.changed_elsewhere()


def test_saving_mine_as_a_copy(view, qtbot, saved_board):
    view.scene.addItem(BeeTextItem('more'))
    view.undo_stack.resetClean()
    saved_elsewhere(saved_board)
    looked_twice(view)
    suggested = []

    def save_dialog(parent, caption, directory, filter):
        suggested.append(directory)
        return directory, filter

    with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName', save_dialog):
        bar_of(view).copy_button.click()
    qtbot.waitUntil(lambda: view.filename == suggested[0], timeout=10000)
    qtbot.waitUntil(lambda: view.undo_stack.isClean(), timeout=5000)
    assert words_in(suggested[0]) == ['mine', 'more']
    assert words_in(saved_board) == ['theirs']
    assert bar_of(view).isHidden()


def test_not_looked_at_while_this_window_reads_or_writes(view, saved_board):
    saved_elsewhere(saved_board)

    class Busy:
        def isRunning(self):
            return True

    view.worker = Busy()
    looked_twice(view)
    assert bar_of(view).isHidden()


def test_looked_at_on_coming_back_to_the_window(view, saved_board):
    saved_elsewhere(saved_board)
    view.check_elsewhere()
    view.on_application_state_for_elsewhere(
        Qt.ApplicationState.ApplicationActive)
    assert not bar_of(view).isHidden()


def test_a_new_board_puts_the_bar_away(view, saved_board):
    saved_elsewhere(saved_board)
    looked_twice(view)
    view.clear_scene()
    assert bar_of(view).isHidden()
    looked_twice(view)
    assert bar_of(view).isHidden()


def test_a_look_is_only_a_look_while_nothing_changed(view, saved_board):
    # Opening the file costs more than asking its size: only on change
    with patch('beeref.fileio.ondisk.read_mark') as read_mark:
        for _ in range(5):
            view.check_elsewhere()
    read_mark.assert_not_called()


def test_it_is_looked_at_every_two_seconds(view):
    assert view.elsewhere_timer.isActive()
    assert view.elsewhere_timer.interval() == 2000


def test_the_bar_sits_under_the_tool_bar(view, saved_board):
    view.resize(1200, 800)
    saved_elsewhere(saved_board)
    looked_twice(view)
    bar = bar_of(view)
    assert bar.y() > view.draw_toolbar.geometry().bottom()
    assert abs(bar.geometry().center().x() - view.width() // 2) <= 1


def test_looks_never_reads_a_missing_file(tmpdir):
    assert looks(os.path.join(str(tmpdir), 'missing.blk')) is None
