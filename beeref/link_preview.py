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

"""The picture a web page offers for showing a link to it.

Sites name one for whoever shows a link to them -- a chat, a social
network -- in the page's head: Open Graph's "og:image", Twitter's
"twitter:image", or the older "image_src". It is the photograph of the
product, the still of the video, the cover of the article.

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


class PreviewImageFinder(HTMLParser):
    """Reads a page's head for the picture it offers."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = {}

    def handle_starttag(self, tag, attrs):
        attrs = {key.lower(): value for key, value in attrs if value}
        if tag == 'meta':
            name = (attrs.get('property') or attrs.get('name') or '').lower()
            if name in IMAGE_PROPERTIES and attrs.get('content'):
                self.found.setdefault(name, attrs['content'].strip())
        elif tag == 'link':
            if 'image_src' in (attrs.get('rel') or '').lower().split():
                if attrs.get('href'):
                    self.found.setdefault('image_src', attrs['href'].strip())


def preview_image_url(html, page_url):
    """The address of the picture a page offers, or None."""

    finder = PreviewImageFinder()
    try:
        finder.feed(html)
    except Exception:
        # A page bad enough to stop the reader may still have named its
        # picture before it did
        logger.debug(f'Could not read all of {page_url}')
    for name in IMAGE_PROPERTIES + ('image_src',):
        if name in finder.found:
            return urljoin(page_url, finder.found[name])
    return None


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
    """Fetches the picture for one link, away from the window's work.

    Emits ``finished`` once, with the picture or a null one and why.
    """

    finished = QtCore.pyqtSignal(QtGui.QImage, str)

    def __init__(self, url, manager, parent=None):
        super().__init__(parent)
        self.url = url
        self.manager = manager
        self.reply = None
        self.done = False

    def start(self):
        self.request(self.url, self.on_page, MAX_PAGE_BYTES)

    def request(self, url, then, limit):
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
        request.setRawHeader(b'User-Agent', USER_AGENT)
        request.setRawHeader(b'Accept-Language', b'pt-PT,pt;q=0.9,en;q=0.8')
        request.setTransferTimeout(TIMEOUT_MS)
        self.reply = self.manager.get(request)
        self.reply.downloadProgress.connect(
            lambda received, total, reply=self.reply:
            received > limit and reply.abort())
        self.reply.finished.connect(
            lambda reply=self.reply: self.answered(reply, then))

    def answered(self, reply, then):
        reply.deleteLater()
        if self.done:
            return
        if reply.error() != QtNetwork.QNetworkReply.NetworkError.NoError:
            self.finish(QtGui.QImage(), reply.errorString())
            return
        then(reply)

    def on_page(self, reply):
        content_type = reply.header(
            QtNetwork.QNetworkRequest.KnownHeaders.ContentTypeHeader) or ''
        data = bytes(reply.readAll())
        if str(content_type).lower().startswith('image/'):
            # The link was to a picture itself
            self.on_image_data(data)
            return
        # Where the page ended up, after any redirects, is what its own
        # relative addresses are relative to
        page_url = reply.url().toString() or self.url
        image_url = preview_image_url(
            page_text(data, str(content_type)), page_url)
        if image_url is None:
            self.finish(QtGui.QImage(), 'The page offers no picture')
            return
        logger.debug(f'Preview picture of {self.url}: {image_url}')
        self.request(image_url, self.on_image, MAX_IMAGE_BYTES)

    def on_image(self, reply):
        self.on_image_data(bytes(reply.readAll()))

    def on_image_data(self, data):
        image = QtGui.QImage.fromData(data)
        if image.isNull():
            self.finish(image, 'The picture could not be read')
        else:
            self.finish(image, '')

    def finish(self, image, reason):
        if self.done:
            return
        self.done = True
        if reason:
            logger.info(f'No preview for {self.url}: {reason}')
        self.finished.emit(image, reason)

    def cancel(self):
        """Stop, and say nothing more."""

        self.done = True
        if self.reply is not None:
            self.reply.abort()
