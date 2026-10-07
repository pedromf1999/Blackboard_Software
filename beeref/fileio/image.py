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

import logging
import os.path
import tempfile
from urllib.error import URLError
from urllib import parse, request

from PyQt6 import QtCore, QtGui

import exif
from lxml import etree


logger = logging.getLogger(__name__)

# What every JPEG file begins with
JPEG_START = b'\xff\xd8'

# How many dropped files are held open at once. A Mac lets a program
# have 256 files open in all; the rest of a larger drop is opened as it
# is read, the way every file used to be.
HELD_AT_ONCE = 64


def held_open(sources):
    """Open the files that were dropped, while the drop is still going on.

    The picture of a screenshot that a Mac shows in the corner of the
    screen is a file in a temporary folder, taken away again the moment
    it has been dropped somewhere. Pictures are read on a thread of
    their own, a moment after the drop, and by then that file was gone:
    "1 image could not be opened". A file that is held open can still be
    read once it has been taken away, and holding it costs nothing --
    where reading it here would keep the window waiting on any file
    that has to be fetched from somewhere first.

    Each local file that could be opened comes back as ``(path, file)``,
    and everything else as it came.
    """

    held = []
    opened = 0
    for source in sources:
        if (opened < HELD_AT_ONCE and isinstance(source, QtCore.QUrl)
                and source.isLocalFile()):
            path = os.path.normpath(source.toLocalFile())
            try:
                held.append((path, open(path, 'rb')))
                opened += 1
                continue
            except OSError as e:
                logger.info(f'Dropped, and not there to be opened: {e}')
        held.append(source)
    return held


def let_go(sources):
    """Close whatever is still held open; see held_open."""

    for source in sources:
        if isinstance(source, tuple):
            source[1].close()


def name_of(source):
    """What a picture brought in goes by: a path, or an address."""

    if isinstance(source, tuple):
        return source[0]
    if isinstance(source, QtCore.QUrl):
        return source.toString()
    return source


def image_from(data, path=None):
    """A picture from the contents of a file.

    Told what it is by what it holds; and where that says nothing, as
    it does not for every kind of file, by how the file is named.
    """

    img = QtGui.QImage.fromData(data)
    suffix = os.path.splitext(path or '')[1].lstrip('.')
    if img.isNull() and suffix:
        img = QtGui.QImage.fromData(data, suffix)
    return img


def exif_rotated_image(path=None, data=None):
    """Returns a QImage that is transformed according to the source's
    orientation EXIF data.

    Given the contents of the file as ``data``, the file itself is left
    alone. Without, it is read once, here: read once for the picture and
    again for which way up it is, a file taken away in between ended the
    thread it was read on.
    """

    if data is None:
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except (OSError, TypeError):
            return QtGui.QImage()

    img = image_from(data, path)
    if img.isNull():
        return img

    # Only a JPEG says which way up it is in a way the reader below
    # knows. Given anything else it goes through the picture itself
    # for the two bytes that would begin that in a JPEG, finds them
    # sooner or later in a file of any size, and reads what follows
    # as though it meant something: a screenshot of a few megabytes
    # was sure to send it wrong.
    if not data.startswith(JPEG_START):
        return img
    try:
        exifimg = exif.Image(data)
    except Exception:
        # Which way up it is can be done without; the picture cannot
        logger.exception(f'Exif parser failed on image: {path}')
        return img

    try:
        if 'orientation' in exifimg.list_all():
            orientation = exifimg.orientation
        else:
            return img
    except Exception:
        logger.exception(f'Exif failed reading orientation of image: {path}')
        return img

    transform = QtGui.QTransform()

    if orientation == exif.Orientation.TOP_RIGHT:
        return img.mirrored(horizontal=True, vertical=False)
    if orientation == exif.Orientation.BOTTOM_RIGHT:
        transform.rotate(180)
        return img.transformed(transform)
    if orientation == exif.Orientation.BOTTOM_LEFT:
        return img.mirrored(horizontal=False, vertical=True)
    if orientation == exif.Orientation.LEFT_TOP:
        transform.rotate(90)
        return img.transformed(transform).mirrored(
            horizontal=True, vertical=False)
    if orientation == exif.Orientation.RIGHT_TOP:
        transform.rotate(90)
        return img.transformed(transform)
    if orientation == exif.Orientation.RIGHT_BOTTOM:
        transform.rotate(270)
        return img.transformed(transform).mirrored(
            horizontal=True, vertical=False)
    if orientation == exif.Orientation.LEFT_BOTTOM:
        transform.rotate(270)
        return img.transformed(transform)

    return img


def load_image(path):
    if isinstance(path, tuple):
        # Held open since it was dropped; see held_open
        path, held = path
        with held:
            data = held.read()
        return (exif_rotated_image(path, data), path)
    if isinstance(path, str):
        path = os.path.normpath(path)
        return (exif_rotated_image(path), path)
    if path.isLocalFile():
        path = os.path.normpath(path.toLocalFile())
        return (exif_rotated_image(path), path)

    url = bytes(path.toEncoded()).decode()
    domain = '.'.join(parse.urlparse(url).netloc.split(".")[-2:])
    img = exif_rotated_image()
    if domain == 'pinterest.com':
        try:
            page_data = request.urlopen(url).read()
            root = etree.HTML(page_data)
            url = root.xpath("//img")[0].get('src')
        except Exception as e:
            logger.debug(f'Pinterest image download failed: {e}')
    try:
        imgdata = request.urlopen(url).read()
    except URLError as e:
        logger.debug(f'Downloading image failed: {e.reason}')
    else:
        with tempfile.TemporaryDirectory() as tmp:
            fname = os.path.join(tmp, 'img')
            with open(fname, 'wb') as f:
                f.write(imgdata)
                logger.debug(f'Temporarily saved in: {fname}')
            img = exif_rotated_image(fname)
    return (img, url)
