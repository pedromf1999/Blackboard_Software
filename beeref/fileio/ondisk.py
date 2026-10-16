# This file is part of BeeRef.
#
# BeeRef is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BeeRef is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BeeRef.  If not, see <https://www.gnu.org/licenses/>.

"""Whether the open board's file has been written by someone else.

A board kept in a folder that Google Drive, OneDrive, Dropbox or iCloud
keeps in step is replaced, now and then, by the version saved on
another computer. This window has to know, because a save here writes
only what changed since the board was read -- written into somebody
else's version, that would mix the two boards up.

Every save leaves a mark of its own in the file, a number made up for
it. The file looking different on disk (its size or its time) is the
first sign; the mark in it then says whether this window wrote it --
a sync program touching a file it is uploading changes its time, not
its mark. Files without a mark, written before marks or by BeeRef, are
known by their size and time alone.
"""

import logging
import os
import pathlib
import sqlite3
import uuid

from beeref.fileio.schema import META_SAVE_MARK_KEY


logger = logging.getLogger(__name__)


def new_mark():
    return uuid.uuid4().hex


def looks(filename):
    """The size and time of a file, or None if it is not there."""

    try:
        found = os.stat(filename)
    except OSError:
        return None
    return (found.st_size, found.st_mtime_ns)


def read_mark(filename):
    """The mark the last save left in a file, or None.

    Only read: never migrates, never creates, and gives up at once
    rather than wait on a file somebody else is writing.
    """

    try:
        uri = pathlib.Path(filename).resolve().as_uri() + '?mode=ro'
        connection = sqlite3.connect(uri, uri=True, timeout=0.2)
    except (sqlite3.Error, OSError, ValueError):
        return None
    try:
        row = connection.execute(
            'SELECT value FROM blackboard_meta WHERE key=?',
            (META_SAVE_MARK_KEY,)).fetchone()
    except sqlite3.Error:
        # No such table, or not a board at all, or half written
        return None
    finally:
        connection.close()
    return row[0] if row else None


class BoardOnDisk:
    """The open board's file, as this window last read or wrote it."""

    def __init__(self):
        self.forget()

    def forget(self):
        """No file: a new board, or one being opened."""

        self.filename = None
        self.looked = None
        self.mark = None

    def remember(self, filename, mark=None):
        """The file as it is now: just read, or just written with this
        mark."""

        self.filename = filename
        self.looked = looks(filename)
        self.mark = mark if mark is not None else read_mark(filename)
        logger.debug(f'On disk: {filename} {self.looked} {self.mark}')

    def changed_elsewhere(self):
        """Whether the file has been written by someone else since.

        A file gone missing is not counted: it may be on its way back,
        and saving will put it there again anyway.
        """

        if self.filename is None or self.looked is None:
            return False
        now = looks(self.filename)
        if now is None or now == self.looked:
            return False
        mark = read_mark(self.filename)
        if mark is not None and mark == self.mark:
            # Touched, not written: as it is, it is still this window's
            self.looked = now
            return False
        logger.info(f'{self.filename} was written elsewhere: '
                    f'{self.looked} {self.mark} -> {now} {mark}')
        return True
