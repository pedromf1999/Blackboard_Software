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

"""Pictures opened only as far as they are seen.

A board used to open every picture in it at its full size the moment it
was read, and keep them all open: a board of 323 pictures, 126 MB in its
file, took 5.3 GB of memory and never gave any of it back. A picture of
ten thousand pixels across takes 250 MB open, however small it is drawn.

Now a picture is kept as the file keeps it, compressed, with a small
copy to draw while nothing better is ready. It is opened at the size it
is drawn at -- halved as many times as that allows, so a picture seen
at a tenth of its size is opened at an eighth -- in the background, so
that zooming never waits for it. What has been opened is kept in a store
of limited size and let go once it is no longer seen.
"""

from collections import defaultdict, OrderedDict
import itertools
import logging
import math
import time
import weakref

from PyQt6 import QtCore, QtGui


logger = logging.getLogger(__name__)


# The longest side of the small copy every picture keeps, to draw while
# nothing larger is open. Enough for a board seen whole, where most
# pictures are drawn smaller than this.
THUMBNAIL_SIDE = 256

# How much opened pictures may take between them. Past this, the ones
# seen longest ago are let go -- but never one drawn in the last moment,
# which would only have to be opened again for the next frame.
BUDGET = 512 * 2 ** 20
IN_USE_SECONDS = 2

# Once a picture has not been seen for this long it is let go, unless it
# is in view: that is what brings memory back down to what is on screen
# when the board is left alone.
KEEP_SECONDS = 8

# Opening a large picture takes a moment and a good deal of memory while
# it lasts, so only a couple are opened at once.
THREADS = 2

_keys = itertools.count(1)


def new_key():
    """A name for one picture in the store, never used twice."""

    return next(_keys)


def image_size(data):
    """How big a compressed picture is, without opening it."""

    buffer = QtCore.QBuffer()
    buffer.setData(QtCore.QByteArray(data))
    buffer.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
    return QtGui.QImageReader(buffer).size()


def image_format(data):
    """What a compressed picture is stored as: 'png', 'jpg' or other."""

    buffer = QtCore.QBuffer()
    buffer.setData(QtCore.QByteArray(data))
    buffer.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
    fmt = bytes(QtGui.QImageReader(buffer).format()).decode().lower()
    return 'jpg' if fmt == 'jpeg' else fmt


def open_image(source, size=None):
    """A picture opened at the given size, or at its own.

    From its compressed bytes -- a photograph is opened straight at the
    smaller size, which is far quicker than opening it whole -- or
    scaled from a picture that is already open. Safe off the main thread:
    only QImage is used, never QPixmap.
    """

    if isinstance(source, QtGui.QImage):
        if source.isNull() or size is None or size == source.size():
            return source
        return source.scaled(
            size, QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation)
    buffer = QtCore.QBuffer()
    buffer.setData(QtCore.QByteArray(source))
    buffer.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
    reader = QtGui.QImageReader(buffer)
    if size is not None and size != reader.size():
        reader.setScaledSize(size)
    image = reader.read()
    if image.isNull():
        logger.debug(f'Could not open a picture: {reader.errorString()}')
    return image


def thumbnail_size(size):
    """The size of the small copy of a picture this size."""

    longest = max(size.width(), size.height())
    if longest <= THUMBNAIL_SIDE:
        return QtCore.QSize(size)
    factor = THUMBNAIL_SIDE / longest
    return QtCore.QSize(max(1, round(size.width() * factor)),
                        max(1, round(size.height() * factor)))


def level_size(size, level):
    """A picture's size halved ``level`` times, never below a pixel."""

    step = 2 ** level
    return QtCore.QSize(max(1, math.ceil(size.width() / step)),
                        max(1, math.ceil(size.height() / step)))


def level_for(scale):
    """How many times a picture can be halved for this drawing scale.

    ``scale`` is how many pixels on screen one pixel of the picture
    takes. Halved while that still leaves at least one of its pixels to
    each on screen, so nothing is drawn blurrier than it is seen.
    """

    if scale <= 0 or scale >= 1:
        return 0
    return max(0, math.floor(math.log2(1 / scale)))


def in_grey(image, background):
    """A picture in shades of grey, over the given background.

    Over it rather than keeping the transparency, which the grey format
    cannot hold: see BeePixmapItem.grayscale.
    """

    grey = QtGui.QImage(image.size(), QtGui.QImage.Format.Format_Grayscale8)
    grey.fill(background)
    painter = QtGui.QPainter(grey)
    painter.drawImage(0, 0, image)
    painter.end()
    return grey


class Opening(QtCore.QRunnable):
    """One picture being opened in the background."""

    def __init__(self, store, name, source, size, background):
        super().__init__()
        self.store = store
        self.name = name
        self.source = source
        self.size = size
        self.background = background

    def run(self):
        if self.name not in self.store.waiting:
            # Wanted at another size by now: not worth the work
            return
        image = open_image(self.source, self.size)
        if not image.isNull() and self.background is not None:
            image = in_grey(image, self.background)
        # Handed to the main thread, which is the only one that may make
        # something drawable of it
        self.store.opened.emit(self.name, image)


class OpenedPictures(QtCore.QObject):
    """The pictures opened so far, kept while they are seen.

    Each is named by (picture, level, grey): the picture's key, how many
    times it was halved, and whether it was turned grey.
    """

    opened = QtCore.pyqtSignal(object, QtGui.QImage)

    def __init__(self):
        super().__init__()
        self.entries = OrderedDict()
        # The names in the store, by picture: asked on every frame for
        # each picture being drawn, where going through the whole store
        # would cost more than the frame has
        self.by_picture = defaultdict(set)
        self.total = 0
        # What has been asked for and not yet opened. Read by the jobs
        # themselves, off the main thread, to see whether they are still
        # wanted; only ever changed on the main thread.
        self.waiting = set()
        self.pictures = weakref.WeakValueDictionary()
        self.pool = QtCore.QThreadPool()
        self.pool.setMaxThreadCount(THREADS)
        self.opened.connect(self.on_opened)
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    def stop(self):
        """Let the application close without pictures half opened.

        What has not started is dropped, and what has is waited for,
        rather than left running while the application comes down.
        """

        self.waiting.clear()
        self.pool.clear()
        self.pool.waitForDone()

    @staticmethod
    def cost(pixmap):
        return pixmap.width() * pixmap.height() * max(1, pixmap.depth()) // 8

    def get(self, name):
        entry = self.entries.get(name)
        if entry is None:
            return None
        entry[1] = time.monotonic()
        self.entries.move_to_end(name)
        return entry[0]

    def best(self, key, grey):
        """The largest opened version of a picture, if any is open.

        The fewest halvings is the largest.
        """

        levels = [name[1] for name in self.by_picture.get(key, ())
                  if name[2] == grey]
        if not levels:
            return None
        return self.entries[(key, min(levels), grey)][0]

    def put(self, name, image):
        """Keep an opened picture, and make room for it if need be."""

        if image.isNull():
            return None
        pixmap = QtGui.QPixmap.fromImage(image)
        self.remove(name)
        self.entries[name] = [pixmap, time.monotonic()]
        self.by_picture[name[0]].add(name)
        self.total += self.cost(pixmap)
        self.make_room()
        return pixmap

    def remove(self, name):
        entry = self.entries.pop(name, None)
        if entry is None:
            return
        self.total -= self.cost(entry[0])
        names = self.by_picture.get(name[0])
        if names is not None:
            names.discard(name)
            if not names:
                del self.by_picture[name[0]]

    def make_room(self):
        now = time.monotonic()
        for name in list(self.entries):
            if self.total <= BUDGET:
                break
            if now - self.entries[name][1] < IN_USE_SECONDS:
                # Seen a moment ago; everything after it more recently
                break
            self.remove(name)

    def ask_for(self, picture, name, source, size, background):
        """Open a picture in the background, unless it is on its way.

        A picture wanted at another size than the one already waiting
        to be opened stops waiting for that one: while zooming, only the
        latest size is worth the work. A job not started yet then finds
        it is no longer wanted, and does nothing.
        """

        if name in self.entries or name in self.waiting:
            return
        key = name[0]
        for other in [n for n in self.waiting if n[0] == key]:
            self.waiting.discard(other)
        self.pictures[key] = picture
        self.waiting.add(name)
        self.pool.start(Opening(self, name, source, size, background))

    def on_opened(self, name, image):
        # Kept even if it has been overtaken: it is open now, and the
        # store lets it go once it is not seen
        self.waiting.discard(name)
        if self.put(name, image) is None:
            return
        picture = self.pictures.get(name[0])
        if picture is not None and picture.scene() is not None:
            picture.update()

    def open_now(self, name, source, size, background):
        """Open a picture straight away, for a picture of the board.

        An exported image or a file's thumbnail cannot wait for the
        background, or it would be drawn from the small copy.
        """

        image = open_image(source, size)
        if not image.isNull() and background is not None:
            image = in_grey(image, background)
        return self.put(name, image)

    def forget(self, key):
        """Let go of everything opened of a picture that has changed."""

        for name in list(self.by_picture.get(key, ())):
            self.remove(name)

    def trim(self, in_view):
        """Let go of what is no longer seen.

        ``in_view`` holds, for each picture on screen, the version last
        drawn of it, which is kept however long ago that was. Anything
        else not seen for a few seconds goes.
        """

        now = time.monotonic()
        for name in list(self.entries):
            if in_view.get(name[0]) == name:
                continue
            if now - self.entries[name][1] < KEEP_SECONDS:
                continue
            self.remove(name)

    def clear(self):
        self.entries.clear()
        self.by_picture.clear()
        self.total = 0


_store = None


def opened_pictures():
    """The one store, made the first time it is asked for.

    Asked for from the main thread only -- when a picture is drawn, or
    by the view -- so that pictures opened in the background are handed
    back to the main thread.
    """

    global _store
    if _store is None:
        _store = OpenedPictures()
    return _store


def forget(key):
    """Let go of what was opened of a picture that has changed.

    Nothing to do before the store exists -- which is also what keeps
    this off the store from other threads: a picture read from a file in
    the background is always a new one, with nothing opened yet.
    """

    if _store is not None:
        _store.forget(key)


def opened(name):
    """A version of a picture that is open already, or None."""

    if _store is None:
        return None
    entry = _store.entries.get(name)
    return entry[0] if entry is not None else None
