"""A board saved on another computer, through a folder that syncs:
knowing it, and never saving over it unasked."""

import os
from unittest.mock import patch

from PyQt6 import QtCore, QtGui, QtWidgets

from beeref.fileio.ondisk import BoardOnDisk, looks, read_mark
from beeref.fileio.sql import SQLiteIO
from beeref.items import BeeTextItem
from beeref.scene import BeeGraphicsScene
from tests.elsewhere import finished_saving, save, saved_elsewhere, words_in


def answering(text):
    """Have the question about saving answered by pressing this."""

    def exec_(box):
        for button in box.buttons():
            if button.text().replace('&', '') == text:
                button.click()
                return 0
        raise AssertionError(
            f'No {text}: {[b.text() for b in box.buttons()]}')

    return patch.object(QtWidgets.QMessageBox, 'exec', exec_)


def never_asked():
    def exec_(box):
        raise AssertionError(f'Asked: {box.text()}')

    return patch.object(QtWidgets.QMessageBox, 'exec', exec_)


# The marks

def test_a_save_leaves_its_mark(view, saved_board):
    assert view.on_disk.mark
    assert read_mark(saved_board) == view.on_disk.mark
    assert view.on_disk.looked == looks(saved_board)


def test_every_save_leaves_a_new_mark(view, qtbot, saved_board):
    first = view.on_disk.mark
    view.scene.addItem(BeeTextItem('more'))
    save(view, qtbot, saved_board, create_new=False)
    assert view.on_disk.mark != first
    assert read_mark(saved_board) == view.on_disk.mark


def test_opening_remembers_the_mark_in_the_file(view, qtbot, tmpdir):
    path = os.path.join(str(tmpdir), 'other.blk')
    saved_elsewhere(path, mark='written-there')
    view.open_from_file(path)
    qtbot.waitUntil(lambda: view.on_disk.filename == path, timeout=10000)
    assert view.on_disk.mark == 'written-there'


def test_a_file_without_a_mark(tmpdir):
    path = os.path.join(str(tmpdir), 'old.blk')
    scene = BeeGraphicsScene(QtGui.QUndoStack())
    SQLiteIO(path, scene, create_new=True).write()
    assert read_mark(path) is None
    assert read_mark(os.path.join(str(tmpdir), 'missing.blk')) is None
    other = os.path.join(str(tmpdir), 'not-a-board.blk')
    with open(other, 'wb') as f:
        f.write(b'nothing like a board')
    assert read_mark(other) is None


def test_reading_the_mark_changes_nothing(tmpdir):
    path = os.path.join(str(tmpdir), 'board.blk')
    saved_elsewhere(path)
    before = looks(path)
    read_mark(path)
    assert looks(path) == before


# Knowing

def test_untouched_is_not_changed(saved_board):
    on_disk = BoardOnDisk()
    on_disk.remember(saved_board)
    assert not on_disk.changed_elsewhere()


def test_touched_with_its_own_mark_is_not_changed(saved_board):
    # As a sync program does to a file it uploads
    on_disk = BoardOnDisk()
    on_disk.remember(saved_board)
    looked = looks(saved_board)
    os.utime(saved_board, ns=(looked[1] + 5 * 10**9, looked[1] + 5 * 10**9))
    assert not on_disk.changed_elsewhere()
    assert on_disk.looked == looks(saved_board)


def test_saved_elsewhere_is_changed(saved_board):
    on_disk = BoardOnDisk()
    on_disk.remember(saved_board)
    saved_elsewhere(saved_board)
    assert on_disk.changed_elsewhere()


def test_a_file_without_marks_is_known_by_its_looks(tmpdir):
    path = os.path.join(str(tmpdir), 'old.blk')
    scene = BeeGraphicsScene(QtGui.QUndoStack())
    SQLiteIO(path, scene, create_new=True).write()
    on_disk = BoardOnDisk()
    on_disk.remember(path)
    assert not on_disk.changed_elsewhere()
    scene.addItem(BeeTextItem('more'))
    SQLiteIO(path, scene, create_new=True).write()
    looked = looks(path)
    os.utime(path, ns=(looked[1] + 2 * 10**9, looked[1] + 2 * 10**9))
    assert on_disk.changed_elsewhere()


def test_a_file_gone_is_not_changed(saved_board):
    on_disk = BoardOnDisk()
    on_disk.remember(saved_board)
    os.remove(saved_board)
    assert not on_disk.changed_elsewhere()


def test_a_new_board_has_no_file_to_watch(view, saved_board):
    view.clear_scene()
    assert view.on_disk.filename is None
    assert not view.on_disk.changed_elsewhere()


# Saving

def test_saving_as_usual_asks_nothing(view, qtbot, saved_board):
    view.scene.addItem(BeeTextItem('more'))
    with never_asked():
        view.on_action_save()
    finished_saving(view, qtbot)
    assert words_in(saved_board) == ['mine', 'more']


def test_saving_over_a_version_from_elsewhere_asks(view, saved_board):
    saved_elsewhere(saved_board)
    with answering('Cancel'), patch.object(view, 'do_save') as do_save:
        view.on_action_save()
    do_save.assert_not_called()
    assert words_in(saved_board) == ['theirs']


def test_replacing_it_writes_this_board_whole(view, qtbot, saved_board):
    # Written as usual, only what changed, into the other version: the
    # two boards would be mixed up
    saved_elsewhere(saved_board)
    view.scene.addItem(BeeTextItem('more'))
    with answering('Replace It'):
        view.on_action_save()
    finished_saving(view, qtbot)
    assert words_in(saved_board) == ['mine', 'more']
    assert read_mark(saved_board) == view.on_disk.mark
    assert not view.on_disk.changed_elsewhere()


def test_saving_as_a_copy_keeps_both(view, qtbot, saved_board):
    saved_elsewhere(saved_board)
    suggested = []

    def save_dialog(parent, caption, directory, filter):
        suggested.append(directory)
        return directory, filter

    with answering('Save as a Copy...'), patch(
            'PyQt6.QtWidgets.QFileDialog.getSaveFileName', save_dialog):
        view.on_action_save()
    qtbot.waitUntil(lambda: not view.worker.isRunning(), timeout=10000)
    qtbot.waitUntil(lambda: view.filename == suggested[0], timeout=5000)
    computer = QtCore.QSysInfo.machineHostName()
    assert os.path.basename(suggested[0]) == f'board ({computer}).blk'
    assert os.path.dirname(suggested[0]) == os.path.dirname(saved_board)
    assert words_in(saved_board) == ['theirs']
    assert words_in(suggested[0]) == ['mine']


def test_the_copy_dialog_dismissed_saves_nothing(view, saved_board):
    saved_elsewhere(saved_board)
    with answering('Save as a Copy...'), patch(
            'PyQt6.QtWidgets.QFileDialog.getSaveFileName',
            return_value=('', '')), patch.object(view, 'do_save') as do_save:
        view.on_action_save()
    do_save.assert_not_called()


def test_closing_and_cancelling_the_question_keeps_the_board_open(
        view, saved_board):
    # Saving on the way out, which waits for the save
    saved_elsewhere(saved_board)
    view.scene.addItem(BeeTextItem('more'))
    with answering('Cancel'):
        assert view.save_and_wait() is False
    assert words_in(saved_board) == ['theirs']


def test_save_as_somewhere_new_asks_nothing(view, qtbot, saved_board, tmpdir):
    saved_elsewhere(saved_board)
    other = os.path.join(str(tmpdir), 'new.blk')
    with never_asked(), patch(
            'PyQt6.QtWidgets.QFileDialog.getSaveFileName',
            return_value=(other, '')):
        view.on_action_save_as()
    qtbot.waitUntil(lambda: not view.worker.isRunning(), timeout=10000)
    qtbot.waitUntil(lambda: view.filename == other, timeout=5000)
    assert view.on_disk.filename == other
