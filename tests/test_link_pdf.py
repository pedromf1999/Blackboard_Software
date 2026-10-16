"""A link to a PDF comes in as its first page."""

import os
import random
from types import SimpleNamespace

from PyQt6 import QtCore, QtGui, QtNetwork

from beeref import link_preview
from beeref.link_preview import LinkPreview, is_pdf, pdf_first_page


def make_pdf(path, noise=0):
    """A one-page A4 PDF: a red square in the middle of white, and, to
    make it big, a picture of noise this many pixels wide."""

    writer = QtGui.QPdfWriter(path)
    writer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4))
    writer.setResolution(72)
    painter = QtGui.QPainter(writer)
    painter.fillRect(QtCore.QRect(200, 300, 195, 240), QtGui.QColor('red'))
    if noise:
        image = QtGui.QImage(noise, noise, QtGui.QImage.Format.Format_RGB32)
        bits = random.Random(1).randbytes(noise * noise * 4)
        for y in range(noise):
            for x in range(noise):
                i = (y * noise + x) * 4
                image.setPixel(x, y, int.from_bytes(bits[i:i + 4], 'little'))
        painter.drawImage(QtCore.QRect(20, 20, 150, 150), image)
    painter.end()
    return path


def preview_of(qtbot, url):
    manager = QtNetwork.QNetworkAccessManager()
    preview = LinkPreview(url, manager)
    result = {}
    preview.finished.connect(
        lambda image, icon, reason: result.update(image=image,
                                                  reason=reason))
    preview.start()
    qtbot.waitUntil(lambda: bool(result), timeout=15000)
    return result


class LocalServer:
    """Answers every request with this, and keeps the server going."""

    def __init__(self, content_type, body):
        self.answer = (
            f'HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\n'
            f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n'
        ).encode('ascii') + body
        self.server = QtNetwork.QTcpServer()
        assert self.server.listen(QtNetwork.QHostAddress(
            QtNetwork.QHostAddress.SpecialAddress.LocalHost), 0)
        self.server.newConnection.connect(self.on_connection)
        self.sockets = []

    def url(self, path):
        return f'http://127.0.0.1:{self.server.serverPort()}{path}'

    def on_connection(self):
        socket = self.server.nextPendingConnection()
        self.sockets.append(socket)

        def on_ready():
            if b'\r\n\r\n' in bytes(socket.peek(65536)):
                socket.readAll()
                socket.write(self.answer)
                socket.disconnectFromHost()

        socket.readyRead.connect(on_ready)


def test_is_pdf():
    assert is_pdf('https://www.ti.com/lit/ds/symlink/lm358.pdf')
    assert is_pdf('https://example.com/Datasheet.PDF?download=1')
    assert is_pdf('https://arxiv.org/pdf/1706.03762', 'application/pdf')
    assert not is_pdf('https://arxiv.org/pdf/1706.03762', 'text/html')
    assert not is_pdf('https://example.com/pdf-guide.html')


def test_the_first_page_drawn_on_white(tmpdir):
    path = make_pdf(os.path.join(str(tmpdir), 'doc.pdf'))
    with open(path, 'rb') as f:
        page = pdf_first_page(f.read())
    assert page.width() == link_preview.PDF_WIDTH
    # A4 is 1 wide to 1.414 high
    assert abs(page.height() / page.width() - 297 / 210) < 0.01
    assert page.pixelColor(5, 5).name() == '#ffffff'
    middle = page.pixelColor(page.width() // 2, page.height() // 2)
    assert middle.red() > 200 and middle.green() < 60


def test_something_else_is_no_page():
    assert pdf_first_page(b'%PDF-1.4 and nothing more').isNull()
    assert pdf_first_page(b'').isNull()


def test_a_link_to_a_pdf_comes_in_as_its_first_page(qtbot, tmpdir):
    path = make_pdf(os.path.join(str(tmpdir), 'datasheet.pdf'))
    result = preview_of(qtbot, QtCore.QUrl.fromLocalFile(path).toString())
    assert result['reason'] == ''
    assert result['image'].width() == link_preview.PDF_WIDTH


def test_a_pdf_bigger_than_a_page_is_taken_whole(qtbot, tmpdir, monkeypatch):
    # Served as a PDF from an address that does not say so, and bigger
    # than the most of a page that is read -- made smaller here, so that
    # a PDF quick to make is past it
    monkeypatch.setattr(link_preview, 'MAX_PAGE_BYTES', 50 * 1024)
    path = make_pdf(os.path.join(str(tmpdir), 'big.pdf'), noise=400)
    with open(path, 'rb') as f:
        data = f.read()
    assert len(data) > link_preview.MAX_PAGE_BYTES
    server = LocalServer('application/pdf', data)
    result = preview_of(qtbot, server.url('/pdf/1706.03762'))
    assert result['reason'] == ''
    assert result['image'].width() == link_preview.PDF_WIDTH


def test_a_pdf_that_cannot_be_read_says_so(qtbot, tmpdir):
    server = LocalServer('application/pdf', b'%PDF-1.4 broken')
    result = preview_of(qtbot, server.url('/broken.pdf'))
    assert result['image'].isNull()
    assert result['reason'] == 'The PDF could not be read'


def reply_saying(url, content_type):
    return SimpleNamespace(
        url=lambda: QtCore.QUrl(url),
        header=lambda which: content_type)


def test_only_a_pdf_is_taken_beyond_the_most_of_a_page():
    preview = LinkPreview('https://example.com/x', None)
    assert preview.page_limit(reply_saying(
        'https://example.com/x', 'application/pdf')) \
        == link_preview.MAX_PDF_BYTES
    assert preview.page_limit(reply_saying(
        'https://example.com/a.pdf', None)) == link_preview.MAX_PDF_BYTES
    assert preview.page_limit(reply_saying(
        'https://example.com/x', 'text/html; charset=utf-8')) \
        == link_preview.MAX_PAGE_BYTES
