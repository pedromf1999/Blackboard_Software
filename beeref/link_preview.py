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

"""The picture a web page offers for showing a link to it, and the
site's icon.

Sites name a picture for whoever shows a link to them -- a chat, a
social network -- in the page's head: Open Graph's "og:image", Twitter's
"twitter:image", or the older "image_src". It is the photograph of the
product, the still of the video, the cover of the article. The icon is
the one a browser's tab shows.

Fetched with Qt's own network, not Python's: Qt checks a site's
certificate against the computer's own list, on Windows and on a Mac
alike, where Python, packed into an application, often has no list to
check against and refuses every https site.
"""

from html.parser import HTMLParser
import logging
import re
from urllib.parse import urljoin

from PyQt6 import QtCore, QtGui, QtNetwork


logger = logging.getLogger(__name__)


# A web address and nothing else, as it is pasted
LINK_RE = re.compile(r'^(?:https?://|www\.)\S+$', re.IGNORECASE)

# Where a page names its picture, best first
IMAGE_PROPERTIES = ('og:image:secure_url', 'og:image', 'og:image:url',
                    'twitter:image', 'twitter:image:src')

# How long to wait for a site, and how much of it to take. A page names
# its picture in its head, near the start, and a picture for a link is
# a few hundred kilobytes.
TIMEOUT_MS = 15000
MAX_PAGE_BYTES = 3 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024
# An icon is small, and not worth waiting long for: the picture comes
# without it rather than late
MAX_ICON_BYTES = 1024 * 1024
ICON_TIMEOUT_MS = 6000

# An icon at least this wide looks sharp in the corner of a picture
SHARP_ICON = 64

# Some sites send a page meant for programs, without the picture, to
# anything that does not say it is a browser
USER_AGENT = (b'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              b'AppleWebKit/537.36 (KHTML, like Gecko) '
              b'Chrome/126.0 Safari/537.36')


def link_in(text):
    """The web address the text is, or None.

    Only text that is a web address and nothing more: an address in a
    sentence is a note that mentions it.
    """

    text = (text or '').strip()
    if not LINK_RE.match(text):
        return None
    if text.lower().startswith('www.'):
        return f'https://{text}'
    return text


class PageReader(HTMLParser):
    """Reads a page's head for the picture it offers, and its icons."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = {}
        # (kind, href, sizes, type) for each icon the page names
        self.icons = []

    def handle_starttag(self, tag, attrs):
        attrs = {key.lower(): value for key, value in attrs if value}
        if tag == 'meta':
            name = (attrs.get('property') or attrs.get('name') or '').lower()
            if name in IMAGE_PROPERTIES and attrs.get('content'):
                self.found.setdefault(name, attrs['content'].strip())
        elif tag == 'link' and attrs.get('href'):
            rel = (attrs.get('rel') or '').lower().split()
            href = attrs['href'].strip()
            if 'image_src' in rel:
                self.found.setdefault('image_src', href)
            if 'icon' in rel or 'apple-touch-icon' in rel:
                self.icons.append((
                    'apple' if 'apple-touch-icon' in rel else 'icon', href,
                    (attrs.get('sizes') or '').lower(),
                    (attrs.get('type') or '').lower()))


def read_page(html, page_url):
    """What a page offers: its picture's address, and its icon's."""

    reader = PageReader()
    try:
        reader.feed(html)
    except Exception:
        # A page bad enough to stop the reader may still have named its
        # picture before it did
        logger.debug(f'Could not read all of {page_url}')
    image = None
    for name in IMAGE_PROPERTIES + ('image_src',):
        if name in reader.found:
            image = urljoin(page_url, reader.found[name])
            break
    return image, icon_urls(reader.icons, page_url)


def preview_image_url(html, page_url):
    """The address of the picture a page offers, or None."""

    return read_page(html, page_url)[0]


def icon_side(sizes, kind):
    """How wide an icon says it is; a drawing scales to any size."""

    if sizes == 'any' or 'svg' in kind:
        return 1000
    sides = [int(side) for side in re.findall(r'(\d+)x\d+', sizes)]
    return max(sides) if sides else 0


def icon_urls(icons, page_url):
    """Where the site's icon may be, best first: the one its tab shows,
    at its sharpest.

    A tab shows the "icon" the page names, often only 16 or 32 pixels
    wide, which in the corner of a picture would be a blur. Those at
    least 64 wide, or drawn rather than painted, come first; then the
    icon the site offers phones for their home screens, which is the
    same mark drawn larger; then the smaller tab icons; and last
    favicon.ico, where browsers have always looked. The next is tried
    when one cannot be had: a site's own address for its icon is
    sometimes wrong.
    """

    def biggest(kind):
        return sorted((icon for icon in icons if icon[0] == kind),
                      key=lambda icon: icon_side(icon[2], icon[3]),
                      reverse=True)

    tab = biggest('icon')
    sharp = [icon for icon in tab
             if icon_side(icon[2], icon[3]) >= SHARP_ICON]
    ordered = sharp + biggest('apple') + [
        icon for icon in tab if icon not in sharp]
    urls = []
    for icon in ordered:
        url = urljoin(page_url, icon[1])
        if url not in urls:
            urls.append(url)
    favicon = urljoin(page_url, '/favicon.ico')
    if favicon not in urls:
        urls.append(favicon)
    return urls


def icon_from(data):
    """The largest picture in an icon file, which may hold several."""

    buffer = QtCore.QBuffer()
    buffer.setData(QtCore.QByteArray(data))
    buffer.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
    reader = QtGui.QImageReader(buffer)
    if bytes(reader.format()) == b'svg' and reader.size().isValid():
        # A drawing is read at the size it says it is, often 32: drawn
        # larger instead, so that it is as sharp as a painted one
        reader.setScaledSize(reader.size().scaled(
            256, 256, QtCore.Qt.AspectRatioMode.KeepAspectRatio))
    best = QtGui.QImage()
    for _ in range(max(reader.imageCount(), 1)):
        image = reader.read()
        if not image.isNull() and image.width() > best.width():
            best = image
        if not reader.jumpToNextImage():
            break
    if best.isNull():
        best = QtGui.QImage.fromData(data)
    return best


def page_text(data, content_type):
    """The words of a page, in the encoding it says it is in."""

    match = re.search(r'charset=([\w-]+)', content_type or '', re.I)
    if match is None:
        match = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', data[:4096],
                          re.I)
        encoding = match.group(1).decode('ascii') if match else 'utf-8'
    else:
        encoding = match.group(1)
    try:
        return data.decode(encoding, errors='replace')
    except LookupError:
        return data.decode('utf-8', errors='replace')


class LinkPreview(QtCore.QObject):
    """Fetches the picture and the icon for one link, while the window
    goes on working.

    Emits ``finished`` once: the picture, or a null one; the site's
    icon, or a null one -- the picture is worth having without it; and
    why there is no picture, if there is none.
    """

    finished = QtCore.pyqtSignal(QtGui.QImage, QtGui.QImage, str)

    def __init__(self, url, manager, parent=None):
        super().__init__(parent)
        self.url = url
        self.manager = manager
        self.replies = []
        self.done = False
        # Each None until it is in
        self.image = None
        self.icon = None
        # Where the icon may be, still to be tried
        self.icon_addresses = []

    def start(self):
        self.request(self.url, self.on_page, MAX_PAGE_BYTES, TIMEOUT_MS)

    def request(self, url, then, limit, timeout):
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
        request.setRawHeader(b'User-Agent', USER_AGENT)
        request.setRawHeader(b'Accept-Language', b'pt-PT,pt;q=0.9,en;q=0.8')
        request.setTransferTimeout(timeout)
        reply = self.manager.get(request)
        self.replies.append(reply)
        reply.downloadProgress.connect(
            lambda received, total, reply=reply:
            received > limit and reply.abort())
        reply.finished.connect(lambda reply=reply: self.answered(reply, then))

    def answered(self, reply, then):
        if reply in self.replies:
            self.replies.remove(reply)
        reply.deleteLater()
        if not self.done:
            then(reply)

    @staticmethod
    def failed(reply):
        return reply.error() != QtNetwork.QNetworkReply.NetworkError.NoError

    def on_page(self, reply):
        if self.failed(reply):
            self.finish(QtGui.QImage(), reply.errorString())
            return
        content_type = str(reply.header(
            QtNetwork.QNetworkRequest.KnownHeaders.ContentTypeHeader) or '')
        data = bytes(reply.readAll())
        # Where the page ended up, after any redirects, is what its own
        # relative addresses are relative to
        page_url = reply.url().toString() or self.url
        if content_type.lower().startswith('image/'):
            # The link was to a picture itself
            self.image = QtGui.QImage.fromData(data)
            self.icon_addresses = [urljoin(page_url, '/favicon.ico')]
        else:
            image_url, self.icon_addresses = read_page(
                page_text(data, content_type), page_url)
            if image_url is None:
                self.finish(QtGui.QImage(), 'The page offers no picture')
                return
            logger.debug(f'Preview picture of {self.url}: {image_url}')
            self.request(image_url, self.on_image, MAX_IMAGE_BYTES,
                         TIMEOUT_MS)
        self.next_icon()
        self.finish_when_both_are_in()

    def next_icon(self):
        """Ask for the next place the icon may be, if any is left."""

        while self.icon_addresses:
            address = self.icon_addresses.pop(0)
            if QtCore.QUrl(address).scheme() in ('http', 'https', 'file'):
                logger.debug(f'Icon of {self.url}: {address}')
                self.request(address, self.on_icon, MAX_ICON_BYTES,
                             ICON_TIMEOUT_MS)
                return
        self.icon = QtGui.QImage()

    def on_image(self, reply):
        if self.failed(reply):
            self.finish(QtGui.QImage(), reply.errorString())
            return
        self.image = QtGui.QImage.fromData(bytes(reply.readAll()))
        self.finish_when_both_are_in()

    def on_icon(self, reply):
        icon = (QtGui.QImage() if self.failed(reply)
                else icon_from(bytes(reply.readAll())))
        if icon.isNull():
            self.next_icon()
        else:
            self.icon = icon
        self.finish_when_both_are_in()

    def finish_when_both_are_in(self):
        if self.image is None or self.icon is None:
            return
        if self.image.isNull():
            self.finish(self.image, 'The picture could not be read')
        else:
            self.finish(self.image, '', self.icon)

    def finish(self, image, reason, icon=None):
        if self.done:
            return
        self.done = True
        for reply in list(self.replies):
            reply.abort()
        if reason:
            logger.info(f'No preview for {self.url}: {reason}')
        self.finished.emit(
            image, QtGui.QImage() if icon is None else icon, reason)

    def cancel(self):
        """Stop, and say nothing more."""

        self.done = True
        for reply in list(self.replies):
            reply.abort()
