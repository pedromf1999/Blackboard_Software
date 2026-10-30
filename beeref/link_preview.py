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

import base64
import binascii
from html.parser import HTMLParser
import json
import logging
import re
from urllib.parse import parse_qs, urljoin, urlparse

from PyQt6 import QtCore, QtGui, QtNetwork, QtPdf

from beeref import imagecache


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
# A PDF is drawn from its first page, and has to come whole for that:
# where the pages are is written at its end. A datasheet is a few
# megabytes; a catalogue can be tens.
MAX_PDF_BYTES = 40 * 1024 * 1024
# How wide the first page of a PDF is drawn: as wide as the pictures
# pages offer for their links, give or take
PDF_WIDTH = 1000
ICON_TIMEOUT_MS = 6000

# An icon at least this wide looks sharp in the corner of a picture
SHARP_ICON = 64

# Some sites send a page meant for programs, without the picture, to
# anything that does not say it is a browser
USER_AGENT = (b'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              b'AppleWebKit/537.36 (KHTML, like Gecko) '
              b'Chrome/126.0 Safari/537.36')


# A YouTube video's own code, eleven letters, digits, - and _
YOUTUBE_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')
# A video's still, largest first: not every video has the largest
YOUTUBE_STILLS = ('https://i.ytimg.com/vi/{}/maxresdefault.jpg',
                  'https://i.ytimg.com/vi/{}/hqdefault.jpg')
# YouTube's icon, where Google keeps it, and where browsers look
YOUTUBE_ICONS = (
    'https://www.gstatic.com/youtube/img/branding/favicon/'
    'favicon_144x144.png',
    'https://www.youtube.com/favicon.ico')


def youtube_video(url):
    """The code of the YouTube video a link is to, or None.

    However the link was written: a watch page, youtu.be, a Short, a
    live stream, an embedded player, YouTube Music, the phone site.
    """

    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = (parsed.hostname or '').lower()
    for prefix in ('www.', 'm.', 'music.'):
        if host.startswith(prefix):
            host = host[len(prefix):]
    parts = [part for part in parsed.path.split('/') if part]
    video = None
    if host == 'youtu.be' and parts:
        video = parts[0]
    elif host in ('youtube.com', 'youtube-nocookie.com'):
        if parts == ['watch']:
            video = parse_qs(parsed.query).get('v', [None])[0]
        elif len(parts) >= 2 and parts[0] in ('shorts', 'live', 'embed',
                                              'v'):
            video = parts[1]
    if video and YOUTUBE_ID_RE.match(video):
        return video
    return None


GRABCAD_MODEL_RE = re.compile(r'^/library/([\w-]+)/?$')
GRABCAD_API = 'https://grabcad.com/community/api/v1/models/{}'


def grabcad_model(url):
    """The name of the GrabCAD model a link is to, or None."""

    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if (parsed.hostname or '').lower() not in ('grabcad.com',
                                               'www.grabcad.com'):
        return None
    match = GRABCAD_MODEL_RE.match(parsed.path)
    return match.group(1) if match else None


def without_black_bars(image):
    """The picture without the black bands above and below it.

    YouTube's smaller still is four by three, with a wide video in the
    middle of it and black above and below; on a board those bands are
    only in the way.
    """

    def dark(y):
        for x in range(0, image.width(), max(1, image.width() // 32)):
            color = image.pixelColor(x, y)
            if max(color.red(), color.green(), color.blue()) > 24:
                return False
        return True

    height = image.height()
    top = 0
    while top < height // 3 and dark(top):
        top += 1
    bottom = 0
    while bottom < height // 3 and dark(height - 1 - bottom):
        bottom += 1
    if top < 2 or bottom < 2:
        return image
    return image.copy(0, top, image.width(), height - top - bottom)


def google_image(url):
    """The picture and the page it is on, for a Google Images link to
    one; or None.

    Such a link ("imgres") names both in what follows its "?": the
    picture can be fetched straight away, and the page is the one worth
    keeping in the caption, rather than Google's long address.
    """

    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = (parsed.hostname or '').lower()
    if not (host == 'google.com' or host.startswith('google.')
            or '.google.' in host) or parsed.path != '/imgres':
        return None
    query = parse_qs(parsed.query)
    picture = query.get('imgurl', [None])[0]
    page = query.get('imgrefurl', [None])[0]
    if not picture or urlparse(picture).scheme not in ('http', 'https'):
        return None
    return picture, page


# A picture written out as text, the way a browser copies the address of
# one it holds itself, as Google Images does for its small pictures
DATA_IMAGE_RE = re.compile(r'^data:image/[\w.+-]+;base64,([A-Za-z0-9+/=\s]+)$')


def image_in(text):
    """The picture text is written as, if it is a data: address."""

    match = DATA_IMAGE_RE.match((text or '').strip())
    if match is None:
        return QtGui.QImage()
    try:
        data = base64.b64decode(''.join(match.group(1).split()))
    except (binascii.Error, ValueError):
        return QtGui.QImage()
    return QtGui.QImage.fromData(data)


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
    """Reads a page for the picture it offers, its icons, and the
    pictures in it."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = {}
        # (kind, href, sizes, type) for each icon the page names
        self.icons = []
        # The attributes of each picture in the page, in order
        self.images = []
        # The products the page describes for search engines, as text
        self.structured = []
        # The data a page built by script is built from, as text
        self.page_data = []
        self._reading = None

    def handle_data(self, data):
        if self._reading is not None:
            self._reading[-1] += data

    def handle_endtag(self, tag):
        if tag == 'script':
            self._reading = None

    def handle_starttag(self, tag, attrs):
        attrs = {key.lower(): value for key, value in attrs if value}
        if tag == 'img':
            self.images.append(attrs)
        elif tag == 'script' and 'ld+json' in (attrs.get('type') or ''):
            self._reading = self.structured
            self.structured.append('')
        elif tag == 'script' and (attrs.get('type') == 'application/json'
                                  or attrs.get('id') == '__NEXT_DATA__'):
            self._reading = self.page_data
            self.page_data.append('')
        elif tag == 'meta':
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
    """What a page offers: where its picture may be, best first, and
    where its icon may be."""

    reader = PageReader()
    try:
        reader.feed(html)
    except Exception:
        # A page bad enough to stop the reader may still have named its
        # picture before it did
        logger.debug(f'Could not read all of {page_url}')
    named = None
    for name in IMAGE_PROPERTIES + ('image_src',):
        if name in reader.found:
            named = urljoin(page_url, reader.found[name])
            break
    pictures = []
    if named and not is_logo(named):
        pictures.append(named)
    # Many shops name no picture for links to them, or name their logo:
    # the product's own picture is looked for in the page, the logo
    # kept for when there is none
    structured = structured_image(reader.structured, page_url)
    if structured:
        pictures.append(structured)
    embedded = embedded_image(reader.page_data, page_url)
    if embedded:
        pictures.append(embedded)
    pictures.extend(content_images(reader.images, page_url)[:3])
    if named and is_logo(named):
        pictures.append(named)
    tried = []
    for picture in pictures:
        for each in (picture, readable_format(picture)):
            if each and each not in tried:
                tried.append(each)
    return tried, icon_urls(reader.icons, page_url)


def is_pdf(url, content_type=''):
    """Whether a link is to a PDF: by what the site says it sends, or,
    before it has said, by the address."""

    if (content_type or '').lower().startswith('application/pdf'):
        return True
    return urlparse(url or '').path.lower().endswith('.pdf')


def drawn_first_page(data, width):
    """The first page as a PDF draws it, or a null picture. All that it
    holds of the PDF is gone when this returns."""

    document = QtPdf.QPdfDocument(None)
    buffer = QtCore.QBuffer()
    buffer.setData(data)
    buffer.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
    document.load(buffer)
    if (document.status() != QtPdf.QPdfDocument.Status.Ready
            or document.pageCount() < 1):
        logger.debug(f'PDF not readable: {document.error()}')
        return QtGui.QImage()
    size = document.pagePointSize(0)
    if size.width() <= 0 or size.height() <= 0:
        return QtGui.QImage()
    height = max(1, round(width * size.height() / size.width()))
    page = document.render(0, QtCore.QSize(width, height))
    document.close()
    return page


def pdf_first_page(data, width=PDF_WIDTH):
    """The first page of a PDF, drawn this wide on white; or a null
    picture, for a PDF that cannot be read (or is locked)."""

    # Asked for while other PDFs may be being opened; see imagecache
    with imagecache.PDF_LOCK:
        page = drawn_first_page(data, width)
    if page.isNull():
        return page
    # A page leaves where nothing is printed see-through; on paper, and
    # on the board, it is white
    image = QtGui.QImage(page.size(), QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor('white'))
    painter = QtGui.QPainter(image)
    painter.drawImage(0, 0, page)
    painter.end()
    return image


def readable_format(url):
    """The same picture asked for in a format Qt reads, if the address
    leaves the format to the server.

    Services that size pictures for shops send AVIF when asked for
    "auto", whatever the request says it can read, and Qt reads no
    AVIF. None when the address does not ask for "auto".
    """

    for auto, png in (('format=auto', 'format=png'), ('f_auto', 'f_png'),
                      ('fm=auto', 'fm=png')):
        if auto in url:
            return url.replace(auto, png)
    return None


def is_logo(url):
    name = urlparse(url).path.rsplit('/', 1)[-1].lower()
    return 'logo' in name


def structured_image(texts, page_url):
    """The picture of the product a page describes for search engines,
    in schema.org's terms; or None."""

    def pictures(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for each in value:
                yield from pictures(each)
        elif isinstance(value, dict):
            for key in ('url', 'contentUrl'):
                if isinstance(value.get(key), str):
                    yield value[key]

    def products(value):
        if isinstance(value, list):
            for each in value:
                yield from products(each)
        elif isinstance(value, dict):
            kind = value.get('@type')
            kinds = kind if isinstance(kind, list) else [kind]
            if 'Product' in kinds:
                yield value
            for key in ('@graph', 'mainEntity', 'itemListElement'):
                if key in value:
                    yield from products(value[key])

    for text in texts:
        try:
            data = json.loads(text)
        except ValueError:
            continue
        for product in products(data):
            for picture in pictures(product.get('image')):
                if picture and not picture.startswith('data:'):
                    return urljoin(page_url, picture)
    return None


IMAGE_FILE_RE = re.compile(r'\.(jpe?g|png|webp)(\?|$)', re.IGNORECASE)


def embedded_image(texts, page_url):
    """The product's picture in the data a page is built from, by script
    in the browser; or None.

    Such a page holds no picture until a browser has run its scripts,
    but the data they build it from is in it: Misumi's names the product
    photograph "productImageList". A picture whose place in that data
    says both product and image is taken, before one that says only
    image; one that says it is a drawing of a size, an icon or the like
    is not.
    """

    best = None

    def walk(value, path):
        nonlocal best
        if isinstance(value, dict):
            for key, each in value.items():
                walk(each, path + [str(key).lower()])
        elif isinstance(value, list):
            for each in value:
                walk(each, path)
        elif isinstance(value, str) and IMAGE_FILE_RE.search(value):
            if not value.startswith(('http', '//', '/')):
                return
            named = words(' '.join(path))
            joined = ''.join(path)
            if (named & NOT_THE_THING or 'logo' in joined
                    or any(word in joined for word in (
                        'spec', 'illustration', 'config', 'avatar'))):
                return
            score = (('product' in joined)
                     + any(word in joined for word in (
                         'image', 'photo', 'picture', 'img')) * 2)
            if score >= 2 and (best is None or score > best[0]):
                best = (score, value)

    for text in texts:
        try:
            walk(json.loads(text), [])
        except ValueError:
            continue
    return urljoin(page_url, best[1]) if best else None


# Words that mark a picture in a page as something other than the thing
# the page is about. Matched against whole words of its address, its
# description and its class; "logo" anywhere, as in "mcmlogo". Not the
# names of parts a supplier sells: a seal, a thumb screw, a push button
# and a track roller are all things a page may be about.
NOT_THE_THING = {
    'icon', 'icons', 'sprite', 'flag', 'flags', 'payment', 'paypal', 'visa',
    'mastercard', 'certificate', 'certificado', 'badge', 'selo',
    'avatar', 'placeholder', 'spinner', 'loading', 'loader', 'banner',
    'teaser', 'footer', 'navigation', 'navicon', 'nav', 'menu', 'social',
    'facebook', 'twitter', 'linkedin', 'instagram', 'pinterest', 'whatsapp',
    'pixel', 'tracking', 'blank', 'spacer', 'arrow',
    'cookie', 'emoji', 'rating', 'stars', 'qr', 'thumbnail',
    'picto', 'recycling'}
# Words that mark it as the thing itself, in the ways shops do
THE_THING = {
    'product', 'produto', 'producto', 'produit', 'produkt', 'artikel',
    'article', 'item', 'zoom', 'main', 'hero', 'gallery', 'galeria',
    'featured', 'primary', 'large'}
# The least a picture must be, across and down, when it says how big
SMALLEST = 100
# Wider than this for its height, and it is a banner across the page
WIDEST = 2.5


def words(*texts):
    found = set()
    for text in texts:
        found.update(word for word in re.split(r'[^a-z0-9]+', text.lower())
                     if word)
    return found


def picture_address(attrs):
    """The largest version of a picture the page has, by its address.

    Shops put the small one in "src" and the large one aside for when it
    is clicked or scrolled to.
    """

    for key in ('data-large_image', 'data-zoom-image', 'data-full',
                'data-src', 'data-lazy-src', 'data-original'):
        value = attrs.get(key, '')
        if value.startswith(('http', '/')):
            return value
    sources = []
    for part in (attrs.get('srcset') or attrs.get('data-srcset') or
                 '').split(','):
        bits = part.split()
        if len(bits) == 2 and bits[1].endswith('w') and bits[1][:-1].isdigit():
            sources.append((int(bits[1][:-1]), bits[0]))
    if sources:
        return max(sources)[1]
    return attrs.get('src', '')


def content_image(images, page_url):
    """The picture in a page most likely to be the thing it is about,
    or None; see content_images."""

    found = content_images(images, page_url)
    return found[0] if found else None


def content_images(images, page_url):
    """The pictures in a page likely to be the thing it is about, most
    likely first.

    One a shop marks as its product's -- WordPress's "wp-post-image", a
    "Zoom" picture, "product" in its name, "itemprop" image, one loaded
    first -- before any other; failing those, the largest that is not a
    banner. Logos, icons, flags, means of payment, certificates and the
    like are left out, as are drawings, animations and anything that
    says it is under a hundred pixels. None rather than the wrong one.
    """

    found = []
    for order, attrs in enumerate(images):
        address = picture_address(attrs)
        path = urlparse(address).path.lower()
        if (not address or address.startswith('data:')
                or path.endswith(('.svg', '.gif'))):
            continue
        described = ' '.join((path, attrs.get('alt', ''),
                              attrs.get('class', ''), attrs.get('id', ''),
                              attrs.get('title', '')))
        named = words(described)
        if 'logo' in described.lower() or named & NOT_THE_THING:
            continue
        try:
            width = int(float(attrs.get('width', 0)))
            height = int(float(attrs.get('height', 0)))
        except ValueError:
            width = height = 0
        if (width and width < SMALLEST) or (height and height < SMALLEST):
            continue
        if width and height and max(width / height,
                                    height / width) > WIDEST:
            continue
        marked = (bool(named & THE_THING)
                  or 'wp-post-image' in attrs.get('class', '')
                  or attrs.get('itemprop') == 'image'
                  or attrs.get('fetchpriority') == 'high')
        if not marked and min(width, height) < 2 * SMALLEST:
            # Neither marked as the thing, nor said to be big enough to
            # be taken for it
            continue
        # Marked first, then the largest, then the first in the page
        found.append(((marked, width * height, -order),
                      urljoin(page_url, address)))
    found.sort(reverse=True)
    unique = []
    for score, address in found:
        if address not in unique:
            unique.append(address)
    return unique


def preview_image_url(html, page_url):
    """The address of the picture a page offers, or None."""

    pictures = read_page(html, page_url)[0]
    return pictures[0] if pictures else None


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
        # Where the picture and the icon may be, still to be tried
        self.image_addresses = []
        self.icon_addresses = []
        # Whether the page is still to be read once the places the
        # picture was looked for first have all been tried
        self.page_after = False
        # Whether the icon is already being looked for
        self.icon_asked = False
        # The address the picture is shown with, in its caption
        self.caption = url

    def start(self):
        model = grabcad_model(self.url)
        if model is not None:
            # A model's page is built by script and holds no picture;
            # GrabCAD says where it is when asked
            self.request(GRABCAD_API.format(model), self.on_grabcad,
                         MAX_PAGE_BYTES, TIMEOUT_MS)
            return
        found = google_image(self.url)
        if found is not None:
            picture, page = found
            logger.debug(f'Google Images picture {picture}: {self.url}')
            if page:
                self.caption = page
            self.image_addresses = [picture]
            self.icon_addresses = [urljoin(page or picture, '/favicon.ico')]
            self.next_image()
            self.icon_asked = True
            self.next_icon()
            return
        video = youtube_video(self.url)
        if video is not None:
            # YouTube shows people in Europe a page asking about cookies
            # instead of the video, and that page offers no picture. A
            # video's still and YouTube's icon are where they always
            # are, so they are fetched from there, without the page.
            logger.debug(f'YouTube video {video}: {self.url}')
            self.image_addresses = [
                still.format(video) for still in YOUTUBE_STILLS]
            self.icon_addresses = list(YOUTUBE_ICONS)
            # A stream that is no longer live has no still there; its
            # page may still have one
            self.page_after = True
            self.next_image()
            self.icon_asked = True
            self.next_icon()
            return
        self.request(self.url, self.on_page, self.page_limit, TIMEOUT_MS)

    def on_grabcad(self, reply):
        picture = None
        if not self.failed(reply):
            try:
                picture = json.loads(bytes(reply.readAll())).get(
                    'preview_image')
            except (ValueError, AttributeError):
                picture = None
        if not isinstance(picture, str) or 'missing' in picture:
            # Read the page instead, for what it is worth
            self.request(self.url, self.on_page, self.page_limit, TIMEOUT_MS)
            return
        # The picture shown on a card, and the same one larger
        self.image_addresses = [picture.replace('/card.', '/large.'),
                                picture]
        self.icon_addresses = ['https://grabcad.com/favicon.ico']
        self.next_image()
        self.icon_asked = True
        self.next_icon()

    def next_image(self):
        """Ask for the next place the picture may be; or give up."""

        if not self.image_addresses:
            if self.page_after:
                self.page_after = False
                self.request(self.url, self.on_page, self.page_limit,
                             TIMEOUT_MS)
                return
            self.finish(QtGui.QImage(), 'The picture could not be read')
            return
        self.request(self.image_addresses.pop(0), self.on_image,
                     MAX_IMAGE_BYTES, TIMEOUT_MS)

    def request(self, url, then, limit, timeout):
        """Ask for an address; `limit` is the most of it to take, or
        what says how much once the answer has begun."""

        request = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
        request.setRawHeader(b'User-Agent', USER_AGENT)
        request.setRawHeader(b'Accept-Language', b'pt-PT,pt;q=0.9,en;q=0.8')
        request.setTransferTimeout(timeout)
        reply = self.manager.get(request)
        self.replies.append(reply)
        most = limit if callable(limit) else (lambda reply: limit)
        reply.downloadProgress.connect(
            lambda received, total, reply=reply:
            received > most(reply) and reply.abort())
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

    def page_limit(self, reply):
        """How much of the link to take: a page is read for its head,
        a PDF has to come whole."""

        content_type = str(reply.header(
            QtNetwork.QNetworkRequest.KnownHeaders.ContentTypeHeader) or '')
        url = reply.url().toString() or self.url
        return (MAX_PDF_BYTES if is_pdf(url, content_type)
                else MAX_PAGE_BYTES)

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
            icons = [urljoin(page_url, '/favicon.ico')]
        elif is_pdf(page_url, content_type) or data.startswith(b'%PDF'):
            # A document: its first page, as it would be printed
            self.image = pdf_first_page(data)
            if self.image.isNull():
                self.finish(self.image, 'The PDF could not be read')
                return
            icons = [urljoin(page_url, '/favicon.ico')]
        else:
            pictures, icons = read_page(
                page_text(data, content_type), page_url)
            if not pictures:
                self.finish(QtGui.QImage(), 'The page offers no picture')
                return
            logger.debug(f'Preview picture of {self.url}: {pictures[0]}')
            # Each tried in turn until one can be read
            self.image_addresses = pictures
            self.next_image()
        if not self.icon_asked:
            self.icon_asked = True
            self.icon_addresses = icons
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
        image = (QtGui.QImage() if self.failed(reply)
                 else QtGui.QImage.fromData(bytes(reply.readAll())))
        if image.isNull():
            if self.image_addresses or self.page_after:
                # The next place the picture may be: a YouTube video
                # without the largest still has the next, a shop's
                # picture Qt cannot read has another; and failing all
                # of a video's, its page
                self.next_image()
            elif self.failed(reply):
                self.finish(image, reply.errorString())
            else:
                self.finish(image, 'The picture could not be read')
            return
        if youtube_video(self.url) is not None:
            image = without_black_bars(image)
        self.image = image
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
