"""Opening a large board quickly: the log written without asking the
disk, pictures' small copies opened side by side, progress shown no
more often than the eye can follow."""

from concurrent.futures import ThreadPoolExecutor
import logging
import os
from unittest.mock import MagicMock, patch

from PyQt6 import QtCore, QtGui

from beeref import imagecache
from beeref.fileio.sql import SQLiteIO
from beeref.items import BeePixmapItem, BeeTextItem
from beeref.logging import BeeRotatingFileHandler
from beeref.widgets import BeeProgressDialog


def record(text):
    return logging.LogRecord('beeref', logging.DEBUG, __file__, 1, text,
                             None, None)


def test_the_log_is_written_without_asking_the_disk(tmpdir):
    path = os.path.join(str(tmpdir), 'log.txt')
    handler = BeeRotatingFileHandler(path, maxBytes=10000, backupCount=1)
    handler.emit(record('first'))
    with patch('os.path.exists') as exists, patch('os.path.isfile') as isfile:
        for n in range(50):
            handler.emit(record(f'line {n}'))
    exists.assert_not_called()
    isfile.assert_not_called()
    handler.close()
    with open(path) as f:
        assert len(f.read().splitlines()) == 51


def test_the_log_still_starts_a_new_file_when_full(tmpdir):
    path = os.path.join(str(tmpdir), 'log.txt')
    handler = BeeRotatingFileHandler(path, maxBytes=200, backupCount=1)
    for n in range(40):
        handler.emit(record(f'a line of the log, number {n}'))
    handler.close()
    assert os.path.exists(path + '.1')
    assert os.path.getsize(path) < 200


def test_the_log_counts_what_was_there_already(tmpdir):
    path = os.path.join(str(tmpdir), 'log.txt')
    with open(path, 'w') as f:
        f.write('x' * 190)
    handler = BeeRotatingFileHandler(path, maxBytes=200, backupCount=1)
    handler.emit(record('a line long enough to go past the end'))
    handler.close()
    assert os.path.exists(path + '.1')


# Reading a board

def board_of_pictures(view, tmpfile, count=9):
    colours = []
    for n in range(count):
        image = QtGui.QImage(40 + n, 30, QtGui.QImage.Format.Format_RGB32)
        colour = QtGui.QColor.fromHsv(n * 30, 200, 200)
        image.fill(colour)
        colours.append(colour.name())
        item = BeePixmapItem(image)
        item.setPos(n * 100, 0)
        view.scene.addItem(item)
    view.scene.addItem(BeeTextItem('and a note'))
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.write()
    view.scene.clear()
    return colours


def read(view, tmpfile):
    worker = MagicMock(canceled=False)
    io = SQLiteIO(tmpfile, view.scene, readonly=True, worker=worker)
    io.read()
    view.scene.add_queued_items()
    return worker


def test_pictures_come_in_with_their_small_copies(view, tmpfile):
    colours = board_of_pictures(view, tmpfile)
    read(view, tmpfile)
    pictures = sorted(view.scene.items_by_type('pixmap'),
                      key=lambda item: item.pos().x())
    assert [item.image_size().width() for item in pictures] == [
        40 + n for n in range(9)]
    assert [item._thumbnail.pixelColor(5, 5).name() for item in pictures] \
        == colours


def test_small_copies_are_opened_side_by_side(view, tmpfile):
    board_of_pictures(view, tmpfile)
    with patch('beeref.fileio.sql.ThreadPoolExecutor',
               wraps=ThreadPoolExecutor) as pool:
        read(view, tmpfile)
    pool.assert_called_once()
    assert pool.call_args[0][0] >= 1


def test_items_are_handed_over_in_the_order_of_the_file(view, tmpfile):
    board_of_pictures(view, tmpfile)
    worker = read(view, tmpfile)
    steps = [call[0][0] for call in worker.progress.emit.call_args_list]
    assert steps == list(range(10))
    worker.finished.emit.assert_called_once()


def test_a_picture_that_cannot_be_read_is_an_error_item(view, tmpfile):
    board_of_pictures(view, tmpfile, count=2)
    io = SQLiteIO(tmpfile, view.scene)
    io.ex('UPDATE sqlar SET data = ? WHERE item_id = '
          '(SELECT MIN(item_id) FROM sqlar)', (b'not a picture',))
    io.connection.commit()
    read(view, tmpfile)
    assert len(list(view.scene.items_by_type('error'))) == 1
    assert len(list(view.scene.items_by_type('pixmap'))) == 1


def test_small_copy():
    image = QtGui.QImage(1000, 500, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('red'))
    buffer = QtCore.QBuffer()
    buffer.open(buffer.OpenModeFlag.WriteOnly)
    image.save(buffer, 'PNG')
    size, small = imagecache.small_copy(bytes(buffer.data()))
    assert (size.width(), size.height()) == (1000, 500)
    assert max(small.width(), small.height()) == imagecache.THUMBNAIL_SIDE


def test_small_copy_of_something_else():
    size, small = imagecache.small_copy(b'not a picture')
    assert small.isNull()


# Progress

def test_progress_is_shown_no_more_often_than_can_be_seen(view):
    dialog = BeeProgressDialog('Loading', worker=MagicMock(), parent=view)
    dialog.setMaximum(1000)
    with patch.object(dialog, 'setValue') as shown:
        for n in range(200):
            dialog.on_progress(n)
    assert 1 <= shown.call_count < 20
    dialog.deleteLater()


def test_the_last_step_is_always_shown(view):
    dialog = BeeProgressDialog('Loading', worker=MagicMock(), parent=view)
    dialog.setMaximum(10)
    dialog.on_progress(1)
    with patch.object(dialog, 'setValue') as shown:
        dialog.on_progress(9)
    shown.assert_called_once_with(9)
    dialog.deleteLater()


# Settings

def test_a_picture_asks_for_the_settings_only_when_it_needs_them(view):
    with patch('beeref.items.BeeSettings') as settings:
        item = BeePixmapItem(QtGui.QImage(10, 10,
                                          QtGui.QImage.Format.Format_RGB32))
        assert settings.call_count == 0
        item.settings
        item.settings
    assert settings.call_count == 1
