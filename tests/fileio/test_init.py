import os.path
import tempfile
from unittest.mock import MagicMock, patch

from PyQt6 import QtCore

from beeref import fileio
from beeref import commands
from ..utils import queue2list


@patch('beeref.fileio.sql.SQLiteIO.write')
def test_save_bee_create_new_false(write_mock):
    with tempfile.TemporaryDirectory() as dirname:
        fname = os.path.join(dirname, 'test.bee')
        fileio.save_bee(fname, 'myscene', create_new=False)
        write_mock.assert_called_once()


@patch('beeref.fileio.sql.SQLiteIO.read')
def test_read_bee(read_mock):
    with tempfile.TemporaryDirectory() as dirname:
        fname = os.path.join(dirname, 'test.bee')
        fileio.load_bee(fname, 'myscene')
        read_mock.assert_called_once()


def test_load_images_loads(view, imgfilename3x3):
    view.scene.undo_stack = MagicMock()
    worker = MagicMock(canceled=False)
    fileio.load_images([imgfilename3x3],
                       QtCore.QPointF(5, 6), view.scene, worker)
    worker.begin_processing.emit.assert_called_once_with(1)
    worker.progress.emit.assert_called_once_with(0)
    worker.finished.emit.assert_called_once_with('', [])
    itemdata = queue2list(view.scene.items_to_add)
    assert len(itemdata) == 1
    item = itemdata[0][0]['item']
    args = view.scene.undo_stack.push.call_args_list[0][0]
    cmd = args[0]
    assert isinstance(cmd, commands.InsertItems)
    assert cmd.items == [item]
    assert cmd.scene == view.scene
    assert cmd.ignore_first_redo is True
    assert item.pos() == QtCore.QPointF(3.5, 4.5)


def test_load_images_canceled(view, imgfilename3x3):
    view.scene.undo_stack = MagicMock()
    worker = MagicMock(canceled=True)
    fileio.load_images([imgfilename3x3, imgfilename3x3],
                       QtCore.QPointF(5, 6), view.scene, worker)
    worker.begin_processing.emit.assert_called_once_with(2)
    worker.progress.emit.assert_called_once_with(0)
    worker.finished.emit.assert_called_once_with('', [])
    itemdata = queue2list(view.scene.items_to_add)
    assert len(itemdata) == 1
    item = itemdata[0][0]['item']
    args = view.scene.undo_stack.push.call_args_list[0][0]
    cmd = args[0]
    assert isinstance(cmd, commands.InsertItems)
    assert cmd.items == [item]
    assert cmd.scene == view.scene
    assert cmd.ignore_first_redo is True
    assert item.pos() == QtCore.QPointF(3.5, 4.5)


def test_load_images_error(view, imgfilename3x3):
    view.scene.undo_stack = MagicMock()
    worker = MagicMock(canceled=False)
    fileio.load_images(['foo.jpg', imgfilename3x3],
                       QtCore.QPointF(5, 6), view.scene, worker)
    worker.begin_processing.emit.assert_called_once_with(2)
    worker.progress.emit.assert_any_call(0)
    worker.progress.emit.assert_any_call(1)
    worker.finished.emit.assert_called_once_with('', ['foo.jpg'])
    itemdata = queue2list(view.scene.items_to_add)
    assert len(itemdata) == 1
    item = itemdata[0][0]['item']
    args = view.scene.undo_stack.push.call_args_list[0][0]
    cmd = args[0]
    assert isinstance(cmd, commands.InsertItems)
    assert cmd.items == [item]
    assert cmd.scene == view.scene
    assert cmd.ignore_first_redo is True
    assert item.pos() == QtCore.QPointF(3.5, 4.5)


def test_load_images_goes_on_when_a_picture_goes_wrong(view, imgfilename3x3):
    """And says so when it is over: left untold, the dialog stayed up
    for good over a board that could no longer be used."""

    view.scene.undo_stack = MagicMock()
    worker = MagicMock(canceled=False)
    read = fileio.load_image

    def read_or_fail(filename):
        if filename == 'bad.png':
            raise RuntimeError('anything at all')
        return read(filename)

    with patch('beeref.fileio.load_image', side_effect=read_or_fail):
        fileio.load_images(['bad.png', imgfilename3x3],
                           QtCore.QPointF(5, 6), view.scene, worker)

    worker.progress.emit.assert_any_call(0)
    worker.progress.emit.assert_any_call(1)
    worker.finished.emit.assert_called_once_with('', ['bad.png'])
    assert len(queue2list(view.scene.items_to_add)) == 1


def test_a_dropped_picture_that_goes_wrong_is_named_by_its_address(view):
    view.scene.undo_stack = MagicMock()
    worker = MagicMock(canceled=False)
    dropped = QtCore.QUrl('file:///somewhere/shot.png')

    with patch('beeref.fileio.load_image', side_effect=OSError('gone')):
        fileio.load_images([dropped], QtCore.QPointF(5, 6), view.scene,
                           worker)

    worker.finished.emit.assert_called_once_with(
        '', ['file:///somewhere/shot.png'])


# A file taken away as soon as it has been dropped

def dropped_file(tmpdir, imgfilename3x3):
    import shutil
    path = os.path.normpath(str(tmpdir.join('Screenshot at 4.20 PM.png')))
    shutil.copy(imgfilename3x3, path)
    return path, QtCore.QUrl.fromLocalFile(path)


def take_away(path):
    """What a Mac does to the picture of a screenshot once it has been
    dropped. Windows will not take away a file that is held open, which
    does just as well."""

    try:
        os.remove(path)
    except PermissionError:
        pass


def test_a_picture_taken_away_after_the_drop_still_comes_in(
        view, tmpdir, imgfilename3x3):
    path, url = dropped_file(tmpdir, imgfilename3x3)
    view.scene.undo_stack = MagicMock()
    worker = MagicMock(canceled=False)

    held = fileio.held_open([url])
    take_away(path)
    fileio.load_images(held, QtCore.QPointF(5, 6), view.scene, worker)

    worker.finished.emit.assert_called_once_with('', [])
    assert len(queue2list(view.scene.items_to_add)) == 1


def test_left_to_be_opened_afterwards_it_is_gone(
        view, tmpdir, imgfilename3x3):
    """Which is what used to happen: "1 image could not be opened"."""

    path, url = dropped_file(tmpdir, imgfilename3x3)
    view.scene.undo_stack = MagicMock()
    worker = MagicMock(canceled=False)

    take_away(path)
    fileio.load_images([url], QtCore.QPointF(5, 6), view.scene, worker)

    worker.finished.emit.assert_called_once_with('', [path])


def test_files_never_reached_are_let_go_when_the_work_is_called_off(
        view, tmpdir, imgfilename3x3):
    path, url = dropped_file(tmpdir, imgfilename3x3)
    view.scene.undo_stack = MagicMock()
    worker = MagicMock(canceled=True)

    held = fileio.held_open([url, url])
    fileio.load_images(held, QtCore.QPointF(5, 6), view.scene, worker)

    assert [one[1].closed for one in held] == [True, True]
