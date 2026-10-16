"""Boards saved on another computer, for the tests about them."""

import os

from PyQt6 import QtGui

from beeref.fileio.ondisk import looks
from beeref.fileio.sql import SQLiteIO
from beeref.items import BeeTextItem
from beeref.scene import BeeGraphicsScene


def words_in(path):
    """The words of the notes in a board file."""

    scene = BeeGraphicsScene(QtGui.QUndoStack())
    io = SQLiteIO(path, scene, readonly=True)
    io.read()
    scene.add_queued_items()
    return sorted(item.toPlainText()
                  for item in scene.items_by_type('text'))


def saved_elsewhere(path, words='theirs', mark='their-mark'):
    """The board saved on another computer, and synced here."""

    scene = BeeGraphicsScene(QtGui.QUndoStack())
    scene.addItem(BeeTextItem(words))
    before = looks(path)
    SQLiteIO(path, scene, create_new=True, mark=mark).write()
    if before is not None:
        # Whatever the clock's grain, it looks different now
        os.utime(path, ns=(before[1] + 2 * 10**9, before[1] + 2 * 10**9))


def save(view, qtbot, path, create_new=True):
    view.do_save(path, create_new=create_new)
    qtbot.waitUntil(lambda: not view.worker.isRunning(), timeout=10000)
    qtbot.waitUntil(lambda: view.undo_stack.isClean(), timeout=5000)
